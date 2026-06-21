# main.py — run with:  uvicorn main:app --reload  (from inside backend/)
import hashlib
import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

import cache
import research
import synthesize
import alternatives
import db
from models import (
    ResearchRequest,
    ResearchResponse,
    AlternativesRequest,
    AlternativesResponse,
    PrefSetRequest,
    PrefResponse,
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

# Load the landing page once at startup; fall back to a tiny message if it's missing.
try:
    _LANDING = (pathlib.Path(__file__).parent / "landing.html").read_text(encoding="utf-8")
except Exception:
    _LANDING = "<h1>good_clothes API</h1><p>See /health</p>"


@app.get("/", response_class=HTMLResponse)
def home():
    return _LANDING


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
    # Key on the image too: alternatives are matched to THIS item's look, so two items
    # of the same brand+category (different colors/photos) must not share a cache entry.
    img_key = hashlib.sha1(req.image.encode("utf-8")).hexdigest()[:10] if req.image else "noimg"
    # pref is part of the key: the same item under a different style lane is a different result.
    key = f"alt::{brand.lower()}::{category}::{req.pref}::{img_key}"  # namespaced; can't collide with /research

    hit = cache.get(key)
    if hit:
        hit["cached"] = True
        return hit

    result = alternatives.suggest_alternatives(
        brand, req.title, req.score, req.composition, req.image, req.pref
    )
    result["cached"] = False

    cache.put(key, result)
    return result


@app.get("/prefs", response_model=PrefResponse)
def get_prefs(user_id: str):
    return {"pref": db.get_pref(user_id) or "", "persisted": db.enabled()}


@app.post("/prefs", response_model=PrefResponse)
def set_prefs(req: PrefSetRequest):
    saved = db.set_pref(req.user_id, req.pref)
    return {"pref": req.pref, "saved": saved, "persisted": db.enabled()}
