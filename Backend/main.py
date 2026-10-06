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
    prompt_clean = (prompt or "").strip().lower()

    approval_keywords = ["approve", "continue", "next", "proceed", "build next", "yes", "go ahead", "y", "ok"]
    is_approval_intent = action == "approve" or prompt_clean in approval_keywords

    if action == "start":
        inputs = {
            "messages": [HumanMessage(content=full_prompt)],
            "github_token": github_token,
            "github_repo": github_repo
        }
        agent_app.invoke(inputs, config)
    elif is_approval_intent:
        agent_app.update_state(config, {"is_approved": True})
        agent_app.invoke(None, config)
    else:
        agent_app.update_state(config, {
            "is_approved": False,
            "messages": [HumanMessage(content=full_prompt or "")]
        })
        agent_app.invoke(None, config)

    state = agent_app.get_state(config)
    is_paused = len(state.next) > 0 and state.next[0] == 'human_approval'
    
    return {
        "is_paused": is_paused,
        "chat_response": state.values.get("chat_response", ""),
        # Suppress these variables so the frontend doesn't print duplicates
        "plan": "",          
        "code_files": {},    
        "github_url": state.values.get("github_url", "")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)