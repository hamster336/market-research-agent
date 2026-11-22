from fpdf import FPDF
from fpdf.enums import WrapMode, XPos, YPos
import re

from models import WorkflowState

# The built-in PDF fonts only support Latin-1, so swap common "smart" characters
# for plain equivalents instead of letting them crash or turn into "?".
_REPLACEMENTS = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u2026": "...",
    "\u2022": "-",
    "\u00a0": " ",
    "\u2192": "->",
}


def _clean(text: str) -> str:
    for old, new in _REPLACEMENTS.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "replace").decode("latin-1")


def build_pdf(state: WorkflowState) -> bytes:
    b = state.final_brief
    origin = {"web": "live web search", "sample": "illustrative sample data"}.get(
        state.data_source, "no data found"
    )

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    def heading(text: str, size: int = 13) -> None:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", size)
        pdf.cell(0, 8, _clean(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def body(text: str, style: str = "", wrap: WrapMode = WrapMode.WORD) -> None:
        pdf.set_font("Helvetica", style, 11)
        pdf.multi_cell(
            0, 6, _clean(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT, wrapmode=wrap
        )

    def bullets(items: list[str], empty: str, wrap: WrapMode = WrapMode.WORD) -> None:
        for item in items or [empty]:
            body(f"- {item}", wrap=wrap)

    # Title block
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "Market Research Brief", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(
        0,
        7,
        _clean(state.scope.name if state.scope else state.query),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    if state.scope:
        body(f"Interpreted as: {state.scope.interpretation}", style="I")
    body(f"Data source: {origin}", style="I")

    heading("Summary")
    body(b.summary)

    heading("Competitors")
    bullets([f"{c.name}: {c.description}" for c in b.competitors], "None identified")

    heading("Key observations")
    bullets(b.key_observations, "None available")

    heading("Sources")
    bullets(
        b.sources, "None available", wrap=WrapMode.CHAR
    )  # long URLs need char wrapping

    heading("Missing information")
    bullets(b.missing_information, "None reported")

    return bytes(pdf.output())


def pdf_filename(state: WorkflowState) -> str:
    name = state.scope.name if state.scope and state.scope.name else state.query
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60].strip("-")
    return f"{slug or 'market'}-market-research-brief.pdf"
