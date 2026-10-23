from typing import Any, TypedDict

class ChatGraphState(TypedDict):
    message: str
    # Knowledge collection of the verified website (tenant isolation).
    collection: str
    # Chat model for this website's configured provider (from Django).
    llm: Any
    route: str
    answer: str