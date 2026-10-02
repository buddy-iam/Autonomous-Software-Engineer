from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
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

    state = agent_app.get_state(config)
    is_paused = len(state.next) > 0 and state.next[0] == 'human_approval'
    
    return {
        "is_paused": is_paused,
        "chat_response": state.values.get("chat_response", ""),
        "plan": state.values.get("project_plan", ""),
        "code_files": state.values.get("code_output", {}),
        "github_url": state.values.get("github_url", "")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)