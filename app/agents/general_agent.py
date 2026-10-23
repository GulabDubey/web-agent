from app.llm.anthropic import get_llm

def general_agent(state):

    message = state["message"]

    llm = state.get("llm") or get_llm()
    response = llm.invoke(message)

    return {
        **state,
        "answer": response.content
    }