from typing import TypedDict

class ChatGraphState(TypedDict):
    message: str
    route: str
    answer: str