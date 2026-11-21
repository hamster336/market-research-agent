# does search work? and which backend?

from ddgs import DDGS

queries = ["food delivery market Nepal", "Foodmandu Nepal", "python"]
# Using 3 different types of queries: broad one, specific one and a control

for q in queries:
    for backend in ["auto", "duckduckgo", "bing", "brave"]:
        try:
            results = DDGS().text(q, max_results=3, backend=backend)
            print(f"OK   [{backend}] {q!r}: {len(results)} results")
            if results:
                print("     ", results[0]["title"], "-", results[0]["href"])
        except Exception as e:
            print(f"FAIL [{backend}] {q!r}: {e}")