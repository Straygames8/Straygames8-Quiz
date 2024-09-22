from flask import Flask, request, jsonify, render_template
from quiz_game import QuizGame  # Import your QuizGame class

app = Flask(__name__)
game = QuizGame()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/set_user_info', methods=['POST'])
def set_user_info():
    data = request.json
    game.region = data.get('region')
    game.age_group = data.get('age_group')
    return jsonify({"success": True})

@app.route('/start_quiz', methods=['POST'])
def start_quiz():
    game.score = 0
    game.total_questions = 0
    question = game.generate_question()
    return jsonify({"question": question, "options": game.current_options})

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    data = request.json
    answer = data.get('answer')
    is_correct = game.check_answer(answer)
    new_question = game.generate_question()
    return jsonify({"is_correct": is_correct, "question": new_question, "options": game.current_options, "score": game.get_score()})

@app.route('/skip_question', methods=['POST'])
def skip_question():
    new_question = game.skip_question()
    return jsonify({"question": new_question, "options": game.current_options, "score": game.get_score()})

@app.route('/end_session', methods=['POST'])
def end_session():
    result = game.end_session()
    return jsonify({"result": result})

if __name__ == '__main__':
    app.run(debug=True)
