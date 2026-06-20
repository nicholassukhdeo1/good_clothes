# main.py — run with:  uvicorn main:app --reload  (from inside backend/)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import cache
import research
import synthesize
import alternatives
from models import (
    ResearchRequest,
    ResearchResponse,
    AlternativesRequest,
    AlternativesResponse,
)

app = FastAPI(title="good_clothes")

# Extensions send an "origin" of chrome-extension://...; "*" is simplest for the hackathon.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

cache.init()


@app.get("/health")
def health():
    return {"ok": True}


# NOTE: this is a SYNC def on purpose. FastAPI runs sync routes in a threadpool,
# which lets us use sync Playwright + the Anthropic sync client without async footguns.
@app.post("/research", response_model=ResearchResponse)
def research_brand(req: ResearchRequest):
    brand = req.brand.strip()

    hit = cache.get(brand)
    if hit:
        hit["brand"] = brand
        hit["cached"] = True
        return hit

    evidence = research.gather_brand_evidence(brand)
    result = synthesize.synthesize(brand, evidence)
    result["brand"] = brand
    result["cached"] = False

    cache.put(brand, result)
    return result


@app.post("/alternatives", response_model=AlternativesResponse)
def alternatives_for(req: AlternativesRequest):
    brand = req.brand.strip()
    category = alternatives.infer_category(req.title)
    key = f"alt::{brand.lower()}::{category}"  # namespaced so it can't collide with /research

    hit = cache.get(key)
    if hit:
        hit["cached"] = True
        return hit

    result = alternatives.suggest_alternatives(
        brand, req.title, req.score, req.composition, req.image
    )
    result["cached"] = False

    cache.put(key, result)
    return result
