from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Annotated, TypedDict
import operator
import json
import uuid
from github import Github, Auth

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import HumanMessage, AIMessage
from langchain_groq import ChatGroq

app = FastAPI()

# Cloudflared handles HTTPS, so wildcard CORS is safe for your local tunneling
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize LLM. Make sure your GROQ_API_KEY environment variable is set.
llm = ChatGroq(model="qwen-2.5-coder-32b", temperature=0.1)

# --- 1. LangGraph State & Nodes ---
class AgencyState(TypedDict):
    messages: Annotated[List[HumanMessage | AIMessage], operator.add]
    project_plan: str
    is_approved: bool
    code_output: dict
    test_results: str
    github_token: str
    github_repo: str
    github_url: str

def project_manager(state: AgencyState):
    """Drafts the plan based on user prompt and uploaded file context."""
    prompt = f"""
    You are an elite Software Architecture Project Manager.
    User Request/Feedback: {state['messages'][-1].content}
    
    CRITICAL INSTRUCTIONS:
    1. Break the request down into a logical tech stack and numbered steps.
    2. Be concise. Do not write code. Only write the architecture plan.
    """
    response = llm.invoke(prompt)
    return {"project_plan": response.content, "is_approved": False}

def human_approval(state: AgencyState):
    """Dummy node. LangGraph will interrupt BEFORE this node executes."""
    pass

def coder_agent(state: AgencyState):
    """Generates the code as a JSON dictionary mapping filenames to code."""
    prompt = f"""
    You are a Senior Principal Software Engineer. 
    Write code based ONLY on this plan: {state['project_plan']}
    
    CRITICAL: Output ONLY a valid JSON object where keys are file paths (e.g., 'src/main.py') and values are the raw code string. 
    Do NOT wrap the JSON in markdown blocks.
    """
    response = llm.invoke(prompt)
    try:
        clean_json = response.content.replace("```json", "").replace("```", "").strip()
        code_files = json.loads(clean_json)
    except:
        code_files = {"error.txt": "AI failed to output valid JSON. Raw: " + response.content}
    return {"code_output": code_files}

def bug_finder_agent(state: AgencyState):
    """Audits the generated code."""
    code_str = json.dumps(state.get('code_output', {}), indent=2)
    prompt = f"""
    You are an elite QA and Security Auditor. Review this codebase:
    {code_str}
    
    If perfect, output 'PASS'. Otherwise, clearly list bugs. Do NOT rewrite the code.
    """
    response = llm.invoke(prompt)
    return {"test_results": response.content}

def optimizer_agent(state: AgencyState):
    """Fixes bugs and optimizes. Skips if code passed audit."""
    bugs = state.get('test_results', 'PASS')
    if "PASS" in bugs.upper() and len(bugs) < 10:
        return state
        
    code_str = json.dumps(state.get('code_output', {}), indent=2)
    prompt = f"""
    You are an elite Code Optimizer. Fix these bugs: {bugs}
    in this code: {code_str}
    
    Output ONLY a valid JSON object of the updated files. No markdown.
    """
    response = llm.invoke(prompt)
    try:
        clean_json = response.content.replace("```json", "").replace("```", "").strip()
        code_files = json.loads(clean_json)
        return {"code_output": code_files}
    except:
        return state

def delivery_agent(state: AgencyState):
    """Safely creates a new branch, commits the files, and opens a Pull Request."""
    token = state.get("github_token")
    repo_name = state.get("github_repo")
    code_output = state.get("code_output", {})
    
    if not token or not repo_name or "error.txt" in code_output:
        return {"github_url": None}
        
    try:
        g = Github(auth=Auth.Token(token))
        user = g.get_user()
        
        try:
            repo = user.get_repo(repo_name)
        except:
            repo = user.create_repo(name=repo_name, private=True, auto_init=True)
            
        # Create a unique branch name
        branch_name = "ai-update-" + str(uuid.uuid4())[:8]
        
        try:
            main_branch = repo.get_branch("main")
        except:
            main_branch = repo.get_branch("master")
            
        # Create the branch off of main
        repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_branch.commit.sha)
        
        # Commit files to the new branch
        for file_path, content in code_output.items():
            try:
                contents = repo.get_contents(file_path, ref=branch_name)
                repo.update_file(contents.path, "AI Agent Update", content, contents.sha, branch=branch_name)
            except:
                repo.create_file(file_path, "AI Agent Initial Commit", content, branch=branch_name)
                
        # Create Pull Request
        pr = repo.create_pull(title="AI Agent Code Update", body="Automated optimization and feature addition by AI Swarm.", head=branch_name, base=main_branch.name)
        return {"github_url": pr.html_url}
    except Exception as e:
        print(f"GitHub Error: {e}")
        return {"github_url": None}

def route_approval(state: AgencyState):
    """If human approved, proceed to coding. Otherwise, route back to Project Manager to revise."""
    return "coder_agent" if state.get("is_approved") else "project_manager"

# --- 2. Compile Graph ---
workflow = StateGraph(AgencyState)
workflow.add_node("project_manager", project_manager)
workflow.add_node("human_approval", human_approval)
workflow.add_node("coder_agent", coder_agent)
workflow.add_node("bug_finder_agent", bug_finder_agent)
workflow.add_node("optimizer_agent", optimizer_agent)
workflow.add_node("delivery_agent", delivery_agent)

workflow.add_edge(START, "project_manager")
workflow.add_edge("project_manager", "human_approval")
workflow.add_conditional_edges("human_approval", route_approval, {"coder_agent": "coder_agent", "project_manager": "project_manager"})
workflow.add_edge("coder_agent", "bug_finder_agent")
workflow.add_edge("bug_finder_agent", "optimizer_agent")
workflow.add_edge("optimizer_agent", "delivery_agent")
workflow.add_edge("delivery_agent", END)

# InMemorySaver allows the graph to pause and wait for the frontend
memory = InMemorySaver()
# Interrupting BEFORE the dummy node acts as our Human-in-the-Loop checkpoint
agent_app = workflow.compile(checkpointer=memory, interrupt_before=["human_approval"])

# --- 3. REST API Endpoints ---
@app.post("/api/chat")
async def chat_endpoint(
    thread_id: str = Form(...),
    action: str = Form(...), # Options: "start", "approve", "feedback"
    prompt: Optional[str] = Form(None),
    github_token: Optional[str] = Form(None),
    github_repo: Optional[str] = Form(None),
    files: List[UploadFile] = File(None)
):
    config = {"configurable": {"thread_id": thread_id}}
    
    # Process uploaded files
    context_data = ""
    if files:
        for f in files:
            content = await f.read()
            context_data += f"\n--- {f.filename} ---\n{content.decode('utf-8', errors='ignore')}\n"
            
    full_prompt = prompt + (f"\n\nAttached Context:\n{context_data}" if context_data else "")

    if action == "start":
        inputs = {
            "messages": [HumanMessage(content=full_prompt)],
            "github_token": github_token,
            "github_repo": github_repo
        }
        agent_app.invoke(inputs, config)
        
    elif action == "approve":
        agent_app.update_state(config, {"is_approved": True})
        agent_app.invoke(None, config) # Resumes the graph
        
    elif action == "feedback":
        agent_app.update_state(config, {
            "is_approved": False, 
            "messages": [HumanMessage(content=f"Feedback to change plan: {prompt}")]
        })
        agent_app.invoke(None, config) # Resumes graph, which routes back to PM

    # Return the current state to the frontend
    state = agent_app.get_state(config)
    is_paused = state.next == ('human_approval',)
    
    return {
        "is_paused": is_paused,
        "plan": state.values.get("project_plan", ""),
        "code_files": state.values.get("code_output", {}),
        "github_url": state.values.get("github_url", "")
    }

if __name__ == "__main__":
    import uvicorn
    # Start server
    uvicorn.run(app, host="0.0.0.0", port=8000)