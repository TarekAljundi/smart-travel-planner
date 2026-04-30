# backend/tests/test_schemas.py
import pytest
from pydantic import ValidationError
from app.models.schemas import RAGQuery, ClassifyInput, LiveConditionsInput

def test_rag_query_valid():
    q = RAGQuery(query="best hiking spots", top_k=5)
    assert q.top_k == 5

def test_classify_input_invalid():
    with pytest.raises(ValidationError):
        ClassifyInput(features="not a dict")

def test_live_conditions_empty_city():
    with pytest.raises(ValidationError):
        LiveConditionsInput(city="")