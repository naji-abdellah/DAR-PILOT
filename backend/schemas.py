"""Pydantic request/response models for DarPilot."""

from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field("agent", pattern="^(admin|agent|viewer)$")


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ListingCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=5000)
    price_mad: int = Field(..., ge=0, le=100_000_000)
    city: str = Field(..., min_length=1, max_length=50)
    neighborhood: str = Field("", max_length=50)
    property_type: str = Field(..., pattern="^(Apartment|Villa|Studio|Riad)$")
    status: str = Field("available", pattern="^(available|sold|pending)$")
    agent_id: Optional[int] = None


class LeadCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    email: EmailStr
    message: str = Field("", max_length=2000)
    listing_id: Optional[int] = None
    status: str = Field("new", pattern="^(new|contacted|closed)$")


class VisitCreate(BaseModel):
    lead_id: int
    listing_id: int
    scheduled_at: str = Field(..., min_length=10, max_length=50)
    status: str = Field("scheduled", pattern="^(scheduled|completed|cancelled)$")
    notes: Optional[str] = Field(None, max_length=1000)


class BlockedPromptAlert(BaseModel):
    user_id: Optional[int] = None
    attack_type: str
    payload: str
    ip: Optional[str] = None


class AIErrorAlert(BaseModel):
    endpoint: str
    error: str


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)