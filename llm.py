import os
import time
from typing import Optional, Type, TypeVar

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

load_dotenv()

T = TypeVar("T", bound=BaseModel)

RETRY_DELAYS = [2, 5, 10]  # seconds to wait before each retry
RETRYABLE_CODES = {429, 500, 503, 504}


class LLMError(Exception):
    """Raised when the LLM cannot return a valid response."""


def _models() -> list[str]:
    main = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    fallback = os.getenv("GEMINI_FALLBACK_MODEL")
    return [m for m in (main, fallback) if m]


def generate_structured(
    prompt: str, schema: Type[T], system: Optional[str] = None
) -> T:
    """Call Gemini and return a validated Pydantic object of type `schema`."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise LLMError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key."
        )

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0.3,
    )

    last_error: Optional[Exception] = None

    for model in _models():
        for delay in [0] + RETRY_DELAYS:
            if delay:
                time.sleep(delay)
            try:
                response = client.models.generate_content(
                    model=model, contents=prompt, config=config
                )
                if not response.text:
                    last_error = LLMError("Empty response from model.")
                    continue
                return schema.model_validate_json(response.text)
            except errors.APIError as e:
                last_error = e
                if e.code in RETRYABLE_CODES:
                    continue  # wait and retry the same model
                break  # e.g. 404 / 403: retrying won't help, try the next model
            except (ValidationError, ValueError) as e:
                last_error = e
                continue  # malformed JSON: try again

    raise LLMError(f"LLM call failed after retries and fallback: {last_error}")
