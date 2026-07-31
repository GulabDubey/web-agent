from pathlib import Path

import fitz  # PyMuPDF
import pandas as pd
from docx import Document


class FileParserService:
    """
    Extract text from supported document types.

    Supported:
    - PDF
    - DOCX
    - TXT
    - CSV
    """

    @staticmethod
    def extract_text(file_path: str) -> list[dict]:
        """
        Returns:
        [
            {
                "source": "company_profile.pdf",
                "file_name": "company_profile.pdf",
                "file_type": "pdf",
                "page": 1,
                "content": "..."
            }
        ]
        """

        extension = Path(file_path).suffix.lower()

        parsers = {
            ".pdf": FileParserService._extract_pdf,
            ".docx": FileParserService._extract_docx,
            ".txt": FileParserService._extract_txt,
            ".csv": FileParserService._extract_csv,
        }

        parser = parsers.get(extension)

        if parser is None:
            raise ValueError(f"Unsupported file type: {extension}")

        return parser(file_path)

    @staticmethod
    def _metadata(
        file_path: str,
        page: int,
        content: str,
    ) -> dict:
        path = Path(file_path)

        return {
            "source": path.name,
            "file_name": path.name,
            "file_type": path.suffix.lower().replace(".", ""),
            "page": page,
            "content": content,
        }

    @staticmethod
    def _extract_pdf(file_path: str) -> list[dict]:
        document = fitz.open(file_path)

        pages = []

        try:
            for page_number, page in enumerate(document, start=1):
                text = page.get_text("text").strip()

                if text:
                    pages.append(
                        FileParserService._metadata(
                            file_path=file_path,
                            page=page_number,
                            content=text,
                        )
                    )

        finally:
            document.close()

        return pages

    @staticmethod
    def _extract_docx(file_path: str) -> list[dict]:
        document = Document(file_path)

        text = "\n".join(
            paragraph.text.strip()
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        )

        return [
            FileParserService._metadata(
                file_path=file_path,
                page=1,
                content=text,
            )
        ]

    @staticmethod
    def _extract_txt(file_path: str) -> list[dict]:
        with open(file_path, "r", encoding="utf-8") as file:
            text = file.read().strip()

        return [
            FileParserService._metadata(
                file_path=file_path,
                page=1,
                content=text,
            )
        ]

    @staticmethod
    def _extract_csv(file_path: str) -> list[dict]:
        dataframe = pd.read_csv(file_path)

        text = dataframe.to_string(index=False)

        return [
            FileParserService._metadata(
                file_path=file_path,
                page=1,
                content=text,
            )
        ]