# backend/scripts/load_rag.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import os
from sentence_transformers import SentenceTransformer
from sqlalchemy import text, create_engine
from app.config import get_settings

settings = get_settings()


def split_text_recursive(text: str, chunk_size=500, chunk_overlap=50) -> list:
    separators = ["\n\n", "\n", ". ", " ", ""]
    for sep in separators:
        if sep == "":
            chunks = []
            for i in range(0, len(text), chunk_size - chunk_overlap):
                chunk = text[i:i + chunk_size]
                if chunk:
                    chunks.append(chunk)
            return chunks
        if sep in text:
            parts = text.split(sep)
            chunks = []
            for part in parts:
                if len(part) <= chunk_size:
                    if part.strip():
                        chunks.append(part)
                else:
                    chunks.extend(split_text_recursive(part, chunk_size, chunk_overlap))
            return chunks
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - chunk_overlap)]


async def main():
    embedder = SentenceTransformer(settings.embedding_model)
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
    engine = create_engine(sync_url)

    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {settings.vector_table_name} (
                id SERIAL PRIMARY KEY,
                destination TEXT NOT NULL,
                chunk_text TEXT NOT NULL,
                embedding vector({settings.embedding_dim})
            );
        """))
        conn.commit()

        docs_dir = settings.knowledge_base_dir
        if not os.path.exists(docs_dir):
            print(f"Directory '{docs_dir}' not found. Create it with subfolders for each destination.")
            return

        for dest_name in os.listdir(docs_dir):
            dest_path = os.path.join(docs_dir, dest_name)
            if not os.path.isdir(dest_path):
                continue
            print(f"Processing {dest_name}...")
            total_chunks = 0
            for filename in os.listdir(dest_path):
                if not filename.endswith(".txt"):
                    continue
                filepath = os.path.join(dest_path, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                chunks = split_text_recursive(content)
                for chunk in chunks:
                    embedding = embedder.encode(chunk).tolist()
                    conn.execute(
                        text(f"INSERT INTO {settings.vector_table_name} (destination, chunk_text, embedding) VALUES (:dest, :text, :emb)"),
                        {"dest": dest_name, "text": chunk, "emb": embedding},
                    )
                total_chunks += len(chunks)
            conn.commit()
            print(f"  Loaded {total_chunks} chunks for {dest_name}")
    print("Knowledge base loaded successfully.")

if __name__ == "__main__":
    asyncio.run(main())