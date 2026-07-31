from langchain_core.prompts import ChatPromptTemplate
from app.llm.anthropic import get_llm

class SQLGenerator:

    def __init__(self):
        self.llm = get_llm()

        self.prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """
You are an expert MySQL developer.

Generate ONLY a valid MySQL query.

Rules:
- Return SQL only.
- No markdown.
- No explanation.
- Use only the provided schema.
- Never invent tables or columns.
- Prefer SELECT statements.
- Add LIMIT 100 if appropriate.

Schema:
{schema}
"""
            ),
            ("human", "{message}")
        ])

    def generate(self, message: str, schema: str) -> str:

        chain = self.prompt | self.llm

        response = chain.invoke({
            "message": message,
            "schema": schema
        })

        return response.content.strip()