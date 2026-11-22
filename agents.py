import json
from typing import Callable, Optional

from llm import LLMError, generate_structured
from models import (
    Brief,
    CompetitorNames,
    CriticFeedback,
    QueryCheck,
    ResearchFindings,
    WorkflowState,
)
from search import search_topic, search_web

StepCallback = Optional[Callable[[str, WorkflowState], None]]


def _step(state: WorkflowState, name: str, on_step: StepCallback) -> None:
    """Record a finished step and notify the UI (if any)."""
    state.log.append(name)
    if on_step:
        on_step(name, state)


# --------------------------------------------------------------------------
# Researcher
# --------------------------------------------------------------------------
RESEARCHER_SYSTEM = (
    "You are a research assistant. You only report facts that appear in the "
    "search results you are given. You never add outside knowledge."
)


def _format_snippets(results: list[dict]) -> str:
    return "\n".join(f"- {r['title']} | {r['url']} | {r['snippet']}" for r in results)


def _add_competitor_results(
    topic: str, base_query: str, results: list[dict]
) -> list[dict]:
    """Second pass: find the main competitors in the snippets, then search for each."""
    prompt = f"""Topic: {topic}

Search results:
{_format_snippets(results)}

Name up to 2 main competitors of this topic (for an industry: its leading companies).
Only use names that appear in the search results above. If none appear, return an empty list."""

    try:
        picked = generate_structured(prompt, CompetitorNames, system=RESEARCHER_SYSTEM)
        print("Competitor picker returned:", picked.names)
    except LLMError:
        return results  # skip the second pass, keep what we have

    merged = list(results)
    seen = {r["url"] for r in results}
    for name in picked.names[:2]:
        extra, src = search_web(f"{name} vs {base_query} market share", max_results=4)
        if src != "web":  # ignore sample data here
            continue
        for r in extra:
            if r["url"] not in seen:
                seen.add(r["url"])
                merged.append(r)
    return merged


def researcher(state: WorkflowState) -> WorkflowState:
    topic = state.topic()
    base_query = state.scope.search_query if state.scope else state.query

    results, source = search_topic(base_query)
    state.data_source = source

    if source == "none":
        state.findings = ResearchFindings(
            findings=[],
            gaps=[
                "Live web search returned no results, and no sample data applies to this topic."
            ],
        )
        print(
            "Findings mentioning Uber:",
            [f.fact for f in found.findings if "uber" in f.fact.lower()],
        )
        return state

    if source == "web":
        results = _add_competitor_results(topic, base_query, results)

    prompt = f"""Research topic: {topic}

Search results:
{_format_snippets(results)}

Extract up to 12 distinct facts relevant to the topic. Rules:
- Each fact must be directly supported by one search result.
- source_url must be copied exactly from that result's URL.
- Do not invent numbers, names or dates.
- Include facts about the main competitors by name (what they do, size, share,
  how they compare), so the brief can describe them.
- Where the results mention them, capture market size, growth rate and market share.
- Prefer research firms, company websites and news outlets. Treat user-uploaded
  documents (e.g. Scribd) as low-reliability: use them sparingly, and mention
  in "gaps" if a key point rests only on such a source.
- In "gaps", list what a market brief would need but the results do not cover."""

    found = generate_structured(prompt, ResearchFindings, system=RESEARCHER_SYSTEM)

    # Guardrail: drop any finding that cites a URL we never gave the model.
    valid_urls = {r["url"] for r in results}
    kept = [f for f in found.findings if f.source_url in valid_urls]
    if len(kept) < len(found.findings):
        found.gaps.append(
            "Some extracted facts were discarded because their source could not be verified."
        )
    found.findings = kept

    if source == "sample":
        found.gaps.append(
            "Live web search was unavailable; findings are illustrative sample data and not verified."
        )
    state.findings = found
    return state


# --------------------------------------------------------------------------
# Analyst
# --------------------------------------------------------------------------
ANALYST_SYSTEM = (
    "You are a market analyst who writes short, factual briefs. You use only the "
    "research findings provided. If evidence is missing, you say so instead of guessing."
)


def analyst(state: WorkflowState, revise: bool = False) -> WorkflowState:
    if not state.findings.findings:
        state.draft = Brief(
            summary=f"No usable evidence could be gathered for '{state.query}', so no brief could be written.",
            competitors=[],
            key_observations=[],
            sources=[],
            missing_information=state.findings.gaps,
        )
        state.final_brief = state.draft
        return state
    findings_json = state.findings.model_dump_json(indent=2)

    prompt = f"""Topic: {state.query}

Research findings (your only source of evidence):
{findings_json}

Write a short market research brief with:
- summary: 2-3 sentences on the topic
- competitors: AT MOST 2, and only if named in the findings (otherwise an empty list)
- key_observations: 3-5 short bullet-style points, each backed by the findings
- sources: URLs of the findings you used
- missing_information: what the evidence does not cover (include the research gaps)

Do not state any number, name or claim that is not in the findings.

Style rules:
- Each competitor description must be different and specific to that company.
  If the findings give no detail beyond the name, write "Named in sources; no
  further detail found."
- Avoid superlatives and hype (e.g. "remarkable", "booming") unless a finding
  states it.
- Only mention a trend (e.g. urban vs rural) if a finding supports it.
- Only attach a statement to a specific company if a finding says it about that
  company. Market-level statements (e.g. barriers to entry, growth drivers)
  belong in the summary or observations, not in a competitor's description.
- For each competitor, use every finding that mentions that company, including
  findings taken from pages about that company. Only fall back to "Named in
  sources; no further detail found." if no finding says anything about it.
"""

    if revise:
        prompt += f"""

This is a REVISION. Your previous draft:
{state.draft.model_dump_json(indent=2)}

The critic raised these issues. Fix every one of them:
{json.dumps(state.feedback.issues, indent=2)}"""

    brief = generate_structured(prompt, Brief, system=ANALYST_SYSTEM)

    # Enforce rules in code, not just in the prompt.
    brief.competitors = brief.competitors[:2]
    brief.sources = sorted({f.source_url for f in state.findings.findings})
    if state.data_source == "sample" and not any(
        "sample" in m.lower() for m in brief.missing_information
    ):
        brief.missing_information.append(
            "This brief is based on illustrative sample data, not live research."
        )

    if revise:
        state.final_brief = brief
        state.revised = True
    else:
        state.draft = brief
    return state


# --------------------------------------------------------------------------
# Critic
# --------------------------------------------------------------------------
CRITIC_SYSTEM = (
    "You are a strict but fair reviewer of market research briefs. You check "
    "claims against the evidence. You only request a revision for real problems."
)


def critic(state: WorkflowState) -> WorkflowState:
    prompt = f"""Topic: {state.query}

Research findings (the evidence):
{state.findings.model_dump_json(indent=2)}

Draft brief to review:
{state.draft.model_dump_json(indent=2)}

Check the draft for:
1. Claims, numbers or names NOT supported by the findings
2. More than 2 competitors, or competitors not named in the findings
3. Missing information that is not acknowledged
4. Vague or padded wording
5. Competitor descriptions that are identical, generic, or not specific to the company
6. Wording stronger than the evidence (hype, superlatives, unsupported trends)
7. Market-level claims wrongly attributed to a single company

Set approved=true if the draft is acceptable (minor style issues do not count).
Set approved=false only for real problems, and list each one specifically in "issues"."""

    state.feedback = generate_structured(prompt, CriticFeedback, system=CRITIC_SYSTEM)
    return state


# --------------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------------
def orchestrator(query: str, on_step: StepCallback = None) -> WorkflowState:
    """Receive the query and run: Researcher -> Analyst -> Critic -> (one revision)."""
    query = query.strip()
    if not query:
        raise ValueError("Please enter a company or industry to research.")

    state = WorkflowState(query=query)

    scoper(state)
    if state.scope.kind == "not_business":
        state.stopped_reason = state.scope.message
        _step(
            state, "Orchestrator: input is not a company or industry, stopping", on_step
        )
        return state
    _step(state, f"Orchestrator: interpreted as {state.scope.interpretation}", on_step)

    researcher(state)
    _step(state, "Researcher: findings collected", on_step)

    analyst(state)
    _step(state, "Analyst: draft written", on_step)

    if not state.findings.findings:
        _step(state, "Critic: skipped (no evidence to review)", on_step)
        return state

    critic(state)
    verdict = "approved" if state.feedback.approved else "revision requested"
    _step(state, f"Critic: {verdict}", on_step)

    if state.feedback.approved:
        state.final_brief = state.draft
    else:
        analyst(state, revise=True)  # at most one revision
        _step(state, "Analyst: draft revised", on_step)

    return state


# --------------------------------------------------------------------------
# Orchestrator: scope check (runs before the workflow starts)
# --------------------------------------------------------------------------
SCOPER_SYSTEM = (
    "You decide whether a user's input names a company or an industry/market "
    "that can be researched for a business brief. You are concise and prrenderecise."
)


def scoper(state: WorkflowState) -> WorkflowState:
    prompt = f"""User input: "{state.query}"

Classify the input as exactly one of:
- "company": a company, brand or organisation
- "industry": an industry, market or sector (e.g. "food delivery market in Nepal")
- "not_business": anything else (a river, animal, person, place, concept, gibberish)

Rules:
1. Business first. If the input could mean a company/brand/industry AND something
   else, choose the business reading whenever a widely known company, brand or
   industry matches the name. Example: "Amazon" -> company (Amazon.com Inc.),
   not the rainforest or the river.
2. If the name is mainly known as something non-business (e.g. "Nile" is a river)
   and you know of no widely known company or industry with that name, classify
   it as "not_business".
3. Do NOT reject a name just because you don't recognise it. If it plausibly looks
   like a company or brand (e.g. a local business), classify it as "company" and
   let the research step find out.
4. name: the short, clean name of the company or industry, without words like
   "analyze", "company" or "market research". Examples: "Amazon", "Apple",
   "Food Delivery Market in Nepal". For "not_business", repeat the input.
5. interpretation: one short phrase, e.g. "Amazon.com Inc. (global e-commerce and cloud company)".
6. search_query: an unambiguous web search query for the business reading, e.g.
   "Amazon.com Inc. company". For "not_business", repeat the input.
7. message: for "not_business" only, one or two sentences saying what the input
   is and asking for a company or industry, e.g. "'Nile' is a river in
   northeastern Africa, not a company or industry. Please enter a company or
   industry to research." If it is gibberish or unknown, write: "No company or
   industry found for '<input>'." Leave empty otherwise."""

    state.scope = generate_structured(prompt, QueryCheck, system=SCOPER_SYSTEM)
    return state
