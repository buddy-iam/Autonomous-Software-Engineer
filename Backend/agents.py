import json
import re
import time
from datetime import datetime
from config import heavy_llm, light_llm, tavily_tool
from state import AgencyState
from langchain_core.messages import AIMessage, HumanMessage

def clean_code_output(content: str) -> str:
    blocks = re.findall(r'```(?:[\w+-]+)?\n(.*?)```', content, re.DOTALL)
    if blocks:
        for block in blocks:
            if block.strip():
                return block.strip()
    cleaned = re.sub(r'^```(?:\w+)?\n', '', content.strip())
    cleaned = re.sub(r'\n```$', '', cleaned)
    return cleaned.strip()

def intent_classifier(state: AgencyState):
    current_time = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
    
    recent_messages = state['messages'][-5:]
    history_text = "\n".join(
        [f"{'User' if isinstance(m, HumanMessage) else 'AI'}: {m.content}" for m in recent_messages]
    )
    
    prompt = f"""
    Current System Time: {current_time}
    
    Recent Conversation:
    {history_text}
    
    You are an intelligent, witty, and highly capable AI collaborator. 
    Your task is to read the Recent Conversation and reply to the User's LATEST message.
    
    CRITICAL RULES:
    1. DO NOT ever use robotic filler phrases like "I am an AI assistant designed to help". 
    2. Answer existential, casual, or philosophical questions directly and creatively.
    3. You must output STRICTLY JSON.
    
    If the user's LATEST message asks to write code, create an app, or build software:
    {{"is_build": true, "reply": ""}}
    
    If the user is chatting, asking a question, or discussing anything else:
    {{"is_build": false, "reply": "Your natural, direct conversational response here"}}
    
    Output NOTHING ELSE but the raw JSON object.
    """
    
    response = None
    try:
        response = light_llm.invoke(prompt)
        cleaned = re.sub(r'```(?:json)?', '', response.content).strip()
        
        start = cleaned.find('{')
        end = cleaned.rfind('}') + 1
        
        if start != -1 and end != 0:
            cleaned = cleaned[start:end]
            cleaned = cleaned.replace('\n', '\\n')
            parsed = json.loads(cleaned, strict=False)
            
            reply = parsed.get("reply", "")
            return {
                "is_build_request": parsed.get("is_build", False),
                "chat_response": reply,
                "messages": [AIMessage(content=reply)] if reply else []
            }
        else:
            raise ValueError("No JSON found")
            
    except Exception as e:
        if response and response.content:
            fallback_reply = response.content.strip()
            fallback_reply = re.sub(r'^```(?:json)?\s*', '', fallback_reply)
            fallback_reply = re.sub(r'\s*```$', '', fallback_reply)
        else:
            fallback_reply = "I'm listening. What would you like to build or discuss today?"
            
        return {
            "is_build_request": False, 
            "chat_response": fallback_reply,
            "messages": [AIMessage(content=fallback_reply)]
        }

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
    1. Write a crisp, concise bulleted list of the Tech Stack and Core Features.
    2. Provide a JSON list of the exact files to create at the very end.
    
    CRITICAL TOKEN RULES:
    - Break the project into small, modular files.
    - DO NOT include 'README.md' by default unless requested.
    
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
    next_file = file_queue[0] if len(file_queue) > 0 else "the required files"
    queue_display = ', '.join(file_queue) if len(file_queue) > 0 else "No files specified"

    chat_msg = (
        f"### Architecture Blueprint\n\n"
        f"{plan_display}\n\n"
        f"📋 **Planned Files:**\n"
        f"- {queue_display}\n\n"
        f"Click **Approve & Build** (or type 'continue') to generate `{next_file}`, or ask questions first."
    )

    return {
        "project_plan": content, 
        "research_context": research_context,
        "file_queue": file_queue,
        "edit_queue": [],
        "code_files": {},         
        "is_replan": False,       
        "is_approved": False,
        "chat_response": chat_msg,
        "messages": [AIMessage(content=chat_msg)]
    }

def human_approval(state: AgencyState):
    pass 

def coder_agent(state: AgencyState):
    time.sleep(12) 
    
    queue = list(state.get("file_queue", []))
    built_code = dict(state.get("code_files", {}))
    
    if not queue:
        return {"chat_response": "✅ All files generated.", "is_approved": False}
    
    current_file = queue.pop(0)
    
    original_request = state['messages'][0].content if state['messages'] else "A web application."
    
    prompt = f"""
    Original User Request: {original_request}
    
    Project Plan: {state.get('project_plan', '')}
    Files already built: {list(built_code.keys())}
    
    CRITICAL INSTRUCTION:
    Write the COMPLETE, production-ready code ONLY for '{current_file}'.
    - NO placeholders, NO "Lorem Ipsum", and NO dummy comments (e.g., "Add more cards here").
    - Implement the ACTUAL functional logic and design requested by the user.
    - Output ONLY valid code inside a single markdown code block.
    - DO NOT include conversational text, introductions, conclusions, or chat prompts inside the code.
    """
    
    response = heavy_llm.invoke(prompt)
    raw_code = clean_code_output(response.content)
    built_code[current_file] = raw_code
    
    ext = current_file.split('.')[-1] if '.' in current_file else ''
    
    if queue:
        next_file = queue[0]
        remaining = len(queue)
        next_msg = (
            f"✅ **Generated `{current_file}`**\n\n"
            f"```{ext}\n{raw_code}\n```\n\n"
            f"📋 **Next up:** `{next_file}` ({remaining} file{'s' if remaining > 1 else ''} remaining)\n"
            f"Ready to build? Type 'continue' or click Approve."
        )
    else:
        next_msg = (
            f"✅ **Generated `{current_file}`**\n\n"
            f"```{ext}\n{raw_code}\n```\n\n"
            f"🎉 **All planned files are complete!** Everything is ready."
        )
                
    return {
        "code_files": built_code,
        "file_queue": queue,
        "chat_response": next_msg,
        "messages": [AIMessage(content=next_msg)], 
        "is_approved": False
    }

def qa_agent(state: AgencyState):
    user_message = state['messages'][-1].content
    built_names = list(state.get("code_files", {}).keys())
    
    prompt = f"""
    The user is providing feedback or asking a question during an active software build:
    User Message: "{user_message}"
    Files already built: {built_names}

    INSTRUCTIONS:
    1. If the user wants to scrap the plan, start over, or change the core tech stack (e.g. "no, create using vanilla JS instead", "start over", "re-plan"):
       Set "is_replan": true.
    2. If the user asks to modify an existing built file:
       List it in "edit_files".
    3. DO NOT write or generate full code files here. The Coder Agent handles code generation.
    4. Provide a short, direct message in "reply".

    Output STRICTLY JSON:
    {{
        "reply": "Understood, updating the project plan to use vanilla HTML, CSS, and JS.",
        "is_replan": false,
        "edit_files": []
    }}
    """
    
    response = light_llm.invoke(prompt)
    is_replan = False
    edit_files = []
    
    try:
        cleaned = re.sub(r'```(?:json)?', '', response.content).strip()
        start = cleaned.find('{')
        end = cleaned.rfind('}') + 1
        if start != -1 and end != 0:
            cleaned = cleaned[start:end]
            
        parsed = json.loads(cleaned)
        answer = parsed.get("reply", "Understood.")
        is_replan = parsed.get("is_replan", False)
        edit_files = [f for f in parsed.get("edit_files", []) if f in built_names]
    except Exception:
        answer = "I've noted your feedback. Let's adjust the plan."

    lower_msg = user_message.lower()
    if any(k in lower_msg for k in ["start over", "redo", "replan", "no! create", "change tech stack", "instead"]):
        is_replan = True

    status_text = answer
    if edit_files and not is_replan:
        status_text += f"\n\n*(Queued for editing: {', '.join(edit_files)}. Type 'continue' to apply changes.)*"

    return {
        "chat_response": status_text,
        "messages": [AIMessage(content=status_text)],
        "edit_queue": edit_files,
        "is_replan": is_replan,
        "is_approved": False
    }

def edit_agent(state: AgencyState):
    time.sleep(12)
    
    queue = list(state.get("edit_queue", []))
    built_code = dict(state.get("code_files", {}))
    
    if not queue:
        return {"is_approved": False}
        
    current_file = queue.pop(0)
    existing_code = built_code.get(current_file, "")
    user_request = state['messages'][-2].content if len(state['messages']) > 1 else ""
    
    prompt = f"""
    You are fixing an existing file: {current_file}
    User Request: {user_request}
    
    Existing Code:
    ```
    {existing_code}
    ```
    
    INSTRUCTIONS:
    Output ONLY a JSON array of search-and-replace blocks to apply the changes. 
    Do NOT rewrite the whole file. 
    The "search" string MUST perfectly match the existing code, including exact indentation and line breaks.
    
    Format EXACTLY like this:
    [
      {{
        "search": "def old_function():\\n    pass",
        "replace": "def new_function():\\n    return True"
      }}
    ]
    """
    
    response = heavy_llm.invoke(prompt)
    
    try:
        cleaned = clean_code_output(response.content)
        edits = json.loads(cleaned)
        
        for edit in edits:
            search_str = edit.get("search", "")
            replace_str = edit.get("replace", "")
            if search_str in existing_code:
                existing_code = existing_code.replace(search_str, replace_str)
                
        built_code[current_file] = existing_code
        ext = current_file.split('.')[-1] if '.' in current_file else ''
        msg = f"✅ **Applied diff edits to `{current_file}`**\n\n```{ext}\n{existing_code}\n```"
    except Exception as e:
        msg = f"⚠️ Failed to parse edits for `{current_file}`. The AI did not output valid JSON diffs."

    return {
        "code_files": built_code,
        "edit_queue": queue,
        "chat_response": msg,
        "messages": [AIMessage(content=msg)],
        "is_approved": False
    }

def delivery_agent(state: AgencyState):
    return {"github_url": None}