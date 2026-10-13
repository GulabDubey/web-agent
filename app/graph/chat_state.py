from typing import TypedDict

class ChatGraphState(TypedDict):
    message: str
    # Knowledge collection of the verified website (tenant isolation).
    collection: str
    route: str
    answer: str