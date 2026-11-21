from typing import Optional
from pydantic import BaseModel, Field


# ---- Models the LLM fills in (no defaults, so the JSON schema stays simple) ----

class Finding(BaseModel):
    fact: str
    source_url: str


class ResearchFindings(BaseModel):
    findings: list[Finding]
    gaps: list[str]  # things the search results did not cover


class Competitor(BaseModel):
    name: str
    description: str


class Brief(BaseModel):
    summary: str
    competitors: list[Competitor]  # trimmed to max 2 in code
    key_observations: list[str]
    sources: list[str]
    missing_information: list[str]


class CriticFeedback(BaseModel):
    approved: bool
    issues: list[str]  # specific problems to fix; empty if approved


# ---- The object passed between roles ----

class WorkflowState(BaseModel):
    query: str
    data_source: str = "web"  # "web" or "sample"
    findings: Optional[ResearchFindings] = None
    draft: Optional[Brief] = None
    feedback: Optional[CriticFeedback] = None
    final_brief: Optional[Brief] = None
    revised: bool = False
    log: list[str] = Field(default_factory=list)  # step-by-step trace for the UI
    scope: Optional[QueryCheck] = None
    stopped_reason: Optional[str] = None

    def topic(self) -> str:
        """The disambiguated topic if known, otherwise the raw query."""
        return self.scope.interpretation if self.scope else self.query

class QueryCheck(BaseModel):
    kind: str            # exactly one of: "company", "industry", "not_business"
    interpretation: str  # short description of what the input refers to
    search_query: str    # refined, unambiguous web search query
    message: str         # for "not_business": short message to the user; otherwise empty

class CompetitorNames(BaseModel):
    names: list[str]  # at most 2