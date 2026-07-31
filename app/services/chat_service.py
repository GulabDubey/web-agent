from app.core.exceptions import AppException
from app.graph.chat_graph import graph

class ChatService:

    async def generate_reply(self, message):

        if not message:
            raise AppException("Message can't be empty", 400)

        state = {
            "message": message,
            "route": "",
            "answer": "",
            "meta_data": None
        }

        result = graph.invoke(state)

        return {"reply": result}