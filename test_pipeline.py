from agents import orchestrator
from llm import LLMError

try:
    state = orchestrator(
        "Analyze the food delivery market in Nepal",
        on_step=lambda name, s: print("[done]", name),
    )
except LLMError as e:
    print("LLM error:", e)
else:
    print("\nData source:", state.data_source)
    print("Revised:", state.revised)
    if state.feedback and state.feedback.issues:
        print("Critic issues:", state.feedback.issues)
    print("\nFINAL BRIEF:")
    print(state.final_brief.model_dump_json(indent=2))
