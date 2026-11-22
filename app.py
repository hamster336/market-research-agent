from urllib.parse import urlparse

import streamlit as st

from agents import orchestrator
from llm import LLMError
from models import WorkflowState
from report import build_pdf, pdf_filename

APP_NAME = "InsightCrew"
TAGLINE = "Four AI agents that research, write and review your market brief."
EXAMPLES = [
    "Analyze the food delivery market in Nepal",
    "Tesla",
    "Fintech market in Nepal",
]

st.markdown(
    """
<style>
.block-container {padding-top: 2.2rem; max-width: 860px;}
.hero h1 {
    font-size: 2.7rem; font-weight: 800; margin: 0; letter-spacing: -0.02em;
    background: linear-gradient(90deg, #6C8CFF, #B07CFF);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.hero p {opacity: .75; margin: .3rem 0 1rem 0; font-size: 1.05rem;}
.crew {display: flex; flex-wrap: wrap; gap: .5rem; margin-bottom: 1.2rem;}
.pill {
    border: 1px solid rgba(128,128,128,.35); border-radius: 999px;
    padding: .2rem .8rem; font-size: .82rem;
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    f'<div class="hero"><h1>🧭 {APP_NAME}</h1><p>{TAGLINE}</p></div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("How it works")
    st.markdown(
        "1. **Orchestrator** checks what you entered and starts the workflow\n"
        "2. **Researcher** searches the web and extracts facts with sources\n"
        "3. **Analyst** writes a short brief from those facts only\n"
        "4. **Critic** reviews it and can request one revision"
    )
    st.divider()
    st.caption(
        "Briefs are generated from web search snippets. Anything the evidence "
        "doesn't cover is listed under *Missing information*."
    )


# ---------------------------------------------------------------- rendering
def source_link(url: str) -> str:
    if url.startswith("http"):
        host = urlparse(url).netloc.removeprefix("www.")
        return f"[{host}]({url})"
    return url


def render(state: WorkflowState) -> None:
    b = state.final_brief
    findings = state.findings.findings
    n_sources = len({f.source_url for f in findings})
    origin = {"web": "Live web", "sample": "Sample data"}.get(state.data_source, "None")
    if state.feedback is None:
        verdict = "Skipped"
    else:
        verdict = "Approved" if state.feedback.approved else "Revised"

    st.divider()
    st.header(state.scope.name if state.scope else state.query)
    if state.scope:
        st.caption(f"Interpreted as: {state.scope.interpretation}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Facts gathered", len(findings))
    c2.metric("Sources", n_sources)
    c3.metric("Data", origin)
    c4.metric("Critic", verdict)

    if state.data_source == "sample":
        st.warning(
            "Live search was unavailable. This brief uses illustrative sample data and is not verified."
        )
    elif state.data_source == "none":
        st.warning(
            "No search results were found for this topic, so no brief could be generated."
        )

    st.subheader("Summary")
    with st.container(border=True):
        st.write(b.summary)

    st.subheader("Competitors")
    if b.competitors:
        cols = st.columns(len(b.competitors))
        for col, comp in zip(cols, b.competitors):
            with col.container(border=True):
                st.markdown(f"**{comp.name}**")
                st.write(comp.description)
    else:
        st.write("No competitors identified in the evidence.")

    st.subheader("Key observations")
    if b.key_observations:
        for o in b.key_observations:
            st.markdown(f"- {o}")
    else:
        st.write("No key observations available.")

    st.subheader("Sources")
    if b.sources:
        for s in b.sources:
            st.markdown(f"- {source_link(s)}")
    else:
        st.write("No sources available.")

    st.subheader("Missing information")
    if b.missing_information:
        for m in b.missing_information:
            st.markdown(f"- {m}")
    else:
        st.write("No missing information reported.")

    st.download_button(
        "Download brief (PDF)",
        data=build_pdf(state),
        file_name=pdf_filename(state),
        mime="application/pdf",
        type="primary",
    )

    with st.expander("How this brief was made"):
        if state.scope:
            st.markdown(
                f"**1. Orchestrator:** interpreted the input as *{state.scope.interpretation}* "
                f"({state.scope.kind})."
            )
        st.markdown(
            f"**2. Researcher:** collected {len(findings)} facts from {n_sources} sources ({origin.lower()})."
        )
        if not findings:
            st.markdown("**3. Analyst:** no usable evidence, so no draft was written.")
        else:
            st.markdown(
                "**3. Analyst:** wrote a draft brief using only those findings."
            )
            if state.feedback is None:
                st.markdown("**4. Critic:** skipped.")
            elif state.feedback.approved:
                st.markdown("**4. Critic:** reviewed the draft and approved it.")
            else:
                st.markdown("**4. Critic:** requested one revision:")
                for issue in state.feedback.issues:
                    st.markdown(f"- {issue}")
                st.markdown(
                    "**5. Analyst:** revised the draft to address those issues."
                )


# ---------------------------------------------------------------- input
for key, default in {
    "running": False,
    "pending_query": "",
    "state": None,
    "error": None,
}.items():
    st.session_state.setdefault(key, default)


def start_research():
    """Runs when the form is submitted (button click or Enter)."""
    st.session_state.running = True
    st.session_state.pending_query = st.session_state.query_input
    st.session_state.state = None
    st.session_state.error = None


def run_example(text: str):
    st.session_state.query_input = text
    start_research()


if st.session_state.running:
    # Locked copy shown while the crew is working: text visible, not editable.
    st.text_input(
        "Company or industry",
        value=st.session_state.pending_query,
        key="query_locked",
        disabled=True,
    )
    st.button("Start research", type="primary", disabled=True)
else:
    # Bring the last query back into the editable box after a run.
    st.session_state.setdefault("query_input", st.session_state.pending_query)
    with st.form("research_form", border=False):
        st.text_input(
            "Company or industry",
            key="query_input",
            placeholder="e.g. Analyze the food delivery market in Nepal",
        )
        st.form_submit_button(
            "Start research",
            type="primary",
            on_click=start_research,
        )

st.caption("Or try an example:")
ex_cols = st.columns(len(EXAMPLES))
for col, example in zip(ex_cols, EXAMPLES):
    col.button(
        example,
        key=f"example_{example}",
        on_click=run_example,
        args=(example,),
        disabled=st.session_state.running,
        use_container_width=True,
    )

# ---------------------------------------------------------------- run
if st.session_state.running:
    query = st.session_state.pending_query.strip()
    try:
        if not query:
            st.session_state.error = (
                "warning",
                "Please enter a company or industry first.",
            )
        else:
            with st.status("Your crew is working...", expanded=True) as status:
                state = orchestrator(
                    query, on_step=lambda name, s: st.write(f"✅ {name}")
                )
                status.update(
                    label="Research complete", state="complete", expanded=False
                )
            st.session_state.state = state
    except LLMError as e:
        st.session_state.error = (
            "error",
            f"The language model could not respond right now. Please try again in a moment.\n\nDetails: {e}",
        )
    except Exception as e:
        st.session_state.error = ("error", f"Something went wrong: {e}")
    finally:
        st.session_state.running = False
    st.rerun()

# ---------------------------------------------------------------- output
if st.session_state.error:
    kind, message = st.session_state.error
    (st.warning if kind == "warning" else st.error)(message)

if st.session_state.state:
    s = st.session_state.state
    if s.stopped_reason:
        st.info(s.stopped_reason, icon="🧭")
    else:
        render(s)
