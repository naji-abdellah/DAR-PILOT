"""FastAPI routes for DarPilot.

Public endpoints:
- GET /listings              → list available listings
- GET /listings/{id}         → single listing
- POST /auth/register        → create a user account
- POST /auth/login           → obtain a short-lived JWT

Authenticated endpoints (require a valid Bearer token):
- POST /listings             → create listing (agent/admin)
- GET /leads/{id}            → single lead
- GET /leads/listing/{lid}   → leads for a listing
- POST /leads                → create lead (public lead capture)
- POST /visits               → schedule a visit
- GET /visits/{id}           → single visit

Roles are enforced server-side via ``require_role``.
"""

from __future__ import annotations

import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend import auth
from backend import services
from ai import rag
from ai.llm import get_llm_client

router = APIRouter()

# Rate limiter keyed by client IP. Wired to the app in backend/app.py.
# Login rate limit is configurable via DARPILOT_LOGIN_RATE_LIMIT (default 5/minute).
LOGIN_RATE_LIMIT = os.environ.get("DARPILOT_LOGIN_RATE_LIMIT", "5/minute")
limiter = Limiter(key_func=get_remote_address)


# ── Pydantic request models ───────────────────────────────────────────

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

# ── Auth endpoints ────────────────────────────────────────────────────


@router.post("/auth/register", response_model=dict, status_code=201)
def register(payload: UserRegister):
    """Create a new user account. Password is hashed server-side."""
    try:
        return services.register_user_account(
            username=payload.username,
            email=payload.email,
            password=payload.password,
            role=payload.role,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/auth/login", response_model=TokenResponse)
@limiter.limit(LOGIN_RATE_LIMIT)
def login(request: Request, payload: UserLogin):
    """Verify credentials and return a short-lived JWT."""
    user = services.authenticate_user(payload.username, payload.password)
    if user is None:
        # Alert n8n about failed login
        client_ip = request.client.host if request.client else None
        services.alert_failed_login(payload.username, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth.create_access_token(user_id=user["id"], role=user["role"])
    return {"access_token": token, "token_type": "bearer"}

# ── Listing endpoints ──────────────────────────────────────────────────


@router.get("/listings", response_model=List[dict])
def list_listings(status: Optional[str] = Query(None, pattern="^(available|sold|pending)$")):
    """Return all listings, optionally filtered by status."""
    if status is not None:
        return services.get_listings_by_status(status)
    return services.get_listings()


@router.get("/listings/{listing_id}", response_model=dict)
def get_listing(listing_id: int):
    """Fetch a single listing by ID."""
    if listing_id <= 0:
        raise HTTPException(status_code=400, detail="listing_id must be positive")
    listing = services.get_listing(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing


@router.get("/search", response_model=List[dict])
def search_listings(
    q: str = Query(..., min_length=1, max_length=200),
    top_k: int = Query(5, ge=1, le=20),
):
    """Semantic search over listings via RAG.

    Returns the top-k most similar chunks with their cosine-similarity score
    and listing metadata, suitable for citation.
    """
    return rag.search(q, top_k=top_k)


RAG_THRESHOLD = float(os.environ.get("DARPILOT_RAG_THRESHOLD", "0.60"))


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)


@router.post("/ask", response_model=dict)
def ask(payload: AskRequest):
    """Answer a question in French or English using RAG over listings.

    Retrieves the top-k relevant chunks, builds a cited answer, and refuses
    when nothing relevant is found. Returns the answer plus the listing IDs
    used as sources.
    """
    question = payload.question.strip()
    results = rag.search(question, top_k=5)
    relevant = [r for r in results if r["score"] >= RAG_THRESHOLD]

    if not relevant:
        return {
            "answer": ("Je n'ai trouv aucune annonce correspondant votre recherche."
                       if _looks_french(question)
                       else "I couldn't find any listings matching your search."),
            "sources": [],
            "refused": True,
        }

    client = get_llm_client()
    context_lines = "\n".join(
        f"- [id: {r['listing_id']}] {r['title']} ({r['city']}, {r['neighborhood']}) "
        f"{r['price_mad']} MAD, {r['property_type']}, {r['status']}. {r['chunk_text']}"
        for r in relevant
    )
    lang = "French" if _looks_french(question) else "English"
    prompt = (
        "You are a helpful real-estate assistant for a fictional Moroccan agency.\n"
        "Answer the question in the same language as the question (French or English).\n"
        "Use ONLY the provided listings. Cite each listing you mention as [id: N].\n"
        "Do not invent listings or prices.\n\n"
        f"Listings:\n{context_lines}\n\n"
        f"Question: {question}\n"
        "Answer:"
    )
    try:
        answer = client.generate(prompt)
    except Exception:
        # Graceful degradation: live provider unavailable (bad key, rate limit,
        # network). Fall back to the offline fake client so the demo keeps
        # working. M4 adds proper retry/backoff + OpenRouter fallback.
        from ai.llm import FakeLLMClient

        answer = FakeLLMClient().generate(prompt)

    return {
        "answer": answer,
        "sources": [{"id": r["listing_id"], "title": r["title"], "score": round(r["score"], 3)}
                    for r in relevant],
        "refused": False,
    }


def _looks_french(text: str) -> bool:
    markers = ("louer", "vente", "appartement", "villa", "studio", "riad",
               "marrakech", "casablanca", "cher", "bonjour", "prix")
    return any(m in text.lower() for m in markers)


@router.post("/listings", response_model=dict, status_code=201)
def create_listing(
    payload: ListingCreate,
    current_user: dict = Depends(auth.require_role("agent", "admin")),
):
    """Create a listing. Requires agent or admin role."""
    try:
        return services.create_listing(
            title=payload.title,
            description=payload.description,
            price_mad=payload.price_mad,
            city=payload.city,
            neighborhood=payload.neighborhood,
            property_type=payload.property_type,
            status=payload.status,
            agent_id=current_user["id"] if payload.agent_id is None else payload.agent_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.post("/leads", response_model=dict, status_code=201)
def create_lead(payload: LeadCreate):
    """Create a new lead (public capture form)."""
    try:
        return services.create_lead(
            name=payload.name,
            phone=payload.phone,
            email=payload.email,
            message=payload.message,
            listing_id=payload.listing_id,
            status=payload.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/leads/{lead_id}", response_model=dict)
def get_lead(
    lead_id: int,
    current_user: dict = Depends(auth.require_role("agent", "admin")),
):
    """Fetch a single lead by ID. Requires agent or admin role."""
    if lead_id <= 0:
        raise HTTPException(status_code=400, detail="lead_id must be positive")
    lead = services.get_lead_by_id(lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.get("/leads/listing/{listing_id}", response_model=List[dict])
def list_leads_for_listing(
    listing_id: int,
    current_user: dict = Depends(auth.require_role("agent", "admin")),
):
    """Return all leads for a given listing. Requires agent or admin role."""
    if listing_id <= 0:
        raise HTTPException(status_code=400, detail="listing_id must be positive")
    return services.get_leads_by_listing(listing_id)

@router.post("/visits", response_model=dict, status_code=201)
def create_visit(
    payload: VisitCreate,
    current_user: dict = Depends(auth.get_current_user),
):
    """Schedule a visit. Requires authentication."""
    try:
        return services.create_visit(
            lead_id=payload.lead_id,
            listing_id=payload.listing_id,
            scheduled_at=payload.scheduled_at,
            status=payload.status,
            notes=payload.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/visits/{visit_id}", response_model=dict)
def get_visit(
    visit_id: int,
    current_user: dict = Depends(auth.get_current_user),
):
    """Fetch a single visit by ID. Requires authentication."""
    if visit_id <= 0:
        raise HTTPException(status_code=400, detail="visit_id must be positive")
    visit = services.get_visit_by_id(visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail="Visit not found")
    return visit


@router.get("/health")
def health():
    """Simple health check."""
    return {"status": "ok", "version": "0.1.0"}


# ── Security Alert Endpoints (for n8n integration) ──────────────────────

class BlockedPromptAlert(BaseModel):
    user_id: Optional[int] = None
    attack_type: str
    payload: str
    ip: Optional[str] = None


@router.post("/security/blocked-prompt", response_model=dict)
def report_blocked_prompt(alert: BlockedPromptAlert, request: Request):
    """Receive blocked prompt report from agent and forward to n8n."""
    client_ip = alert.ip or (request.client.host if request.client else None)
    services.alert_blocked_prompt(alert.user_id, alert.attack_type, alert.payload, client_ip)
    return {"success": True, "message": "Alert forwarded to monitoring"}


class AIErrorAlert(BaseModel):
    endpoint: str
    error: str


@router.post("/security/ai-error", response_model=dict)
def report_ai_error(alert: AIErrorAlert):
    """Receive AI service error and forward to n8n error workflow."""
    services.alert_ai_service_error(alert.endpoint, alert.error)
    return {"success": True, "message": "Error alert forwarded to monitoring"}
