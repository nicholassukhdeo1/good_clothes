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
