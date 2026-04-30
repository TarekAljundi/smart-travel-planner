# backend/app/models/schemas.py
from pydantic import BaseModel, Field, EmailStr
from typing import Literal, List, Optional
from app.config import get_settings

settings = get_settings()

# ---------- Auth ----------
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)

class Token(BaseModel):
    access_token: str
    token_type: str

# ---------- Trip Request ----------
class TripRequest(BaseModel):
    query: str = Field(..., min_length=10)

# ---------- RAG Tool ----------
class RAGQuery(BaseModel):
    query: str

class RAGResult(BaseModel):
    text: str
    destination: str
    relevance: float



# ---------- Live Conditions Tool ----------
class ToolError(BaseModel):
    error: str
    retryable: bool

class LiveConditionsInput(BaseModel):
    city: str

class LiveConditionsOutput(BaseModel):
    temperature_c: float
    conditions: str

# ---------- Webhook payload ----------
class TripPlan(BaseModel):
    user_id: int
    query: str
    plan: str
    tools_used: List[str]
    
# ------- Internal user representation -------
class CurrentUser(BaseModel):
    id: int

# ------- Login request (separate from UserCreate) -------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=72)

# ------- Geocoding result -------
class GeocodingCoords(BaseModel):
    lat: float
    lon: float

# ------- Destination feature vector (must match training columns) -------
class DestinationFeatures(BaseModel):
    continent: str                                  # <-- NEW
    avg_temperature: float
    cost_index: int = Field(ge=10, le=100)
    hiking_score: float = Field(ge=0, le=10)
    beach_score: float = Field(ge=0, le=10)
    culture_score: float = Field(ge=0, le=10)
    family_friendly_score: float = Field(ge=0, le=10)
    tourist_density: float = Field(ge=1, le=10)
    
# ---------- Classify Tool ----------

class ClassifyInput(BaseModel):
    features: DestinationFeatures
    
class ClassifyOutput(BaseModel):
    label: str
    probabilities: dict
    
    
class ClassifyByNameInput(BaseModel):
    """Used by the classify tool when the LLM passes a destination name."""
    destination: str = Field(..., min_length=1, description="Name of the destination to classify")
    
