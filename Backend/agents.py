import json
import re
from langgraph.graph import END
from config import llm
from state import AgencyState
from github_service import push_to_github

def clean_json_output(content: str) -> dict:
    try:
        cleaned = re.sub(r'```(?:json)?', '', content).strip()
        return json.loads(cleaned)
    except Exception:
        return {"error.txt": f"AI failed to output valid JSON. Raw output:\n{content}"}

def intent_classifier(state: AgencyState):
    prompt = f"""
    You are the front-desk AI. User Message: {state['messages'][-1].content}
    Determine if the user is asking to build/write software.
    If YES: Output strictly JSON: {{"is_build": true}}
    If NO: Output strictly JSON: {{"is_build": false, "reply": "Your conversational reply here"}}
    """
    response = llm.invoke(prompt)
    try:
        parsed = clean_json_output(response.content)
        return {"is_build_request": parsed.get("is_build", True), "chat_response": parsed.get("reply", "")}
    except:
        return {"is_build_request": True, "chat_response": ""}

def project_manager(state: AgencyState):
    prompt = f"""
    You are an elite Software Architecture Project Manager.
    User Request/Feedback: {state['messages'][-1].content}
    Break the request down into a logical tech stack and numbered steps.
    Be concise. Do not write code. Only write the architecture plan.
    """
    response = llm.invoke(prompt)
    return {"project_plan": response.content, "is_approved": False}

def human_approval(state: AgencyState):
    pass # Dummy node for interrupt

def coder_agent(state: AgencyState):
    prompt = f"""
    You are a Senior Principal Software Engineer. 
    Write code based ONLY on this plan: {state['project_plan']}
    CRITICAL: Output ONLY a valid JSON object where keys are file paths and values are the raw code string. 
    """
    response = llm.invoke(prompt)
    return {"code_output": clean_json_output(response.content)}

def bug_finder_agent(state: AgencyState):
    if "error.txt" in state.get('code_output', {}):
        return {"test_results": "Syntax generation failed."}
    code_str = json.dumps(state.get('code_output', {}), indent=2)
    prompt = f"Review this codebase:\n{code_str}\nIf perfect, output 'PASS'. Otherwise, clearly list bugs. Do NOT rewrite the code."
    response = llm.invoke(prompt)
    return {"test_results": response.content}

def optimizer_agent(state: AgencyState):
    bugs = state.get('test_results', 'PASS')
    if "PASS" in bugs.upper() and len(bugs) < 10:
        return state 
    code_str = json.dumps(state.get('code_output', {}), indent=2)
    prompt = f"Fix these bugs: {bugs}\nin this code: {code_str}\nOutput ONLY a valid JSON object of the updated files."
    response = llm.invoke(prompt)
    optimized = clean_json_output(response.content)
    if "error.txt" not in optimized:
        return {"code_output": optimized}
    return state

def delivery_agent(state: AgencyState):
    token = state.get("github_token")
    repo_name = state.get("github_repo")
    code_output = state.get("code_output", {})
    
    if not token or not repo_name or "error.txt" in code_output:
        return {"github_url": None}
        
    url = push_to_github(token, repo_name, code_output)
    return {"github_url": url}