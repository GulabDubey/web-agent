SYSTEM_PROMPT = """
You are a router.

If the user asks about:

- SQL
- MySQL
- Database
- Table
- Column
- Record
- Data
- CRUD
- Count
- Insert
- Update
- Delete

Return only:

DATABASE

Otherwise return:

GENERAL

Return one word only.
"""

from app.llm.anthropic import get_llm

def router_agent(state):
    message = state["message"]
    
    return { **state,"route": "KNOWLEDGE"}

    llm = get_llm()
    response = llm.invoke([
        ("system", SYSTEM_PROMPT),
        ("human", message)
    ])

    route = response.content.strip().upper()

    return {
        **state,
        "route": route
    }