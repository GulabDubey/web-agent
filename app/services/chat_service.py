from app.core.exceptions import AppException
from app.graph.chat_graph import graph

class ChatService:

    async def generate_reply(self, message, collection):

        if not message:
            raise AppException("Message can't be empty", 400)

        if not collection:
            raise AppException("No knowledge base is configured for this website.", 403)

        state = {
            "message": message,
            "collection": collection,
            "route": "",
            "answer": "",
            "meta_data": None
        }

        result = graph.invoke(state)

        return {"reply": result}

    @staticmethod
    def token_usage(result, message):
        """LLM tokens used by a reply; estimated when the model reports none."""
        meta = result["reply"].get("meta_data")
        usage = getattr(meta, "usage_metadata", None) or {}
        total = usage.get("total_tokens") if isinstance(usage, dict) else None
        if isinstance(total, int) and total > 0:
            return total
        return (len(message) + len(result["reply"].get("answer") or "")) // 4
