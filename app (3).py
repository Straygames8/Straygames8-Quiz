import gradio as gr
from openai import OpenAI
import os
from datetime import datetime
import time
import json
import random
import hashlib
from pymongo import MongoClient


# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize MongoDB client
mongo_uri = os.getenv("MONGODB_URI")
if not mongo_uri:
    raise ValueError("MONGODB_URI environment variable is not set")

# Initialize MongoDB client
mongo_client = MongoClient(mongo_uri)
db = mongo_client["quiz_game"]
session_collection = db["sessions"]

class QuizGame:
    def __init__(self):
        self.region = ""
        self.age_group = ""
        self.general_topic = ""
        self.sub_topic = ""
        self.difficulty = ""
        self.question_type = ""
        self.questions = []
        self.user_answers = []
        self.session_data = {}
        self.start_time = 0
        self.score = 0
        self.total_questions = 0
        self.current_options = []
        self.correct_answer = ""
        self.message_history = [
            {"role": "system", "content": "You are a quiz question generator. Generate questions in the following formats:\n\nFor Multiple Choice:\nQuestion: [Question text]\nA) [Option A]\nB) [Option B]\nC) [Option C]\nD) [Option D]\nCorrect: [Letter of correct answer]\n\nFor True/False:\nQuestion: [Question text]\nA) True\nB) False\nCorrect: [A or B]\n\nEnsure there are always exactly 4 options for Multiple Choice, and 2 options for True/False."}
        ]
        self.question_count = 0
        self.question_history = []

    def trim_message_history(self, max_messages=10):
        # Keep the system message and the last max_messages
        if len(self.message_history) > max_messages + 1:
            self.message_history = [self.message_history[0]] + self.message_history[-(max_messages):]

    def generate_topics(self):
        general_topics = ["Science", "History", "Entertainment", "Sports", "Literature", "Computer Science"]
        sub_topics = {
            "Science": ["Biology", "Astronomy", "Chemistry"],
            "History": ["Ancient", "Modern", "World Wars"],
            "Entertainment": ["Movies", "Music", "TV Shows"],
            "Sports": ["Football", "Basketball", "Tennis"],
            "Literature": ["Classic", "Contemporary", "Poetry"],
            "Computer Science": ["OS", "DBMS", "System Design", "COA", "CN"]
        }
        difficulties = ["Easy", "Medium", "Hard"]
        return general_topics, sub_topics, difficulties

    def generate_question(self):
        self.question_count += 1
        
        self.message_history.append({
            "role": "user",
            "content": f"Generate 1 unique {self.question_type} question about {self.sub_topic} in {self.general_topic} at {self.difficulty} difficulty level. This is question number {self.question_count}, so make sure it's different from all previous questions."
        })
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=self.message_history,
            temperature=1.0
        )
        
        question = response.choices[0].message.content.strip()
        
        self.message_history.append({
            "role": "assistant",
            "content": question
        })
        
        self.message_history.append({
            "role": "user",
            "content": "This question has been used. Please generate a different question next time."
        })
        
        self.questions.append(question)
        self.trim_message_history()
        return self.format_question(question)

    def format_question(self, question):
        lines = question.split('\n')
        formatted_question = lines[0].replace("Question: ", "")
        options = lines[1:-1]
        correct_line = lines[-1]
        self.correct_answer = next(option for option in options if option.startswith(correct_line.replace("Correct: ", "")))
        self.current_options = [option[3:].strip() for option in options]
        return formatted_question

    def check_answer(self, user_answer):
        self.total_questions += 1
        is_correct = user_answer.strip().lower() == self.correct_answer[3:].strip().lower()
        if is_correct:
            self.score += 1
        self.question_history.append({
            "question": self.questions[-1],
            "correct_answer": self.correct_answer[3:].strip(),
            "user_answer": user_answer.strip()
        })
        return is_correct

    def skip_question(self):
        self.total_questions += 1
        self.question_history.append({
            "question": self.questions[-1],
            "correct_answer": self.correct_answer[3:].strip(),
            "user_answer": "Skipped"
        })
        self.user_answers.append({
            "question": self.questions[-1],
            "user_answer": "Skipped",
            "correct_answer": self.correct_answer,
            "is_correct": False,
            "time_taken": 30.0
        })
        return self.generate_question()

    def get_score(self):
        score_text = f"Score: {self.score}/{self.total_questions}\n\n"
        for i, qa in enumerate(self.question_history, 1):
            score_text += f"Question {i}: {qa['question']}\n"
            score_text += f"Correct answer = {qa['correct_answer']}, Your answer = {qa['user_answer']}\n\n"
        return score_text

    def end_session(self):
        self.session_data = {
            "region": self.region,
            "age_group": self.age_group,
            "general_topic": self.general_topic,
            "sub_topic": self.sub_topic,
            "difficulty": self.difficulty,
            "question_history": self.question_history,
            "score": self.score,
            "total_questions": self.total_questions,
            "timestamp": datetime.now().isoformat()
        }
        
        # Save to MongoDB
        session_collection.insert_one(self.session_data)
        
        return f"Session ended. Final score: {self.score}/{self.total_questions}. Data has been collected and saved to MongoDB."

game = QuizGame()

def set_user_info(region, age_group):
    game.region = region
    game.age_group = age_group
    general_topics, _, _ = game.generate_topics()
    return gr.update(choices=general_topics, visible=True), gr.update(visible=True)

def set_general_topic(general_topic):
    game.general_topic = general_topic
    _, sub_topics, _ = game.generate_topics()
    return gr.update(choices=sub_topics[general_topic], visible=True)

def set_sub_topic(sub_topic):
    game.sub_topic = sub_topic
    _, _, difficulties = game.generate_topics()
    return gr.update(choices=difficulties, visible=True), gr.update(choices=["Multiple Choice", "True/False"], visible=True)

def set_difficulty_and_type(difficulty, question_type):
    game.difficulty = difficulty
    game.question_type = question_type
    return gr.update(visible=True)

def start_quiz():
    game.score = 0
    game.total_questions = 0
    question = game.generate_question()
    game.start_time = time.time()
    
    if game.question_type == "Multiple Choice":
        return (gr.update(value=question, visible=True), 
                gr.update(value=game.current_options[0], visible=True),
                gr.update(value=game.current_options[1], visible=True),
                gr.update(value=game.current_options[2], visible=True),
                gr.update(value=game.current_options[3], visible=True),
                gr.update(visible=False),  # Hide True/False buttons
                gr.update(visible=False),
                gr.update(visible=True), 
                gr.update(value=game.get_score(), visible=True),
                gr.update(value="0.00 seconds", visible=True))
    else:  # True/False
        return (gr.update(value=question, visible=True), 
                gr.update(visible=False),  # Hide Multiple Choice buttons
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(value="True", visible=True),
                gr.update(value="False", visible=True),
                gr.update(visible=True), 
                gr.update(value=game.get_score(), visible=True),
                gr.update(value="0.00 seconds", visible=True))

def submit_answer(answer):
    end_time = time.time()
    time_taken = end_time - game.start_time
    
    is_correct = game.check_answer(answer)
    
    new_question = game.generate_question()
    game.start_time = time.time()
    
    if game.question_type == "Multiple Choice":
        return (gr.update(value=new_question), 
                gr.update(value=game.current_options[0]),
                gr.update(value=game.current_options[1]),
                gr.update(value=game.current_options[2]),
                gr.update(value=game.current_options[3]),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(value=game.get_score()),
                gr.update(value="0.00 seconds"))
    else:  # True/False
        return (gr.update(value=new_question), 
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(value="True"),
                gr.update(value="False"),
                gr.update(value=game.get_score()),
                gr.update(value="0.00 seconds"))

def skip_question():
    new_question = game.skip_question()
    game.start_time = time.time()
    
    if game.question_type == "Multiple Choice":
        return (gr.update(value=new_question), 
                gr.update(value=game.current_options[0]),
                gr.update(value=game.current_options[1]),
                gr.update(value=game.current_options[2]),
                gr.update(value=game.current_options[3]),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(value=game.get_score()),
                gr.update(value="0.00 seconds"))
    else:  # True/False
        return (gr.update(value=new_question), 
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(value="True"),
                gr.update(value="False"),
                gr.update(value=game.get_score()),
                gr.update(value="0.00 seconds"))

def update_timer():
    if game.start_time > 0:
        elapsed_time = time.time() - game.start_time
        if elapsed_time >= 30:
            return skip_question()
        return [gr.update()] * 9 + [gr.update(value=f"{elapsed_time:.2f} seconds")]
    return [gr.update()] * 9 + [gr.update(value="0.00 seconds")]

with gr.Blocks(gr.themes.Monochrome()) as ui:
    gr.Markdown("# AI-Powered Quiz Game")
    
    with gr.Row():
        with gr.Column(scale=1):
            region = gr.Textbox(label="Region")
            age_group = gr.Textbox(label="Age Group")
            submit_info = gr.Button("Submit")
            
            general_topic = gr.Radio(label="Select General Topic", visible=False)
            sub_topic = gr.Radio(label="Select Sub Topic", visible=False)
            difficulty = gr.Radio(label="Select Difficulty", visible=False)
            question_type = gr.Radio(label="Select Question Type", visible=False)
            start_button = gr.Button("Start Quiz", visible=False)
            
            end_button = gr.Button("End Quiz", visible=False)
        
        with gr.Column(scale=2):
            question = gr.Textbox(label="Question", visible=False)
            with gr.Row():
                option_a = gr.Button("A", visible=False)
                option_b = gr.Button("B", visible=False)
                option_c = gr.Button("C", visible=False)
                option_d = gr.Button("D", visible=False)
            with gr.Row():
                true_button = gr.Button("True", visible=False)
                false_button = gr.Button("False", visible=False)
            score = gr.Textbox(label="Score and Question History", visible=False)
            timer = gr.Textbox(label="Timer", visible=False)
            result = gr.Textbox(label="Result")

    submit_info.click(set_user_info, inputs=[region, age_group], outputs=[general_topic, start_button])
    general_topic.change(set_general_topic, inputs=[general_topic], outputs=[sub_topic])
    sub_topic.change(set_sub_topic, inputs=[sub_topic], outputs=[difficulty, question_type])
    difficulty.change(set_difficulty_and_type, inputs=[difficulty, question_type], outputs=[start_button])
    question_type.change(set_difficulty_and_type, inputs=[difficulty, question_type], outputs=[start_button])
    start_button.click(start_quiz, outputs=[question, option_a, option_b, option_c, option_d, true_button, false_button, end_button, score, timer])
    
    for option in [option_a, option_b, option_c, option_d, true_button, false_button]:
        option.click(submit_answer, inputs=[option], outputs=[question, option_a, option_b, option_c, option_d, true_button, false_button, score, timer])
    
    end_button.click(game.end_session, outputs=[result])

    ui.load(update_timer, outputs=[question, option_a, option_b, option_c, option_d, true_button, false_button, score, timer], every=0.1)

ui.launch()

