from dataclasses import dataclass, field


@dataclass
class ChatSession:
    current_question: int = 0
    answers: dict = field(
        default_factory=dict
    )


class SessionService:

    def __init__(self):
        self.sessions = {}

    def get(
        self,
        session_id: str
    ) -> ChatSession:

        if session_id not in self.sessions:
            self.sessions[session_id] = ChatSession()

        return self.sessions[session_id]


    def reset(
        self,
        session_id: str
    ):
        self.sessions.pop(
            session_id,
            None
        )


session_service = SessionService()