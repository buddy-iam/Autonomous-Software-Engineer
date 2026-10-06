import json
import re
import time
from datetime import datetime
from config import heavy_llm, light_llm, tavily_tool, wikipedia_tool
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
    user_msg = state['messages'][-1].content
    prompt = f"""
    You are a router. Read the user message: "{user_msg}"
    If the user asks to write code, create an app, build software, or modify files, output strictly JSON: {{"is_build": true}}
    If it is a general question, greeting, or fact retrieval, output strictly JSON: {{"is_build": false}}
    """
    try:
        response = light_llm.invoke(prompt)
        cleaned = re.sub(r'```(?:json)?', '', response.content).strip()
        start = cleaned.find('{')
        end = cleaned.rfind('}') + 1
        if start != -1 and end != 0:
            parsed = json.loads(cleaned[start:end])
            return {"is_build_request": parsed.get("is_build", False)}
    except:
        pass
    return {"is_build_request": False}

def general_chat_agent(state: AgencyState):
    """Handles general queries using basic knowledge, Tavily, and Wikipedia."""
    user_request = state['messages'][-1].content
    
    try:
        wiki_context = wikipedia_tool.run(user_request)
    except:
        wiki_context = "No Wikipedia data."
        
    try:
        search_context = tavily_tool.invoke({"query": user_request})
    except:
        search_context = "No search data."

    prompt = f"""
    You are a helpful AI assistant. Answer the user's query naturally.
    User Query: {user_request}
    
    Web Context: {search_context}
    Wiki Context: {wiki_context}
    """
    response = light_llm.invoke(prompt)
    
    return {
        "chat_response": response.content,
        "messages": [AIMessage(content=response.content)]
    }

def project_manager(state: AgencyState):
    user_request = state['messages'][-1].content
    current_time = datetime.now().strftime("%A, %B %d, %Y")
    
    prompt = f"""
    You are a Technical Lead. User Request: {user_request}
    Current Date: {current_time}
    
    INSTRUCTIONS:
    1. Write a concise bulleted list of the Tech Stack and Core Features.
    2. Provide a JSON list of the exact files to create at the very end.
    
    Format EXACTLY like this on a new line:
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
        f"### Architecture Blueprint\n\n{plan_display}\n\n"
        f"📋 **Planned Files:**\n- {queue_display}\n\n"
        f"Click **Approve & Build** (or type 'continue') to generate `{next_file}`, or ask questions first."
    )

    return {
        "project_plan": content, 
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
    - NO placeholders. Output ONLY valid code inside a single markdown code block.
    """
    
    response = heavy_llm.invoke(prompt)
    raw_code = clean_code_output(response.content)
    built_code[current_file] = raw_code
    
    # UI FIX: No code blocks in the chat response!
    if queue:
        next_file = queue[0]
        remaining = len(queue)
        next_msg = (
            f"✅ **Code generation completed for `{current_file}`**.\n\n"
            f"📋 **Next up:** `{next_file}` ({remaining} file{'s' if remaining > 1 else ''} remaining)\n\n"
            f"Ready to build next? Type 'continue' or click Approve."
        )
    else:
        next_msg = f"🎉 **Code generation completed for `{current_file}`!** All planned files are complete."
                
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
    User Message: "{user_message}"
    Files already built: {built_names}

    INSTRUCTIONS:
    1. If the user wants to scrap the plan or start over, set "is_replan": true.
    2. If the user asks to modify a built file, list it in "edit_files".
    Output STRICTLY JSON.
    """
    
    response = light_llm.invoke(prompt)
    is_replan = False
    edit_files = []
    
    try:
        cleaned = re.sub(r'```(?:json)?', '', response.content).strip()
        start = cleaned.find('{')
        end = cleaned.rfind('}') + 1
        if start != -1 and end != 0:
            parsed = json.loads(cleaned[start:end])
            answer = parsed.get("reply", "Understood.")
            is_replan = parsed.get("is_replan", False)
            edit_files = [f for f in parsed.get("edit_files", []) if f in built_names]
    except:
        answer = "I've noted your feedback. Let's adjust."

    lower_msg = user_message.lower()
    if any(k in lower_msg for k in ["start over", "redo", "replan"]):
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
    Output ONLY a JSON array of search-and-replace blocks.
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
        msg = f"✅ **Applied updates to `{current_file}`**."
    except Exception as e:
        msg = f"⚠️ Failed to parse edits for `{current_file}`."

    return {
        "code_files": built_code,
        "edit_queue": queue,
        "chat_response": msg,
        "messages": [AIMessage(content=msg)],
        "is_approved": False
    }

def delivery_agent(state: AgencyState):
    return {"github_url": None}