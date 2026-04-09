from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import json
from urllib import request as urllib_request
from urllib.parse import urlparse

app = FastAPI()

class SearchRequest(BaseModel):
    query: str = Field(..., description="The external factual question to search for.")
    max_results: int = Field(default=5, ge=1, le=10)

class SearchResult(BaseModel):
    title: str
    source: str
    url: str
    tier: str
    source_type: str
    trust_level: str
    date: str
    credibility_score: float
    summary: str

class SearchResponse(BaseModel):
    query: str
    route: Optional[str] = None
    results: List[SearchResult]
    uncertainty: bool
    message: str

BLOCKED_KEYWORDS = [
    "reddit",
    "quora",
    "wikipedia",
    "medium"
]

BLOCKED_DOMAINS = {
    "reddit.com": "user_generated",
    "quora.com": "user_generated",
    "wikipedia.org": "low_trust",
    "medium.com": "low_trust",
    "linkedin.com": "user_generated"
}

HIGH_TRUST_DOMAIN_RULES = {
    "dpiit.gov.in": {"source": "DPIIT", "tier": "tier1", "source_type": "government", "credibility_score": 0.98},
    "investindia.gov.in": {"source": "Invest India", "tier": "tier1", "source_type": "government-linked", "credibility_score": 0.94},
    "mca.gov.in": {"source": "MCA", "tier": "tier1", "source_type": "government", "credibility_score": 0.98},
    "cbic.gov.in": {"source": "CBIC", "tier": "tier1", "source_type": "government", "credibility_score": 0.98},
    "rbi.org.in": {"source": "RBI", "tier": "tier1", "source_type": "government", "credibility_score": 0.98}
}

MEDIUM_TRUST_DOMAIN_RULES = {
    "ficci.in": {"source": "FICCI", "tier": "tier2", "source_type": "industry_body", "credibility_score": 0.88},
    "ey.com": {"source": "EY", "tier": "tier2", "source_type": "consulting", "credibility_score": 0.88},
    "deloitte.com": {"source": "Deloitte", "tier": "tier2", "source_type": "consulting", "credibility_score": 0.88},
    "hofstede-insights.com": {"source": "Hofstede Insights", "tier": "tier4", "source_type": "academic-cultural-framework", "credibility_score": 0.80},
    "globeproject.com": {"source": "GLOBE Study", "tier": "tier4", "source_type": "academic-cultural-framework", "credibility_score": 0.82},
    "indiajuris.com": {"source": "India Juris", "tier": "tier2", "source_type": "consulting", "credibility_score": 0.82},
    "spiceroutelegal.com": {"source": "Spice Route Legal", "tier": "tier2", "source_type": "consulting", "credibility_score": 0.82},
    "law.asia": {"source": "Law.asia", "tier": "tier3", "source_type": "business_media", "credibility_score": 0.75}
}

TRUST_PRIORITY = {
    "high_trust": 3,
    "medium_trust": 2,
    "unknown": 1,
    "blocked": 0
}

def normalize_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""

def classify_source(url: str):
    domain = normalize_domain(url)

    for blocked_domain, blocked_type in BLOCKED_DOMAINS.items():
        if domain == blocked_domain or domain.endswith("." + blocked_domain):
            return {
                "source": domain,
                "tier": "blocked",
                "source_type": blocked_type,
                "trust_level": "blocked",
                "credibility_score": 0.0
            }

    if domain.endswith(".gov.in"):
        return {
            "source": domain,
            "tier": "tier1",
            "source_type": "government",
            "trust_level": "high_trust",
            "credibility_score": 0.96
        }

    for allowed_domain, meta in HIGH_TRUST_DOMAIN_RULES.items():
        if domain == allowed_domain or domain.endswith("." + allowed_domain):
            return {
                **meta,
                "trust_level": "high_trust"
            }

    for allowed_domain, meta in MEDIUM_TRUST_DOMAIN_RULES.items():
        if domain == allowed_domain or domain.endswith("." + allowed_domain):
            return {
                **meta,
                "trust_level": "medium_trust"
            }

    return {
        "source": domain or "unknown",
        "tier": "unknown",
        "source_type": "unclassified",
        "trust_level": "unknown",
        "credibility_score": 0.45
    }

def filter_and_rank_results(results: List[SearchResult]) -> List[SearchResult]:
    filtered = [r for r in results if r.trust_level != "blocked"]
    filtered.sort(
        key=lambda r: (
            TRUST_PRIORITY.get(r.trust_level, 0),
            r.credibility_score
        ),
        reverse=True
    )
    return filtered

def has_sufficient_trust(results: List[SearchResult]) -> bool:
    if any(r.trust_level == "high_trust" for r in results):
        return True
    medium_count = sum(1 for r in results if r.trust_level == "medium_trust")
    return medium_count >= 2

def call_tavily_search(query: str, max_results: int):
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY is not set.")

    payload = {
        "query": query,
        "max_results": max_results,
        "search_depth": "advanced",
        "include_answer": False,
        "include_raw_content": False
    }

    req = urllib_request.Request(
        "https://api.tavily.com/search",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        method="POST"
    )

    with urllib_request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))

@app.get("/")
def root():
    return {"message": "India Trainer Action API is running"}

@app.post("/search_sources", response_model=SearchResponse)
def search_sources(request: SearchRequest):
    q = request.query.lower()

    for blocked in BLOCKED_KEYWORDS:
        if blocked in q:
            return SearchResponse(
                query=request.query,
                route=None,
                results=[],
                uncertainty=True,
                message="Blocked or low-trust source request detected."
            )

    try:
        tavily_data = call_tavily_search(request.query, max_results=min(request.max_results * 3, 10))
    except Exception as e:
        return SearchResponse(
            query=request.query,
            route=None,
            results=[],
            uncertainty=True,
            message=f"Search provider error: {str(e)}"
        )

    raw_results = tavily_data.get("results", [])
    parsed_results = []

    for item in raw_results:
        url = item.get("url", "")
        title = item.get("title", "Untitled")
        summary = item.get("content", "") or item.get("snippet", "") or ""
        meta = classify_source(url)

        parsed_results.append(
            SearchResult(
                title=title,
                source=meta["source"],
                url=url,
                tier=meta["tier"],
                source_type=meta["source_type"],
                trust_level=meta["trust_level"],
                date="",
                credibility_score=meta["credibility_score"],
                summary=summary[:500]
            )
        )

    ranked_results = filter_and_rank_results(parsed_results)
    final_results = ranked_results[:request.max_results]

    if not final_results or not has_sufficient_trust(final_results):
        return SearchResponse(
            query=request.query,
            route=None,
            results=final_results,
            uncertainty=True,
            message="No sufficiently precise trusted source found. Do not infer a specific rule."
        )

    return SearchResponse(
        query=request.query,
        route=None,
        results=final_results,
        uncertainty=False,
        message="Trusted or sufficiently credible sources found."
    )
