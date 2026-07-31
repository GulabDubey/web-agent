from app.services.vector_service import VectorService

class KnowledgeAgent:

    def __init__(self, vector_service: VectorService, llm):
        self.vector_service = vector_service
        self.llm = llm

    def __call__(self, state):
        message = state["message"]

        result = self.vector_service.similarity_search(
            "companiesnext",
            message
        )

        context = "\n\n".join(d["content"] for d in result)

        prompt = f"""
        Answer the question using only the context below.
        If the answer isn't present, say you don't have that information and ask the user to contact support.
        Do not invent information or mention the context.

        Format the answer in Markdown so it is easy to scan:
        - Break the answer into bullet points (use "-") instead of long paragraphs whenever it lists more than one item, step, or fact.
        - Use **bold** for key terms, names, and numbers the user should notice first.
        - Use *italic* for secondary emphasis or clarifying notes.
        - Use <u>underline</u> HTML tags to underline anything the user must not miss (e.g. deadlines, requirements).
        - Keep the tone concise and professional; do not overuse formatting on every word.

        Context:
        {context}

        Question:
        {message}

        Answer:
        """

        response = self.llm.invoke(prompt)

        return {
            **state,
            "answer": response.content,
            "meta_data": response
        }