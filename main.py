from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Annotated, TypedDict
import operator
import json
import uuid
import re
from github import Github, Auth
from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import HumanMessage, AIMessage
from langchain_groq import ChatGroq

app = FastAPI()

# Cloudflared tunneling handles secure routing, so wildcard CORS is required
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize LLM (Ensure GROQ_API_KEY environment variable is set)
load_dotenv()
llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0.1)

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

def clean_json_output(content: str) -> dict:
    """Helper to safely extract JSON from LLM outputs even if wrapped in markdown."""
    try:
        # Strip markdown code blocks if present
        cleaned = re.sub(r'```(?:json)?', '', content).strip()
        return json.loads(cleaned)
    except Exception:
        return {"error.txt": f"AI failed to output valid JSON. Raw output:\n{content}"}

def project_manager(state: AgencyState):
    """Drafts the architecture plan based on the user's prompt and files."""
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
    """Dummy node. LangGraph interrupts BEFORE this node executes to wait for user input."""
    pass

def coder_agent(state: AgencyState):
    """Generates the code as a JSON dictionary mapping filenames to code."""
    prompt = f"""
    You are a Senior Principal Software Engineer. 
    Write code based ONLY on this plan: {state['project_plan']}
    
    CRITICAL: Output ONLY a valid JSON object where keys are file paths (e.g., 'src/main.js') and values are the raw code string. 
    Do NOT wrap the JSON in markdown blocks. No explanations.
    """
    response = llm.invoke(prompt)
    return {"code_output": clean_json_output(response.content)}

def bug_finder_agent(state: AgencyState):
    """Audits the generated code for errors or edge cases."""
    if "error.txt" in state.get('code_output', {}):
        return {"test_results": "Syntax generation failed."}
        
    code_str = json.dumps(state.get('code_output', {}), indent=2)
    prompt = f"""
    You are an elite QA and Security Auditor. Review this codebase:
    {code_str}
    
    If perfect, output 'PASS'. Otherwise, clearly list bugs. Do NOT rewrite the code.
    """
    response = llm.invoke(prompt)
    return {"test_results": response.content}

def optimizer_agent(state: AgencyState):
    """Fixes bugs based on the QA report."""
    bugs = state.get('test_results', 'PASS')
    if "PASS" in bugs.upper() and len(bugs) < 10:
        return state # No optimization needed
        
    code_str = json.dumps(state.get('code_output', {}), indent=2)
    prompt = f"""
    You are an elite Code Optimizer. Fix these bugs: {bugs}
    in this code: {code_str}
    
    Output ONLY a valid JSON object of the updated files. No markdown.
    """
    response = llm.invoke(prompt)
    optimized = clean_json_output(response.content)
    if "error.txt" not in optimized:
        return {"code_output": optimized}
    return state

def delivery_agent(state: AgencyState):
    """Autonomously branches, commits, and creates a GitHub PR if credentials exist."""
    token = state.get("github_token")
    repo_name = state.get("github_repo")
    code_output = state.get("code_output", {})
    
    if not token or not repo_name or "error.txt" in code_output:
        return {"github_url": None}
        
    try:
        g = Github(auth=Auth.Token(token))
        user = g.get_user()
        
        # Get or create repo
        try:
            repo = user.get_repo(repo_name)
        except:
            repo = user.create_repo(name=repo_name, private=True, auto_init=True)
            
        # Create a unique branch name
        branch_name = f"ai-update-{str(uuid.uuid4())[:8]}"
        
        try:
            main_branch = repo.get_branch("main")
        except:
            main_branch = repo.get_branch("master")
            
        repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=main_branch.commit.sha)
        
        # Commit files
        for file_path, content in code_output.items():
            try:
                contents = repo.get_contents(file_path, ref=branch_name)
                repo.update_file(contents.path, "AI Agent Update", content, contents.sha, branch=branch_name)
            except:
                repo.create_file(file_path, "AI Agent Initial Commit", content, branch=branch_name)
                
        # Create PR
        pr = repo.create_pull(
            title="AI Swarm Code Update", 
            body="Automated optimization and feature addition by Autonomous Agency.", 
            head=branch_name, 
            base=main_branch.name
        )
        return {"github_url": pr.html_url}
    except Exception as e:
        print(f"GitHub Execution Error: {e}")
        return {"github_url": None}

def route_approval(state: AgencyState):
    """Conditional router based on the Human-in-the-Loop checkpoint."""
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

memory = InMemorySaver()
# Interrupting BEFORE human_approval pauses the graph so the UI can prompt the user
agent_app = workflow.compile(checkpointer=memory, interrupt_before=["human_approval"])

# --- 3. REST API Endpoint ---
@app.post("/api/chat")
async def chat_endpoint(
    thread_id: str = Form(...),
    action: str = Form(...), 
    prompt: Optional[str] = Form(None),
    github_token: Optional[str] = Form(None),
    github_repo: Optional[str] = Form(None),
    files: List[UploadFile] = File(None)
):
    config = {"configurable": {"thread_id": thread_id}}
    
    # Process uploaded files into readable text context
    context_data = ""
    if files:
        for f in files:
            content = await f.read()
            context_data += f"\n--- {f.filename} ---\n{content.decode('utf-8', errors='ignore')}\n"
            
    full_prompt = (prompt or "") + (f"\n\nAttached Context:\n{context_data}" if context_data else "")

    if action == "start":
        inputs = {
            "messages": [HumanMessage(content=full_prompt)],
            "github_token": github_token,
            "github_repo": github_repo
        }
        agent_app.invoke(inputs, config)
        
    elif action == "approve":
        agent_app.update_state(config, {"is_approved": True})
        agent_app.invoke(None, config) 
        
    elif action == "feedback":
        agent_app.update_state(config, {
            "is_approved": False, 
            "messages": [HumanMessage(content=f"Feedback to revise plan: {prompt}")]
        })
        agent_app.invoke(None, config)

    # Retrieve current state to send back to the frontend
    state = agent_app.get_state(config)
    
    # Check if the graph is currently halted at the approval gate
    is_paused = len(state.next) > 0 and state.next[0] == 'human_approval'
    
    return {
        "is_paused": is_paused,
        "plan": state.values.get("project_plan", ""),
        "code_files": state.values.get("code_output", {}),
        "github_url": state.values.get("github_url", "")
    }