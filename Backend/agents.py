import json
import re
from datetime import datetime
from config import heavy_llm, light_llm, tavily_tool
from state import AgencyState

def clean_code_output(content: str) -> str:
    """Extracts clean raw code from LLM output, preventing duplicates."""
    blocks = re.findall(r'```(?:[\w+-]+)?\n(.*?)```', content, re.DOTALL)
    if blocks:
        for block in blocks:
            if block.strip():
                return block.strip()
    cleaned = re.sub(r'^```(?:\w+)?\n', '', content.strip())
    cleaned = re.sub(r'\n```$', '', cleaned)
    return cleaned.strip()

def intent_classifier(state: AgencyState):
    from datetime import datetime
    current_time = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
    
    prompt = f"""
    Current System Time: {current_time}
    User Message: {state['messages'][-1].content}
    
    If the user is asking to build/write software, output strictly JSON: {{"is_build": true}}
    If NOT, answer their question naturally (use the Current System Time if they ask for the date or time) and output strictly JSON: {{"is_build": false, "reply": "Your reply here"}}
    """
    try:
        response = light_llm.invoke(prompt)
        cleaned = re.sub(r'```(?:json)?', '', response.content).strip()
        parsed = json.loads(cleaned)
        return {"is_build_request": parsed.get("is_build", True), "chat_response": parsed.get("reply", "")}
    except:
        return {"is_build_request": True, "chat_response": ""}


def project_manager(state: AgencyState):
    user_request = state['messages'][-1].content
    current_time = datetime.now().strftime("%A, %B %d, %Y")
    
    try:
        search_query = light_llm.invoke(f"Search query for latest docs on: {user_request}").content
        raw_results = tavily_tool.invoke({"query": search_query.replace('"', '').strip()})
        research_context = "\n\n".join([f"Source: {res['url']}\nContent: {res['content']}" for res in raw_results])
    except:
        research_context = "No internet context available."

    prompt = f"""
    You are a Technical Lead. User Request: {user_request}
    Current Date: {current_time}
    
    INSTRUCTIONS:
    1. Write a crisp, concise bulleted list of the Tech Stack and Core Features. Do NOT write long paragraphs.
    2. Provide a JSON list of the exact files to create at the very end.
    
    CRITICAL TOKEN RULES:
    - Break the project into small, modular files.
    - DO NOT include 'README.md' by default to save tokens unless the user specifically asked for documentation.
    
    Format the file list EXACTLY like this on a new line:
    FILES: ["index.html", "style.css", "app.js"]
    """
    response = heavy_llm.invoke(prompt)
    content = response.content
    
    file_queue = ["index.html"]
    match = re.search(r'FILES:\s*(\[.*?\])', content, re.DOTALL)
    if match:
        try:
            file_queue = json.loads(match.group(1))
        except:
            pass

    plan_display = re.sub(r'FILES:\s*\[.*?\]', '', content, flags=re.DOTALL).strip()

    chat_msg = (
        f"### Architecture Blueprint\n\n"
        f"{plan_display}\n\n"
        f"📋 **Planned Files:**\n"
        f"- {', '.join(file_queue)}\n\n"
        f"*(Note: `README.md` is omitted to save tokens. Reply 'add readme' if you want one).* \n\n"
        f"Click **Approve & Build** (or type 'continue') to generate `{file_queue[0]}`, or ask any questions first."
    )

    return {
        "project_plan": content, 
        "research_context": research_context,
        "file_queue": file_queue,
        "code_files": {},
        "is_approved": False,
        "chat_response": chat_msg
    }

def human_approval(state: AgencyState):
    pass 

def coder_agent(state: AgencyState):
    queue = list(state.get("file_queue", []))
    built_code = dict(state.get("code_files", {}))
    
    if not queue:
        return {
            "chat_response": "✅ All files are generated! Everything is complete.",
            "is_approved": False
        }
    
    current_file = queue.pop(0)
    
    prompt = f"""
    Project Plan: {state.get('project_plan', '')}
    Files already built: {list(built_code.keys())}
    
    CRITICAL INSTRUCTION:
    Write the COMPLETE, production-ready code ONLY for '{current_file}'.
    KEEP IT CONCISE. Focus on core logic and avoid unnecessary boilerplate to prevent token cutoffs.
    Do NOT output JSON. Do NOT write conversational introductions or conclusions. Output ONLY the code inside a single markdown code block.
    """
    response = heavy_llm.invoke(prompt)
    
    raw_code = clean_code_output(response.content)
    built_code[current_file] = raw_code
    
    ext = current_file.split('.')[-1] if '.' in current_file else ''
    
    if queue:
        next_msg = (
            f"✅ **Generated `{current_file}`**\n\n"
            f"```{ext}\n{raw_code}\n```\n\n"
            f"📋 **Queue Status:**\n"
            f"- **Next to build:** `{queue[0]}`\n"
            f"- **Remaining in queue:** {', '.join(queue)}\n\n"
            f"Ready to build **`{queue[0]}`**? Click **Approve & Build** (or type 'continue'). You can also ask any questions or request changes before we proceed."
        )
    else:
        next_msg = (
            f"✅ **Generated `{current_file}`**\n\n"
            f"```{ext}\n{raw_code}\n```\n\n"
            f"🎉 **All planned files are complete!**\n"
            f"You can review the code above, ask questions, or make revisions."
        )

    return {
        "code_files": built_code,
        "file_queue": queue,
        "chat_response": next_msg,
        "is_approved": False
    }

def qa_agent(state: AgencyState):
    user_message = state['messages'][-1].content
    file_queue = list(state.get("file_queue", []))
    code_files = dict(state.get("code_files", {}))
    project_plan = state.get("project_plan", "")
    
    # Inject live system time for context
    current_time = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
    
    msg_lower = user_message.lower()
    note = ""
    
    if "readme" in msg_lower and any(w in msg_lower for w in ["add", "include", "create", "generate"]):
        if "README.md" not in file_queue:
            file_queue.append("README.md")
            note = "*(I've added `README.md` to the generation queue)*\n\n"
        else:
            note = "*(`README.md` is already in the queue)*\n\n"
    elif "readme" in msg_lower and any(w in msg_lower for w in ["remove", "skip", "delete", "without", "no"]):
        file_queue = [f for f in file_queue if "readme" not in f.lower()]
        note = "*(I've removed `README.md` from the generation queue)*\n\n"

    built_names = list(code_files.keys())
    
    prompt = f"""
    You are an intelligent, helpful AI software assistant.
    Current System Time: {current_time}
    
    Project Plan:
    {project_plan}

    Files built so far: {built_names}
    Files pending in queue: {file_queue}

    The user is asking a question midway through the build:
    "{user_message}"

    INSTRUCTIONS:
    1. Answer the question directly and concisely. Use the Current System Time if asked about the date/time.
    2. If it is general or unrelated to code, answer it politely and naturally.
    3. If it is technical, provide clear guidance.
    4. Do not output large code blocks unless explicitly requested.
    """
    response = light_llm.invoke(prompt)
    answer = response.content.strip()

    next_file = file_queue[0] if file_queue else None
    if next_file:
        status_text = (
            f"{note}{answer}\n\n"
            f"---\n"
            f"📋 **Queue Status:**\n"
            f"- **Built so far:** {', '.join(built_names) if built_names else 'None'}\n"
            f"- **Next up:** `{next_file}`\n"
            f"- **Remaining:** {', '.join(file_queue)}\n\n"
            f"Would you like to proceed with generating **`{next_file}`**, or do you have any other questions?"
        )
    else:
        status_text = (
            f"{note}{answer}\n\n"
            f"---\n"
            f"All files have been generated! Ready to finalize or answer any additional questions."
        )

    return {
        "chat_response": status_text,
        "file_queue": file_queue,
        "is_approved": False
    }

def delivery_agent(state: AgencyState):
    # Returning an empty dictionary ensures we do NOT overwrite the final
    # chat_response from the coder_agent, keeping your last code file visible.
    return {"github_url": None}