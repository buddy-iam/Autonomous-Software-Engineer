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
    is_replan: bool                # Signals a reset/re-plan request
    
    file_queue: List[str]          
    edit_queue: List[str]          
    code_files: Dict[str, str]     
    
    github_token: str
    github_repo: str
    github_url: str