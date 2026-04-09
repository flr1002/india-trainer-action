from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional

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

ROUTE_KEYWORDS = {
    "fdi_entry_mode": [
        "fdi", "foreign direct investment", "ownership", "entry mode",
        "joint venture", "wholly owned", "subsidiary", "automatic route",
        "approval route", "equity cap"
    ],
    "incorporation_compliance": [
        "incorporation", "registration", "register company", "company setup",
        "mca", "compliance", "private limited", "llp", "entity setup"
    ],
    "tax_customs": [
        "tax", "gst", "customs", "duty", "duties", "tariff", "tariffs",
        "import tax", "withholding tax"
    ],
    "sector_market": [
        "sector", "market", "industry", "competition", "competitor",
        "market size", "healthcare", "medical services", "medical devices",
        "pharma", "retail", "manufacturing", "it services", "distribution"
    ],
    "labour_hr": [
        "labour", "labor", "employment", "employee", "employees", "hiring",
        "hr", "wages", "salary", "termination", "contract worker"
    ],
    "culture_leadership": [
        "culture", "leadership", "hierarchy", "trust", "communication",
        "relationship", "authority", "decision-making", "power distance"
    ]
}

ROUTE_RESULTS = {
    "fdi_entry_mode": [
        SearchResult(
            title="Consolidated FDI Policy",
            source="DPIIT",
            url="https://www.dpiit.gov.in/",
            tier="tier1",
            source_type="government",
            date="2026-01-01",
            credibility_score=0.98,
            summary="Primary official source for FDI rules, entry structures, approval routes, and sectoral caps."
        ),
        SearchResult(
            title="Invest India - FDI and Entry Overview",
            source="Invest India",
            url="https://www.investindia.gov.in/",
            tier="tier1",
            source_type="government-linked",
            date="2026-01-01",
            credibility_score=0.94,
            summary="Practical entry-oriented overview for foreign investors, including sector and structure guidance."
        )
    ],
    "incorporation_compliance": [
        SearchResult(
            title="Company Registration and Compliance",
            source="MCA",
            url="https://www.mca.gov.in/",
            tier="tier1",
            source_type="government",
            date="2026-01-01",
            credibility_score=0.98,
            summary="Primary source for company incorporation, registration procedures, and compliance rules."
        ),
        SearchResult(
            title="Invest India - Business Setup",
            source="Invest India",
            url="https://www.investindia.gov.in/",
            tier="tier1",
            source_type="government-linked",
            date="2026-01-01",
            credibility_score=0.94,
            summary="Government-linked business setup guidance for foreign firms entering India."
        )
    ],
    "tax_customs": [
        SearchResult(
            title="Indirect Taxes and Customs",
            source="CBIC",
            url="https://www.cbic.gov.in/",
            tier="tier1",
            source_type="government",
            date="2026-01-01",
            credibility_score=0.98,
            summary="Primary source for GST, customs duties, tariffs, and indirect tax administration."
        ),
        SearchResult(
            title="Tax and Regulatory Overview",
            source="Deloitte India",
            url="https://www2.deloitte.com/in/en.html",
            tier="tier2",
            source_type="consulting",
            date="2026-01-01",
            credibility_score=0.88,
            summary="High-quality interpretive guidance on Indian tax and regulatory topics."
        )
    ],
    "sector_market": [
        SearchResult(
            title="Sector and Investment Opportunities",
            source="Invest India",
            url="https://www.investindia.gov.in/",
            tier="tier1",
            source_type="government-linked",
            date="2026-01-01",
            credibility_score=0.94,
            summary="Government-linked source for sector overviews, market opportunities, and investment themes."
        ),
        SearchResult(
            title="Industry and Sector Reports",
            source="FICCI",
            url="https://ficci.in/",
            tier="tier2",
            source_type="industry_body",
            date="2026-01-01",
            credibility_score=0.88,
            summary="Sector-level reports, industry sentiment, and market context."
        )
    ],
    "labour_hr": [
        SearchResult(
            title="Labour and Employment Framework",
            source="Invest India",
            url="https://www.investindia.gov.in/",
            tier="tier1",
            source_type="government-linked",
            date="2026-01-01",
            credibility_score=0.94,
            summary="Government-linked overview for employment-related operating topics."
        ),
        SearchResult(
            title="Employment and HR Insights",
            source="EY India",
            url="https://www.ey.com/en_in",
            tier="tier2",
            source_type="consulting",
            date="2026-01-01",
            credibility_score=0.88,
            summary="Interpretive guidance on workforce, labour, and HR topics in India."
        )
    ],
    "culture_leadership": [
        SearchResult(
            title="Country Cultural Profile",
            source="Hofstede Insights",
            url="https://www.hofstede-insights.com/",
            tier="tier4",
            source_type="academic-cultural-framework",
            date="2026-01-01",
            credibility_score=0.80,
            summary="Widely used comparative framework for cultural dimensions relevant to cross-border management."
        ),
        SearchResult(
            title="Leadership and Culture Research",
            source="GLOBE Study",
            url="https://globeproject.com/",
            tier="tier4",
            source_type="academic-cultural-framework",
            date="2026-01-01",
            credibility_score=0.82,
            summary="Research-based source on leadership expectations and cultural patterns."
        )
    ]
}

def detect_route(query: str) -> Optional[str]:
    q = query.lower()
    route_scores = {}

    for route, keywords in ROUTE_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if keyword in q:
                score += 1
        if score > 0:
            route_scores[route] = score

    if not route_scores:
        return None

    return max(route_scores, key=route_scores.get)

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

    route = detect_route(request.query)

    if route is None:
        return SearchResponse(
            query=request.query,
            route=None,
            results=[],
            uncertainty=True,
            message="No sufficiently trusted source route found for this query. Do not infer beyond the retrieval output."
        )

    results = ROUTE_RESULTS.get(route, [])[:request.max_results]

    if not results:
        return SearchResponse(
            query=request.query,
            route=route,
            results=[],
            uncertainty=True,
            message="A route was detected, but no trusted source set is available yet."
        )

    return SearchResponse(
        query=request.query,
        route=route,
        results=results,
        uncertainty=False,
        message="Trusted sources found."
    )
