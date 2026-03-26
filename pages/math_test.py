"""Math Test — five questions testing arithmetic and instruction-following."""

from engine.chain import ChainForm
from engine.choice import ChoiceForm
from engine.eigenforms import CheckboxForm, TextForm
from engine.page import PageForm
from engine.tab import TabForm


definition = PageForm(key="math-test", label="Math Test", instruction="Answer each question.", eigenforms=[
    TextForm(key="q1", label="Question 1", instruction="What is 2 + 2?"),
    ChoiceForm(key="q2", label="Question 2", instruction="What is 7 * 8?",
               options=["49", "54", "56", "63"]),
    CheckboxForm(key="q3", label="Question 3", instruction="Which of the following are prime numbers?",
                 items=["2", "9", "13", "15", "23"]),
    TabForm(key="q4", label="Question 4", instruction="Follow the instructions on each tab. You will need to jump between tabs.", tabs={
        "tab-1": TextForm(key="step-1", label="Step 1",
                          instruction="Pick any number between 1 and 10. Enter it here, then go to Tab 3."),
        "tab-2": TextForm(key="step-2", label="Step 2",
                          instruction="Take the number from Tab 4 and multiply it by 2. Enter the result here, then go to Tab 6."),
        "tab-3": ChoiceForm(key="step-3", label="Step 3",
                            instruction="Choose the third number in this list. Then go to Tab 5.",
                            options=["11", "22", "33", "44", "55"]),
        "tab-4": TextForm(key="step-4", label="Step 4",
                          instruction="Add your number from Tab 1 to the number you chose on Tab 3. Enter the sum here, then go to Tab 2."),
        "tab-5": ChoiceForm(key="step-5", label="Step 5",
                            instruction="Which of these is the correct sequence of tabs you visited before arriving here? Then go to Tab 4.",
                            options=["1, 2, 3", "1, 5, 3", "1, 3", "3, 1"]),
        "tab-6": TextForm(key="step-6", label="Step 6",
                          instruction="Final answer: subtract 33 from your Tab 2 result. Enter the answer here."),
    }),
    ChainForm(key="q5", label="Question 5", instruction="A sequence of clues. Each step unlocks the next.", steps=[
        ChoiceForm(key="clue-1", label="Clue 1",
                   instruction="I am a two-digit number. My digits sum to 10 and their product is 21. What am I?",
                   options=["37", "46", "55", "73"]),
        TextForm(key="clue-2", label="Clue 2",
                 instruction="Take your answer from Clue 1. Reverse its digits. What is the difference between the original and the reversed number?"),
        CheckboxForm(key="clue-3", label="Clue 3",
                     instruction="Select every number below that evenly divides your answer from Clue 2.",
                     items=["2", "3", "6", "9", "12", "18", "36"]),
        TextForm(key="clue-4", label="Clue 4",
                 instruction="How many items did you select in Clue 3? Raise that number to the power of itself. What do you get?"),
    ]),
])
