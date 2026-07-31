from app.llm.anthropic import get_llm

def general_agent(state):

    message = state["message"]

    llm = get_llm()
    response = llm.invoke(message)

    return {
        **state,
        "answer": response.content
    }