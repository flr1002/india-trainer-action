from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List

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
    results: List[SearchResult]
    uncertainty: bool
    message: str

@app.get("/")
def root():
    return {"message": "India Trainer Action API is running"}

@app.post("/search_sources", response_model=SearchResponse)
def search_sources(request: SearchRequest):
    return SearchResponse(
        query=request.query,
        results=[
            SearchResult(
                title="FDI Policy for Medical Devices",
                source="DPIIT",
                url="https://www.dpiit.gov.in/",
                tier="tier1",
                source_type="government",
                date="2026-01-01",
                credibility_score=0.98,
                summary="Official policy-related source for foreign investment and industry regulation."
            ),
            SearchResult(
                title="Medical Devices Sector Overview",
                source="Invest India",
                url="https://www.investindia.gov.in/",
                tier="tier1",
                source_type="government-linked",
                date="2026-01-01",
                credibility_score=0.94,
                summary="Entry-oriented overview for foreign investors in India."
            )
        ][:request.max_results],
        uncertainty=False,
        message="Trusted sources found."
    )