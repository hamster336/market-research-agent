# InsightCrew

InsightCrew is a Streamlit web app that turns a company or industry name into a short market research brief. Four roles (Orchestrator, Researcher, Analyst, Critic) run in sequence and pass structured data to each other.

Example input: `Analyze the food delivery market in Nepal`

## How it works

```
Input -> Orchestrator -> Researcher -> Analyst (draft) -> Critic
                                            ^                |
                                            +-- one revision-+  (only if needed)
                                                             |
                                                     Final brief + PDF
```

| Role         | What it does                                                                                                                                                             |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Orchestrator | Receives the query, checks whether it names a company or industry (for example "Amazon" is treated as the company, "Nile" is rejected as a river), and runs the workflow |
| Researcher   | Searches the web from several angles, finds the main competitors, and extracts facts with their source URLs                                                              |
| Analyst      | Writes the brief using only the researcher's findings                                                                                                                    |
| Critic       | Reviews the draft against the evidence and may request one revision                                                                                                      |

All roles use the same language model (Google Gemini). Data moves between roles as Pydantic models (see `models.py`), carried in a single `WorkflowState` object.

## The brief

- Summary of the topic
- Up to two competitors, if relevant
- Key observations
- Sources
- Missing information (anything the evidence did not cover)

The brief can be downloaded as a PDF.

## Setup

Requirements: Python 3.10 or newer and a free Gemini API key from [Google AI Studio](https://aistudio.google.com/).

1. Clone the repository and enter the folder:

   ```bash
   git clone <your-repository-url>
   cd <repository-folder>
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   ```

   - Windows: `.venv\Scripts\activate`
   - macOS / Linux: `source .venv/bin/activate`

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Create your environment file and add your key:
   ```bash
   cp .env.example .env        # Windows PowerShell: copy .env.example .env
   ```
   Then open `.env` and set `GEMINI_API_KEY`.

## Run

```bash
streamlit run app.py
```

Open http://localhost:8501, enter a company or industry, and click **Start research**.

## Configuration

| Variable                | Required | Description                                                     |
| ----------------------- | -------- | --------------------------------------------------------------- |
| `GEMINI_API_KEY`        | Yes      | Your Gemini API key                                             |
| `GEMINI_MODEL`          | No       | Main model name (set a current model if the default is retired) |
| `GEMINI_FALLBACK_MODEL` | No       | Used if the main model stays unavailable                        |

Model names change over time. If you see a "model not found" error, set `GEMINI_MODEL` to a current model from Google AI Studio.

No search API key is needed. Web search uses the `ddgs` package.

## Project structure

```
app.py          Streamlit interface
agents.py       Orchestrator, Researcher, Analyst and Critic
models.py       Pydantic models for the shared data
llm.py          Gemini wrapper (structured output, retries, fallback model)
search.py       Web search with retries and clearly labelled sample data
report.py       PDF generation
.env.example    Placeholder environment variables
sample_output/  Example brief
```

## Design notes

- **Structured handoffs.** Each role reads from and writes to one `WorkflowState` object, validated with Pydantic.
- **Rules enforced in code, not only in prompts.** Findings that cite a URL the search did not return are discarded, the source list is built from validated findings, and competitors are limited to two.
- **One revision at most.** If the Critic rejects the draft, the Analyst revises once and the workflow ends.
- **Evidence first.** The Researcher and Analyst are told to use only the findings. Anything not covered is reported under "Missing information".
- **Graceful failures.** LLM calls retry on temporary errors and fall back to a second model. If live search returns nothing, the app uses labelled sample data only for the food delivery demo topic, otherwise it reports that no evidence was found.

## Known limitations

- The Researcher reads search result snippets, not full pages, so detail (especially for competitors) can be thin. Gaps are reported in the brief.
- Search uses free, scraping-based backends that can fail temporarily. Competitor selection and coverage can vary between runs.
- Briefs are generated by a language model from limited evidence. Check important facts against the listed sources.

## Sample output

[`Daraz Nepal`](sample_output/daraz-nepal-market-research-brief.pdf)
[`Ikea`](sample_output/ikea-market-research-brief.pdf)
[`inDrive`](sample_output/indrive-market-research-brief.pdf)
[`Meesho`](sample_output/meesho-market-research-brief.pdf)
[`Fintech Nepal`](sample_output/fintech-market-in-nepal-market-research-brief.pdf)
[`Mitsubishi`](sample_output/mitsubishi-market-research-brief.pdf)
 