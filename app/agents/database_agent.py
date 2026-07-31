# agents/database_agent.py

from app.tools.database_tool import database_tool

def database_agent(state):

    message = state["message"]

    answer = database_tool(message)

    return {
        **state,
        "answer": answer
    }