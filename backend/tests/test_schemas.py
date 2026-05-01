# backend/tests/test_schemas.py
import pytest
from pydantic import ValidationError
from app.models.schemas import (
    UserCreate,
    LoginRequest,
    RAGQuery,
    ClassifyInput,
    ClassifyByNameInput,
    LiveConditionsInput,
    DestinationFeatures,
    TripPlan,
    Token,
)

class TestUserCreate:
    def test_valid_user(self):
        u = UserCreate(email="a@b.com", password="12345678")
        assert u.email == "a@b.com"

    def test_password_too_short(self):
        with pytest.raises(ValidationError):
            UserCreate(email="a@b.com", password="123")

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            UserCreate(email="notanemail", password="12345678")

class TestLoginRequest:
    def test_valid_login(self):
        lr = LoginRequest(email="a@b.com", password="mypassword")
        assert lr.email == "a@b.com"

    def test_password_too_long(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="a@b.com", password="a"*73)

class TestRAGQuery:
    def test_valid(self):
        q = RAGQuery(query="best hiking")
        assert q.query == "best hiking"
        # top_k was removed from the model; the tool internally uses 3

class TestClassifyInput:
    def test_valid(self):
        features = DestinationFeatures(
            continent="Europe",
            avg_temperature=20.0,
            cost_index=50,
            hiking_score=5.0,
            beach_score=3.0,
            culture_score=8.0,
            family_friendly_score=5.0,
            tourist_density=5.0,
        )
        inp = ClassifyInput(features=features)
        assert inp.features.continent == "Europe"

    def test_invalid_features_type(self):
        with pytest.raises(ValidationError):
            ClassifyInput(features="not a dict")

class TestClassifyByNameInput:
    def test_valid(self):
        inp = ClassifyByNameInput(destination="Paris")
        assert inp.destination == "Paris"

    def test_empty_destination(self):
        with pytest.raises(ValidationError):
            ClassifyByNameInput(destination="")

class TestLiveConditionsInput:
    def test_valid(self):
        inp = LiveConditionsInput(city="Paris")
        assert inp.city == "Paris"

    # empty city is allowed by the model, so no ValidationError
    def test_empty_city_accepted(self):
        inp = LiveConditionsInput(city="")
        assert inp.city == ""

class TestTripPlan:
    def test_valid_trip_plan(self):
        plan = TripPlan(
            user_id=1,
            query="test",
            plan="A great trip",
            user_email="a@b.com",
        )
        assert plan.user_id == 1

class TestToken:
    def test_token_model(self):
        token = Token(access_token="abc", token_type="bearer")
        assert token.token_type == "bearer"