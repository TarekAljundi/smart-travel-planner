# backend/app/tools/rag_search.py
from sqlalchemy import text
from app.models.schemas import RAGQuery, RAGResult
from app.config import get_settings
from typing import List

settings = get_settings()


async def rag_search(query: RAGQuery, session, embedder, top_k: int = 3) -> List[RAGResult]:
    embedding = embedder.encode(query.query).tolist()
    emb_str = str(embedding).replace(" ", "")

    sql = text(f"""
        SELECT destination, chunk_text,
               1 - (embedding <=> '{emb_str}'::vector) AS similarity
        FROM {settings.vector_table_name}
        ORDER BY embedding <=> '{emb_str}'::vector
        LIMIT :k
    """)
    result = await session.execute(sql, {"k": top_k})
    rows = result.fetchall()

    return [
        RAGResult(
            text=row.chunk_text[:200] + ("..." if len(row.chunk_text) > 200 else ""),
            destination=row.destination,
            relevance=float(row.similarity),
        )
        for row in rows
    ]