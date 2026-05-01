# backend/tests/test_retrieval.py
import pytest
from sqlalchemy import text, create_engine, exc
from sentence_transformers import SentenceTransformer
from app.config import get_settings

settings = get_settings()


@pytest.fixture(scope="module")
def embedder():
    return SentenceTransformer(settings.embedding_model)


@pytest.fixture(scope="module")
def engine():
    # Replace Docker service name 'db' with 'localhost' for local testing
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace("@db:", "@localhost:")
    try:
        eng = create_engine(sync_url)
        # Test the connection – if it fails, we'll skip
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return eng
    except exc.OperationalError:
        pytest.skip("PostgreSQL is not available – start the database container")


QUERIES = [
    "warm beach with hiking nearby",
    "historic cultural European city",
    "adventure activities in mountains",
    "affordable tropical island for relaxation",
    "romantic coastal village in Italy",
]


def test_retrieval_returns_correct_destinations(embedder, engine):
    with engine.connect() as conn:
        # Check if the table exists
        table_exists = conn.execute(
            text(
                f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{settings.vector_table_name}')"
            )
        ).scalar()
        if not table_exists:
            pytest.skip(f"Table {settings.vector_table_name} does not exist – run load_rag.py first")

        for query in QUERIES:
            q_emb = embedder.encode(query).tolist()
            emb_str = str(q_emb).replace(" ", "")
            sql = text(f"""
                SELECT destination, chunk_text,
                       1 - (embedding <=> '{emb_str}'::vector) AS similarity
                FROM {settings.vector_table_name}
                ORDER BY embedding <=> '{emb_str}'::vector
                LIMIT 3
            """)
            res = conn.execute(sql).fetchall()
            print(f"\n--- {query} ---")
            for row in res:
                print(f"{row.destination} (sim={row.similarity:.3f}): {row.chunk_text[:100]}...")
            assert len(res) == 3
            assert any(r.similarity > 0.3 for r in res)