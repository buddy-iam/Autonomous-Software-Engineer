from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from state import AgencyState
import agents

def route_intent(state: AgencyState):
    return "project_manager" if state.get("is_build_request") else END

def route_approval(state: AgencyState):
    return "coder_agent" if state.get("is_approved") else "project_manager"

def build_graph():
    workflow = StateGraph(AgencyState)
    
    workflow.add_node("intent_classifier", agents.intent_classifier)
    workflow.add_node("project_manager", agents.project_manager)
    workflow.add_node("human_approval", agents.human_approval)
    workflow.add_node("coder_agent", agents.coder_agent)
    workflow.add_node("bug_finder_agent", agents.bug_finder_agent)
    workflow.add_node("optimizer_agent", agents.optimizer_agent)
    workflow.add_node("delivery_agent", agents.delivery_agent)

    workflow.add_edge(START, "intent_classifier")
    workflow.add_conditional_edges("intent_classifier", route_intent, {"project_manager": "project_manager", END: END})
    workflow.add_edge("project_manager", "human_approval")
    workflow.add_conditional_edges("human_approval", route_approval, {"coder_agent": "coder_agent", "project_manager": "project_manager"})
    workflow.add_edge("coder_agent", "bug_finder_agent")
    workflow.add_edge("bug_finder_agent", "optimizer_agent")
    workflow.add_edge("optimizer_agent", "delivery_agent")
    workflow.add_edge("delivery_agent", END)

    memory = InMemorySaver()
    return workflow.compile(checkpointer=memory, interrupt_before=["human_approval"])

agent_app = build_graph()