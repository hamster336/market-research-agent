from llm import generate_structured
from models import ResearchFindings
from search import search_web

results, source = search_web("food delivery market Nepal")
print(f"Search source: {source}, {len(results)} results")
for r in results[:3]:
    print(" -", r["title"], "|", r["url"])

snippets = "\n".join(f"{r['title']} ({r['url']}): {r['snippet']}" for r in results)
out = generate_structured(
    prompt=f"Extract up to 3 facts from these search results.\n\n{snippets}",
    schema=ResearchFindings,
)
print(out.model_dump_json(indent=2))
