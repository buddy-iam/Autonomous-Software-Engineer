from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from langchain_core.messages import HumanMessage
from graph import agent_app

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class FileUpdateRequest(BaseModel):
    thread_id: str
    filename: str
    content: str

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
    
    context_data = ""
    if files:
        for f in files:
            content = await f.read()
            context_data += f"\n--- {f.filename} ---\n{content.decode('utf-8', errors='ignore')}\n"
            
    full_prompt = (prompt or "") + (f"\n\nAttached Context:\n{context_data}" if context_data else "")
    prompt_clean = (prompt or "").strip().lower()

    approval_keywords = ["approve", "continue", "next", "proceed", "build next", "yes", "go ahead", "y", "ok"]
    is_approval_intent = action == "approve" or prompt_clean in approval_keywords

    state = agent_app.get_state(config)
    is_paused = len(state.next) > 0 and state.next[0] == 'human_approval'

    if action == "start":
        inputs = {
            "messages": [HumanMessage(content=full_prompt)],
            "github_token": github_token,
            "github_repo": github_repo
        }
        agent_app.invoke(inputs, config)
        
    elif is_paused and is_approval_intent:
        agent_app.update_state(config, {"is_approved": True}, as_node="human_approval")
        agent_app.invoke(None, config)
        
    elif is_paused:
        agent_app.update_state(config, {
            "is_approved": False,
            "messages": [HumanMessage(content=full_prompt or "")]
        }, as_node="human_approval")
        agent_app.invoke(None, config)
        
    else:
        inputs = {
            "messages": [HumanMessage(content=full_prompt)],
            "github_token": github_token,
            "github_repo": github_repo
        }
        agent_app.invoke(inputs, config)

    state = agent_app.get_state(config)
    is_paused = len(state.next) > 0 and state.next[0] == 'human_approval'
    
    return {
        "is_paused": is_paused,
        "chat_response": state.values.get("chat_response", ""),
        "plan": "",          
        "code_files": {},    
        "github_url": state.values.get("github_url", "")
    }

@app.get("/api/workspace/{thread_id}")
async def get_workspace(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    state = agent_app.get_state(config)
    
    return {
        "code_files": state.values.get("code_files", {}),
        "file_queue": state.values.get("file_queue", []),
        "edit_queue": state.values.get("edit_queue", [])
    }

@app.post("/api/workspace/save")
async def save_file(request: FileUpdateRequest):
    config = {"configurable": {"thread_id": request.thread_id}}
    state = agent_app.get_state(config)
    
    current_files = state.values.get("code_files", {})
    current_files[request.filename] = request.content
    
    agent_app.update_state(
        config, 
        {"code_files": current_files}, 
        as_node="human_approval"
    )
    
    return {"status": "success", "message": f"Updated {request.filename}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)