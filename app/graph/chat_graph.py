from langgraph.graph import StateGraph, END
from app.graph.chat_state import ChatGraphState

from app.agents.router_agent import router_agent
from app.agents.general_agent import general_agent
from app.agents.database_agent import database_agent
from app.agents.knowledge_agent import KnowledgeAgent

from app.core.dependencies import get_vector_service
from app.llm.anthropic import get_llm

knowledge_agent = KnowledgeAgent(
    vector_service=get_vector_service(),
    llm=get_llm()
)

builder = StateGraph(ChatGraphState)

builder.add_node("router", router_agent)
builder.add_node("general", general_agent)
builder.add_node("database", database_agent)
builder.add_node("knowledge", knowledge_agent)

builder.set_entry_point("router")


def route(state):
    return state["route"]


builder.add_conditional_edges(
    "router",
    route,
    {
        "GENERAL": "general",
        "DATABASE": "database",
        "KNOWLEDGE": "knowledge",
    },
)

builder.add_edge("general", END)
builder.add_edge("database", END)
builder.add_edge("knowledge", END)

graph = builder.compile()