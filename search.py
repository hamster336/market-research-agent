import logging
import re
import time

from ddgs import DDGS

logger = logging.getLogger("search")

BACKENDS = ["bing", "auto"]
RETRY_PAUSE = 1.5  # seconds between attempts

# Clearly labelled fallback, used only for the food-delivery demo topic.
SAMPLE_RESULTS = [
    {
        "title": "[SAMPLE DATA] Online food delivery overview",
        "url": "sample://illustrative-data",
        "snippet": "ILLUSTRATIVE SAMPLE, NOT VERIFIED: Online food delivery in Nepal is "
        "concentrated in Kathmandu Valley and a few other major cities.",
    },
    {
        "title": "[SAMPLE DATA] Competitor landscape",
        "url": "sample://illustrative-data",
        "snippet": "ILLUSTRATIVE SAMPLE, NOT VERIFIED: Foodmandu and Pathao Food are "
        "examples of food delivery platforms operating in Nepal.",
    },
    {
        "title": "[SAMPLE DATA] Market drivers",
        "url": "sample://illustrative-data",
        "snippet": "ILLUSTRATIVE SAMPLE, NOT VERIFIED: Smartphone adoption and digital "
        "payments are commonly cited drivers of delivery growth.",
    },
]


def _clean_query(query: str) -> str:
    """'Analyze the food delivery market in Nepal' -> 'food delivery market in Nepal'."""
    cleaned = re.sub(
        r"^\s*(please\s+)?(analy[sz]e|research|study|investigate|tell me about)\s+(the\s+)?",
        "",
        query,
        flags=re.IGNORECASE,
    )
    return cleaned.strip() or query.strip()


def _sample_applies(query: str) -> bool:
    return "food delivery" in query.lower()


def search_web(query: str, max_results: int = 6) -> tuple[list[dict], str]:
    """Return (results, source). source is 'web', 'sample' or 'none'. Never raises."""
    variants = [_clean_query(query)]
    if query.strip().lower() != variants[0].lower():
        variants.append(query.strip())

    for variant in variants:
        for backend in BACKENDS:
            for attempt in range(2):
                try:
                    raw = DDGS().text(variant, max_results=max_results, backend=backend)
                    results = [
                        {
                            "title": r.get("title", ""),
                            "url": r.get("href", ""),
                            "snippet": r.get("body", ""),
                        }
                        for r in raw
                        if r.get("href")
                    ]
                    if results:
                        return results, "web"
                except Exception as e:
                    logger.warning(
                        "search failed (query=%r, backend=%s, attempt=%d): %s",
                        variant,
                        backend,
                        attempt + 1,
                        e,
                    )
                if attempt == 0:
                    time.sleep(RETRY_PAUSE)

    if _sample_applies(query):
        return SAMPLE_RESULTS, "sample"
    return [], "none"


ANGLES = ["", " competitors", " market size and growth"]


def search_topic(query: str, per_query: int = 5) -> tuple[list[dict], str]:
    """Search the topic from several angles and merge unique results."""
    merged, seen = [], set()

    for angle in ANGLES:
        results, source = search_web(query + angle, max_results=per_query)
        if source == "web":
            for r in results:
                if r["url"] not in seen:
                    seen.add(r["url"])
                    merged.append(r)
        time.sleep(0.5)  # be gentle with the search backend

    if merged:
        return merged, "web"
    if _sample_applies(query):
        return SAMPLE_RESULTS, "sample"
    return [], "none"
