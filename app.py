import streamlit as st

from agents import orchestrator
from llm import LLMError
from models import WorkflowState

st.set_page_config(page_title="InsightCrew", page_icon="🔍", layout="centered")
st.title("🔍 InsightCrew")
st.caption("Multi-agent market research briefs in minutes.")


def brief_to_markdown(state: WorkflowState) -> str:
    b = state.final_brief
    origin = {"web": "live web search", "sample": "illustrative sample data"}.get(
        state.data_source, "no data found"
    )
    lines = [
        f"# Market Research Brief: {state.query}",
        "",
        f"_Data source: {origin}_",
        "",
        "## Summary",
        b.summary,
        "",
        "## Competitors",
    ]
    lines += [f"- **{c.name}**: {c.description}" for c in b.competitors] or [
        "- None identified"
    ]
    lines += ["", "## Key observations"] + (
        [f"- {o}" for o in b.key_observations] or ["- None available"]
    )
    lines += ["", "## Sources"] + (
        [f"- {s}" for s in b.sources] or ["- None available"]
    )
    lines += ["", "## Missing information"] + (
        [f"- {m}" for m in b.missing_information] or ["- None reported"]
    )
    return "\n".join(lines)


def render(state: WorkflowState) -> None:
    st.caption(f"Interpreted as: {state.scope.interpretation}")

    b = state.final_brief

    if state.data_source == "sample":
        st.warning(
            "Live search was unavailable. This brief uses illustrative sample data and is not verified."
        )
    elif state.data_source == "none":
        st.warning(
            "No search results were found for this topic, so no brief could be generated."
        )

    st.subheader("Summary")
    st.write(b.summary)

    st.subheader("Competitors")
    if b.competitors:
        for c in b.competitors:
            st.markdown(f"**{c.name}**: {c.description}")
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
            st.markdown(f"- {s}")
    else:
        st.write("No sources available.")

    st.subheader("Missing information")
    if b.missing_information:
        for m in b.missing_information:
            st.markdown(f"- {m}")
    else:
        st.write("No missing information reported.")

    st.download_button(
        "Download brief (Markdown)",
        brief_to_markdown(state),
        file_name="brief.md",
        mime="text/markdown",
    )

    with st.expander("How this brief was made"):
        findings = state.findings.findings
        n_facts = len(findings)
        n_sources = len({f.source_url for f in findings})
        origin = {"web": "live web search", "sample": "illustrative sample data"}.get(
            state.data_source, "no data found"
        )

        st.markdown(
            f"**1. Orchestrator:** interpreted the input as *{state.scope.interpretation}* "
            f"({state.scope.kind})."
        )
        st.markdown(
            f"**2. Researcher:** collected {n_facts} facts from {n_sources} sources ({origin})."
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


# ---- session state defaults ----
for key, default in {
    "running": False,
    "pending_query": "",
    "state": None,
    "error": None,  # (kind, message) or None
}.items():
    st.session_state.setdefault(key, default)


def start_research():
    """Runs when the form is submitted (button click or Enter)."""
    st.session_state.running = True
    st.session_state.pending_query = st.session_state.query_input
    st.session_state.state = None  # hide the previous brief while running
    st.session_state.error = None


with st.form("research_form"):
    st.text_input(
        "Company or industry",
        key="query_input",
        placeholder="e.g. Analyze the food delivery market in Nepal",
        disabled=st.session_state.running,
    )
    st.form_submit_button(
        "Start research",
        type="primary",
        disabled=st.session_state.running,
        on_click=start_research,
    )

# ---- run the workflow (the form is already disabled at this point) ----
if st.session_state.running:
    query = st.session_state.pending_query.strip()
    try:
        if not query:
            st.session_state.error = (
                "warning",
                "Please enter a company or industry first.",
            )
        else:
            with st.status("Running the research workflow...", expanded=True) as status:
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
    st.rerun()  # re-enable the form and show the result

# ---- show errors / results ----
if st.session_state.error:
    kind, message = st.session_state.error
    (st.warning if kind == "warning" else st.error)(message)

if st.session_state.state:
    s = st.session_state.state
    if s.stopped_reason:
        st.info(s.stopped_reason)
    else:
        render(s)
