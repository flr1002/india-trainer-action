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
    disclaimer: Optional[str] = None

BLOCKED_KEYWORDS = [
    "reddit",
    "quora",
    "wikipedia",
    "medium",
    "linkedin",
    "facebook",
    "instagram",
    "twitter",
    "x.com",
    "tiktok",
    "youtube"
]

BLOCKED_DOMAINS = {
    "reddit.com": "user_generated",
    "quora.com": "user_generated",
    "wikipedia.org": "low_trust",
    "medium.com": "low_trust",
    "linkedin.com": "user_generated",
    "facebook.com": "social_media",
    "instagram.com": "social_media",
    "x.com": "social_media",
    "twitter.com": "social_media",
    "tiktok.com": "social_media",
    "youtube.com": "video_platform"
}

TIER1_DISCLAIMER = (
    "This answer is based on sources that were retrieved successfully but are not "
    "classified as Tier 1 sources in the system's trust hierarchy. It should "
    "therefore be treated as indicative rather than fully verified. I recommend "
    "an independent check before relying on it."
)

TIER1_DOMAIN_RULES = {
    "dpiit.gov.in": {"source": "DPIIT", "tier": "tier1", "source_type": "government", "credibility_score": 0.98},
    "investindia.gov.in": {"source": "Invest India", "tier": "tier1", "source_type": "government-linked", "credibility_score": 0.94},
    "rbi.org.in": {"source": "RBI", "tier": "tier1", "source_type": "government", "credibility_score": 0.98},
    "nsws.gov.in": {"source": "NSWS", "tier": "tier1", "source_type": "government", "credibility_score": 0.96},
    "indiacode.nic.in": {"source": "India Code", "tier": "tier1", "source_type": "government", "credibility_score": 0.98},
    "mca.gov.in": {"source": "MCA", "tier": "tier1", "source_type": "government", "credibility_score": 0.98},
    "cbic.gov.in": {"source": "CBIC", "tier": "tier1", "source_type": "government", "credibility_score": 0.98},
    "gst.gov.in": {"source": "GST Portal", "tier": "tier1", "source_type": "government", "credibility_score": 0.97},
    "dgft.gov.in": {"source": "DGFT", "tier": "tier1", "source_type": "government", "credibility_score": 0.97},
    "incometax.gov.in": {"source": "Income Tax Department", "tier": "tier1", "source_type": "government", "credibility_score": 0.97},
    "epfindia.gov.in": {"source": "EPFO", "tier": "tier1", "source_type": "government", "credibility_score": 0.96},
    "esic.gov.in": {"source": "ESIC", "tier": "tier1", "source_type": "government", "credibility_score": 0.96},
    "bis.gov.in": {"source": "BIS", "tier": "tier1", "source_type": "government", "credibility_score": 0.96},
    "fssai.gov.in": {"source": "FSSAI", "tier": "tier1", "source_type": "government", "credibility_score": 0.97},
    "foscos.fssai.gov.in": {"source": "FoSCoS", "tier": "tier1", "source_type": "government-portal", "credibility_score": 0.97},
    "cdsco.gov.in": {"source": "CDSCO", "tier": "tier1", "source_type": "government", "credibility_score": 0.96},
    "sebi.gov.in": {"source": "SEBI", "tier": "tier1", "source_type": "government", "credibility_score": 0.97},
    "ipindia.gov.in": {"source": "IP India", "tier": "tier1", "source_type": "government", "credibility_score": 0.96}
}

KNOWN_FALLBACK_DOMAIN_RULES = {
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
    "tier1": 3,
    "allowed": 2,
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

    for allowed_domain, meta in TIER1_DOMAIN_RULES.items():
        if domain == allowed_domain or domain.endswith("." + allowed_domain):
            return {
                **meta,
                "trust_level": "tier1"
            }

    for allowed_domain, meta in KNOWN_FALLBACK_DOMAIN_RULES.items():
        if domain == allowed_domain or domain.endswith("." + allowed_domain):
            return {
                **meta,
                "trust_level": "allowed"
            }

    return {
        "source": domain or "unknown",
        "tier": "tier2",
        "source_type": "unclassified",
        "trust_level": "allowed",
        "credibility_score": 0.6
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

def build_tier1_query(query: str) -> str:
    site_filters = " OR ".join(f"site:{domain}" for domain in TIER1_DOMAIN_RULES)
    return f"({site_filters}) {query}"

def parse_search_results(raw_results: List[dict]) -> List[SearchResult]:
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

    return filter_and_rank_results(parsed_results)

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
                message="Blocked or disallowed source request detected.",
                disclaimer=None
            )

    try:
        tier1_data = call_tavily_search(
            build_tier1_query(request.query),
            max_results=min(request.max_results * 3, 10)
        )
    except Exception as e:
        return SearchResponse(
            query=request.query,
            route=None,
            results=[],
            uncertainty=True,
            message=f"Search provider error: {str(e)}",
            disclaimer=None
        )

    tier1_results = [
        result for result in parse_search_results(tier1_data.get("results", []))
        if result.trust_level == "tier1"
    ][:request.max_results]

    if tier1_results:
        return SearchResponse(
            query=request.query,
            route="tier1_only",
            results=tier1_results,
            uncertainty=False,
            message="Tier 1 sources found. Returning Tier 1 results only.",
            disclaimer=None
        )

    try:
        fallback_data = call_tavily_search(
            request.query,
            max_results=min(request.max_results * 3, 10)
        )
    except Exception as e:
        return SearchResponse(
            query=request.query,
            route=None,
            results=[],
            uncertainty=True,
            message=f"Search provider error: {str(e)}",
            disclaimer=None
        )

    fallback_results = [
        result for result in parse_search_results(fallback_data.get("results", []))
        if result.trust_level not in {"blocked", "tier1"}
    ][:request.max_results]

    if not fallback_results:
        return SearchResponse(
            query=request.query,
            route="no_results",
            results=[],
            uncertainty=True,
            message="No allowed sources were retrieved for this question.",
            disclaimer=None
        )

    return SearchResponse(
        query=request.query,
        route="fallback_non_tier1",
        results=fallback_results,
        uncertainty=True,
        message="No Tier 1 sources were found. Returning allowed fallback sources.",
        disclaimer=TIER1_DISCLAIMER
    )
