from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from state import AgencyState
import agents

def route_intent(state: AgencyState):
    return "project_manager" if state.get("is_build_request") else "chat_node"

def route_after_approval(state: AgencyState):
    if state.get("is_approved"):
        if state.get("edit_queue"):
            return "edit_agent"
        if state.get("file_queue"):
            return "coder_agent"
        return "delivery_agent"
    return "qa_agent"

def route_after_generation(state: AgencyState):
    if state.get("edit_queue") or state.get("file_queue"):
        return "human_approval" 
    return "delivery_agent"     

# NEW: Allow qa_agent to re-trigger project_manager if user wants a redesign
def route_after_qa(state: AgencyState):
    if state.get("is_replan"):
        return "project_manager"
    return "human_approval"

def chat_node(state: AgencyState):
    return {"chat_response": state.get("chat_response", "Hello! How can I help you?")}

def build_graph():
    workflow = StateGraph(AgencyState)
    
    workflow.add_node("intent_classifier", agents.intent_classifier)
    workflow.add_node("chat_node", chat_node)
    workflow.add_node("project_manager", agents.project_manager)
    workflow.add_node("human_approval", agents.human_approval)
    workflow.add_node("coder_agent", agents.coder_agent)
    workflow.add_node("edit_agent", agents.edit_agent)
    workflow.add_node("qa_agent", agents.qa_agent)
    workflow.add_node("delivery_agent", agents.delivery_agent)

    workflow.add_edge(START, "intent_classifier")
    
    workflow.add_conditional_edges("intent_classifier", route_intent, {
        "project_manager": "project_manager", 
        "chat_node": "chat_node"
    })
    
    workflow.add_edge("chat_node", END)
    workflow.add_edge("project_manager", "human_approval")
    
    workflow.add_conditional_edges("human_approval", route_after_approval, {
        "edit_agent": "edit_agent",
        "coder_agent": "coder_agent",
        "qa_agent": "qa_agent",
        "delivery_agent": "delivery_agent"
    })
    
    workflow.add_conditional_edges("coder_agent", route_after_generation, {
        "human_approval": "human_approval",
        "delivery_agent": "delivery_agent"
    })
    
    workflow.add_conditional_edges("edit_agent", route_after_generation, {
        "human_approval": "human_approval",
        "delivery_agent": "delivery_agent"
    })
    
    # Conditional edge: QA can either wait for human approval or re-plan
    workflow.add_conditional_edges("qa_agent", route_after_qa, {
        "project_manager": "project_manager",
        "human_approval": "human_approval"
    })
    
    workflow.add_edge("delivery_agent", END)

    memory = InMemorySaver()
    return workflow.compile(checkpointer=memory, interrupt_before=["human_approval"])

agent_app = build_graph()