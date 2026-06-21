# models.py — the request/response contract. Keep extension + backend in sync with this.
from pydantic import BaseModel
from typing import List


class ResearchRequest(BaseModel):
    brand: str


class Source(BaseModel):
    label: str
    url: str


class ResearchResponse(BaseModel):
    brand: str
    ethics_score: int      # 0-100, higher = better
    ownership_score: int   # 0-100, independent/small high, conglomerate/PE-owned low
    summary: str
    sources: List[Source] = []
    cached: bool = False


class AlternativesRequest(BaseModel):
    brand: str
    title: str = ""        # product page title — used to infer the category
    score: int = 0         # the item's overall good_clothes score, so we beat it
    composition: str = ""  # e.g. "100% cotton" — context for material upgrades
    image: str = ""        # product image URL — Claude vision reads the look from it
    pref: str = "balanced" # user's style lane (set in onboarding) — biases brand picks


class Alternative(BaseModel):
    name: str              # a real, more-conscious brand in the same category
    why: str               # one line: why it's a better buy
    est_score: int         # rough 0-100 estimate, must beat the original
    url: str               # search link we build server-side (never hallucinated)


class AlternativesResponse(BaseModel):
    category: str
    look: str = ""         # the visual query Claude read from the photo
    alternatives: List[Alternative] = []
    cached: bool = False


class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]


class ChatResponse(BaseModel):
    message: str
    pref_text: str = ""


class PrefSetRequest(BaseModel):
    user_id: str           # anonymous id generated once per install
    pref: str


class PrefResponse(BaseModel):
    pref: str = ""         # empty when nothing stored / Supabase not configured
    saved: bool = False    # set on a successful write
    persisted: bool = False  # whether Supabase is actually wired up
