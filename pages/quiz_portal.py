"""Quiz Portal — three quizzes (Geography, Science, History) in a TabForm, five questions each."""

from engine.choice import ChoiceForm
from engine.eigenforms import CheckboxForm, TextForm
from engine.page import PageForm
from engine.score import ScoreForm
from engine.tab import TabForm


geography = TabForm(key="geography", label="Geography Quiz", instruction="Five geography questions.", tabs={
    "q1": ChoiceForm(key="geo-q1", label="Q1",
                     instruction="What is the longest river in the world?",
                     options=["Amazon", "Nile", "Yangtze", "Mississippi"]),
    "q2": ChoiceForm(key="geo-q2", label="Q2",
                     instruction="Which country has the most time zones?",
                     options=["Russia", "USA", "France", "China"]),
    "q3": CheckboxForm(key="geo-q3", label="Q3",
                       instruction="Select all countries that border the Mediterranean Sea.",
                       items=["Spain", "Germany", "Egypt", "Turkey", "Brazil", "Italy"]),
    "q4": TextForm(key="geo-q4", label="Q4",
                   instruction="What is the capital of Australia?"),
    "q5": ChoiceForm(key="geo-q5", label="Q5",
                     instruction="Which desert is the largest by area?",
                     options=["Sahara", "Arabian", "Gobi", "Antarctic"]),
    "results": ScoreForm(key="geo-score", label="Results", instruction="Geography Quiz results.", answer_key={
        "geo-q1": "Nile",
        "geo-q2": "France",
        "geo-q3": {"Spain": True, "Germany": False, "Egypt": True, "Turkey": True, "Brazil": False, "Italy": True},
        "geo-q4": "Canberra",
        "geo-q5": "Antarctic",
    }),
})

science = TabForm(key="science", label="Science Quiz", instruction="Five science questions.", tabs={
    "q1": ChoiceForm(key="sci-q1", label="Q1",
                     instruction="What is the chemical symbol for gold?",
                     options=["Go", "Gd", "Au", "Ag"]),
    "q2": TextForm(key="sci-q2", label="Q2",
                   instruction="How many bones are in the adult human body?"),
    "q3": CheckboxForm(key="sci-q3", label="Q3",
                       instruction="Select all that are noble gases.",
                       items=["Helium", "Nitrogen", "Neon", "Oxygen", "Argon", "Krypton"]),
    "q4": ChoiceForm(key="sci-q4", label="Q4",
                     instruction="What planet has the most moons?",
                     options=["Jupiter", "Saturn", "Uranus", "Neptune"]),
    "q5": TextForm(key="sci-q5", label="Q5",
                   instruction="What force keeps planets in orbit around the Sun?"),
    "results": ScoreForm(key="sci-score", label="Results", instruction="Science Quiz results.", answer_key={
        "sci-q1": "Au",
        "sci-q2": "206",
        "sci-q3": {"Helium": True, "Nitrogen": False, "Neon": True, "Oxygen": False, "Argon": True, "Krypton": True},
        "sci-q4": "Saturn",
        "sci-q5": "gravity",
    }),
})

history = TabForm(key="history", label="History Quiz", instruction="Five history questions.", tabs={
    "q1": ChoiceForm(key="hist-q1", label="Q1",
                     instruction="In what year did the Berlin Wall fall?",
                     options=["1987", "1989", "1991", "1993"]),
    "q2": TextForm(key="hist-q2", label="Q2",
                   instruction="Who was the first Emperor of Rome?"),
    "q3": CheckboxForm(key="hist-q3", label="Q3",
                       instruction="Select all events that occurred in the 20th century.",
                       items=["French Revolution", "Moon Landing", "World War I", "Printing Press Invention", "Fall of Constantinople", "Russian Revolution"]),
    "q4": ChoiceForm(key="hist-q4", label="Q4",
                     instruction="Which civilization built Machu Picchu?",
                     options=["Maya", "Aztec", "Inca", "Olmec"]),
    "q5": TextForm(key="hist-q5", label="Q5",
                   instruction="What treaty ended World War I?"),
    "results": ScoreForm(key="hist-score", label="Results", instruction="History Quiz results.", answer_key={
        "hist-q1": "1989",
        "hist-q2": "Augustus",
        "hist-q3": {"French Revolution": False, "Moon Landing": True, "World War I": True, "Printing Press Invention": False, "Fall of Constantinople": False, "Russian Revolution": True},
        "hist-q4": "Inca",
        "hist-q5": "Treaty of Versailles",
    }),
})

quizzes = TabForm(key="quizzes", label="Quizzes", instruction="Pick a quiz.", tabs={
    "geography": geography,
    "science": science,
    "history": history,
})

definition = PageForm(key="quiz-portal", label="Quiz Portal",
                      instruction="Three quizzes. Complete all tabs in each to finish.",
                      eigenforms=[quizzes])
