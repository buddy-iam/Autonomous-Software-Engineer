from typing import TypedDict, List, Annotated, Dict
import operator
from langchain_core.messages import HumanMessage, AIMessage

class AgencyState(TypedDict):
    messages: Annotated[List[HumanMessage | AIMessage], operator.add]
    is_build_request: bool
    chat_response: str
    project_plan: str
    research_context: str
    is_approved: bool
    
    # NEW: Interactive File Queue State
    file_queue: List[str]          # Files left to build (e.g., ["index.html", "style.css"])
    code_files: Dict[str, str]     # Accumulated built files to send to the frontend
    
    github_token: str
    github_repo: str
    github_url: str