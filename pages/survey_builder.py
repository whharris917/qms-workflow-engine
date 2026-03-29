"""Survey Builder — a self-modifying page (Phase E).

Demonstrates eigenform actions that reshape the page's own structure.
The user selects a topic, clicks Generate, and questions materialize
from the registry. Each generation adds new eigenforms to the page.
The structure persists across restarts.
"""

from engine.actionform import ActionForm
from engine.choiceform import ChoiceForm
from engine.textform import TextForm
from engine.pageform import PageForm
from engine.store import Store


# --- Question banks by topic ---

QUESTIONS = {
    "geography": [
        {"type": "text", "label": "What is the longest river in Africa?"},
        {"type": "choice", "label": "Which country has the most time zones?",
         "config": {"options": ["Russia", "USA", "France", "China"]}},
        {"type": "text", "label": "Name the smallest country by area."},
    ],
    "science": [
        {"type": "choice", "label": "What is the chemical symbol for gold?",
         "config": {"options": ["Au", "Ag", "Fe", "Cu"]}},
        {"type": "text", "label": "What force keeps planets in orbit?"},
        {"type": "choice", "label": "Which gas makes up most of Earth's atmosphere?",
         "config": {"options": ["Oxygen", "Nitrogen", "Carbon Dioxide", "Argon"]}},
    ],
    "history": [
        {"type": "text", "label": "In what year did the Berlin Wall fall?"},
        {"type": "choice", "label": "Who was the first Emperor of Rome?",
         "config": {"options": ["Julius Caesar", "Augustus", "Nero", "Caligula"]}},
        {"type": "text", "label": "What ancient civilization built Machu Picchu?"},
    ],
}

# Track how many questions have been generated (for unique keys)
_counter_key = "__survey_counter"


def generate_questions(context: dict, store: Store, scope: str) -> dict:
    """Generate questions for the selected topic via structural actions."""
    topic = context.get("topic")
    if not topic or topic not in QUESTIONS:
        return {"message": f"Unknown topic: {topic}"}

    # Get and increment counter for unique keys
    counter = store.get(scope, _counter_key) or 0

    questions = QUESTIONS[topic]
    actions = []
    for i, q in enumerate(questions):
        key = f"q_{counter + i}"
        action = {
            "action": "add_eigenform",
            "type": q["type"],
            "key": key,
            "label": f"Q{counter + i + 1}: {q['label']}",
        }
        if "config" in q:
            action["config"] = q["config"]
        actions.append(action)

    # Update counter
    store.set(scope, _counter_key, counter + len(questions))

    return {
        "message": f"Added {len(questions)} {topic} questions.",
        "structural_actions": actions,
    }


definition = PageForm(
    key="survey-builder",
    label="Survey Builder",
    instruction="Select a topic and generate questions. Answer them, then generate more!",
    mutable_structure=True,
    eigenforms=[
        ChoiceForm(key="topic", label="Topic",
                   instruction="Choose a topic to generate questions for.",
                   options=list(QUESTIONS.keys())),
        ActionForm(key="generate", label="Generate Questions",
                   instruction="Create questions for the selected topic.",
                   action_label="Generate",
                   action_fn=generate_questions,
                   depends_on=["topic"],
                   precondition_fn=lambda ctx: ctx.get("topic") is not None,
                   precondition_message="Select a topic first."),
    ],
)
