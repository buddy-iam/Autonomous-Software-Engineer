from typing import TypedDict, List, Annotated
import operator
from langchain_core.messages import HumanMessage, AIMessage

class AgencyState(TypedDict):
    messages: Annotated[List[HumanMessage | AIMessage], operator.add]
    is_build_request: bool
    chat_response: str
    project_plan: str
    is_approved: bool
    code_output: dict
    test_results: str
    github_token: str
    github_repo: str
    github_url: str