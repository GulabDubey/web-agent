"""
Embed crawled pages with Voyage AI and upload them to Qdrant.

Run locally (uses .env: VOYAGE_API_KEY, VOYAGE_MODEL, EMBEDDING_DIMENSION,
QDRANT_URL / QDRANT_API_KEY):

    python -m scripts.ingest_folder storage/websites/Bydo Bydo --recreate

The collection name must match websites_website.collection_name in Django.
"""
import argparse
import sys
from pathlib import Path

from app.core.dependencies import get_vector_service

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EXTENSIONS = {".txt", ".md"}


def split_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Fixed-size chunks with overlap, preferring to break at a newline or space."""
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            cut = max(text.rfind("\n", start + size // 2, end), text.rfind(" ", start + size // 2, end))
            if cut > start:
                end = cut
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def load_chunks(folder):
    documents = []
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() not in EXTENSIONS or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").strip()
        for index, chunk in enumerate(split_text(text)):
            documents.append({
                "content": chunk,
                "source": path.name,
                "file_name": path.name,
                "page": 1,
                "metadata": {"chunk_index": index},
            })
    return documents


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path, help="Folder of crawled .txt/.md pages")
    parser.add_argument("collection", help="Qdrant collection name (Django collection_name)")
    parser.add_argument("--recreate", action="store_true", help="Delete the collection first")
    args = parser.parse_args()

    if not args.folder.is_dir():
        sys.exit(f"Not a folder: {args.folder}")

    documents = load_chunks(args.folder)
    if not documents:
        sys.exit(f"No .txt/.md content found in {args.folder}")

    vector_service = get_vector_service()
    client = vector_service.repository.client

    if args.recreate and client.collection_exists(args.collection):
        client.delete_collection(args.collection)

    vector_service.create_collection(args.collection)
    vector_service.add_documents(args.collection, documents)

    total = vector_service.total_documents(args.collection).count
    print(f"Uploaded {len(documents)} chunks to '{args.collection}' ({total} points total).")


if __name__ == "__main__":
    main()
