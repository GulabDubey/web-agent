from langchain_text_splitters import RecursiveCharacterTextSplitter


class TextSplitterService:
    _splitter = None

    def __init__(self):
        if self.__class__._splitter is None:
            print("Loading text splitter...")

            self.__class__._splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )

        self.splitter = self.__class__._splitter

    def split_text(self, pages: list[dict]) -> list[dict]:
        """
        Input:
        [
            {
                "source": "company_profile.pdf",
                "file_name": "company_profile.pdf",
                "file_type": "pdf",
                "page": 1,
                "content": "..."
            }
        ]

        Output:
        [
            {
                "content": "...",
                "chunk_index": 0,
                "page": 1,
                "source": "company_profile.pdf",
                "file_name": "company_profile.pdf",
                "file_type": "pdf"
            }
        ]
        """

        chunks = []

        for page in pages:

            texts = self.splitter.split_text(page["content"])

            for chunk_index, chunk in enumerate(texts):

                chunks.append({
                    "content": chunk,
                    "chunk_index": chunk_index,
                    "page": page["page"],
                    "source": page["source"],
                    "file_name": page["file_name"],
                    "file_type": page["file_type"],
                })

        return chunks