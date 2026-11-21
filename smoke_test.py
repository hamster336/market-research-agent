# checks whether the LLM is working or not: 
# 1- valid API key
# 2- properly installed google-genai package
# 3- model name exists and is availaible from the key
# 4- search reaches google

import os
from dotenv import load_dotenv

load_dotenv()

# 1. LLM check
from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
r = client.models.generate_content(
    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    contents="Reply with the single word: ok",
)
print("LLM:", r.text)

# 2. Search check
from ddgs import DDGS

for item in DDGS().text("food delivery market Nepal", max_results=3):
    print("SEARCH:", item["title"], "-", item["href"])
