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
        result["answer"] = self.answer_text(result.get("answer"))

        return {"reply": result}

    @staticmethod
    def answer_text(content):
        """
        Plain text of a model reply. With extended thinking the content is a
        list of blocks ({"type": "thinking"...}, {"type": "text"...}); only
        the text blocks are shown to visitors - thinking stays server-side.
        """
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text") or "")
            return "\n\n".join(part.strip() for part in parts if part.strip())

        return ""

    @staticmethod
    def token_usage(result, message):
        """LLM tokens used by a reply; estimated when the model reports none."""
        meta = result["reply"].get("meta_data")
        usage = getattr(meta, "usage_metadata", None) or {}
        total = usage.get("total_tokens") if isinstance(usage, dict) else None
        if isinstance(total, int) and total > 0:
            return total
        return (len(message) + len(result["reply"].get("answer") or "")) // 4
