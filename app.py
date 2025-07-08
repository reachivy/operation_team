# -*- coding: utf-8 -*-
import pandas as pd
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_mail import Mail, Message
from sentence_transformers import SentenceTransformer, util
import re
from collections import Counter
import time
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Configure session secret key
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Configure Flask-Mail for sending emails
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

# Initialize Flask-Mail
mail = Mail(app)

# Make sessions non-permanent to enforce login on every run
app.config['SESSION_PERMANENT'] = False

# Initialize database
def init_db():
    conn = sqlite3.connect('chatbot.db')
    c = conn.cursor()
    # Create users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )
    ''')
    # Create password_resets table
    c.execute('''
        CREATE TABLE IF NOT EXISTS password_resets (
            email TEXT NOT NULL,
            token TEXT PRIMARY KEY,
            expires_at INTEGER NOT NULL,
            FOREIGN KEY (email) REFERENCES users (email)
        )
    ''')
    # Insert default user if not exists
    email = 'reachivy.experts@gmail.com'
    password = 'sale@reachivy.team'
    password_hash = generate_password_hash(password)
    c.execute('INSERT OR IGNORE INTO users (email, password_hash) VALUES (?, ?)', (email, password_hash))
    conn.commit()
    conn.close()

# Load dataset
try:
    df = pd.read_csv('data/questions.csv', encoding='cp1252')
    print("CSV Columns:", df.columns.tolist())
    required_columns = ['section', 'question_number', 'question', 'correct_answer', 'keywords']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns in CSV: {missing_columns}")
except Exception as e:
    app.logger.error(f"Failed to load questions.csv: {str(e)}")
    raise

# Define sections with topics
sections = {
    1: {'name': 'Daily Numbers Tracking', 'questions': list(range(1, 9))},
    2: {'name': 'Calendly Slot Availability', 'questions': list(range(9, 15))},
    3: {'name': 'Event Registration Numbers', 'questions': list(range(15, 18))},
    4: {'name': 'Scholarship Numbers and Process', 'questions': list(range(18, 29))},
    5: {'name': 'Action Payment Process', 'questions': list(range(29, 56))},
    6: {'name': 'Scheduling Session', 'questions': list(range(56, 61))},
    7: {'name': 'Generic', 'questions': list(range(61, 63))},
    8: {'name': 'Weekly Conversation Tracker', 'questions': list(range(63, 76))},
    9: {'name': 'Counselling FAQs', 'questions': list(range(76, 77))},
    10: {'name': 'Test Scores and Transcripts', 'questions': list(range(77, 82))},
    11: {'name': 'Application FAQs', 'questions': list(range(82, 98))},
    12: {'name': 'Interview Prep FAQs', 'questions': list(range(98, 102))}
}

# Load sentence transformer model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Precompute embeddings for all correct answers
correct_answer_embeddings = {}
start_precompute = time.time()
for _, row in df.iterrows():
    question_num = row['question_number']
    correct_answer = row['correct_answer']
    embedding = model.encode(correct_answer)
    correct_answer_embeddings[question_num] = embedding
app.logger.info(f"Precomputing correct answer embeddings took {time.time() - start_precompute:.2f} seconds")

# Store user progress
user_progress = {}

# Prepare questions data for each section
section_questions = {}
for section, info in sections.items():
    section_questions[section] = []
    section_start_question = info['questions'][0]
    for q_num in info['questions']:
        filtered_df = df[df['question_number'] == q_num]
        if not filtered_df.empty:
            question_row = filtered_df.iloc[0]
            display_question_number = q_num - section_start_question + 1
            section_questions[section].append({
                'question_number': q_num,
                'display_question_number': display_question_number,
                'question': question_row['question']
            })
        else:
            section_questions[section].append({
                'question_number': q_num,
                'display_question_number': None,
                'question': "Question data missing"
            })

def normalize_text(text):
    text = re.sub(r'[^\w\s]', '', text)
    text = text.lower()
    return text

def keyword_present(keyword, user_answer):
    keyword = normalize_text(keyword.strip())
    user_answer = normalize_text(user_answer)
    keyword_words = set(keyword.split())
    user_answer_words = set(user_answer.split())
    if not keyword_words:
        return True
    overlap = len(keyword_words.intersection(user_answer_words))
    overlap_ratio = overlap / len(keyword_words)
    return overlap_ratio >= 0.7

def generate_content_accuracy_feedback(user_answer, question_num):
    question_row = df[df['question_number'] == question_num].iloc[0]
    keywords_str = question_row['keywords']
    if not keywords_str or pd.isna(keywords_str):
        return {"score": 100, "comment": "Content Accuracy: Excellent - No keywords to evaluate, but your response aligns well."}
    keywords = [keyword.strip() for keyword in keywords_str.split('|') if keyword.strip()]
    if not keywords:
        return {"score": 100, "comment": "Content Accuracy: Excellent - No keywords to evaluate, but your response aligns well."}
    present_keywords = [keyword for keyword in keywords if keyword_present(keyword, user_answer)]
    missing_keywords = [keyword for keyword in keywords if keyword not in present_keywords]
    total_keywords = len(keywords)
    present_count = len(present_keywords)
    accuracy_score = (present_count / total_keywords) * 100 if total_keywords > 0 else 100
    if accuracy_score >= 90:
        comment = "Content Accuracy: Excellent - Your response captures almost all key keywords."
    elif accuracy_score >= 70:
        comment = "Content Accuracy: Good - You included most of the key keywords, but some are missing."
    elif accuracy_score >= 50:
        comment = "Content Accuracy: Fair - You captured some key keywords, but several are missing."
    else:
        comment = "Content Accuracy: Needs Improvement - Many key keywords are missing from your response."
    if missing_keywords:
        comment += "\nMissing keywords: " + ", ".join([f"'{keyword}'" for keyword in missing_keywords])
    return {"score": accuracy_score, "comment": comment}

def evaluate_answer(user_answer, question_num):
    start_time = time.time()
    user_embedding = model.encode(user_answer)
    correct_embedding = correct_answer_embeddings[question_num]
    semantic_similarity = util.cos_sim(user_embedding, correct_embedding).item() * 100
    content_accuracy = generate_content_accuracy_feedback(user_answer, question_num)
    content_accuracy_score = content_accuracy["score"]
    final_match_percentage = (semantic_similarity + content_accuracy_score) / 2
    final_match_percentage = max(0, min(100, round(final_match_percentage)))
    if final_match_percentage >= 70:
        score = 100
    elif 65 <= final_match_percentage < 70:
        score = 90
    elif 60 <= final_match_percentage < 65:
        score = 80
    elif 55 <= final_match_percentage < 60:
        score = 70
    elif 50 <= final_match_percentage < 55:
        score = 60
    elif 45 <= final_match_percentage < 50:
        score = 50
    else:
        score = final_match_percentage
    app.logger.info(f"Total evaluate_answer took {time.time() - start_time:.2f} seconds")
    return score

def generate_detailed_feedback(user_answer, correct_answer, score):
    start_time = time.time()
    question_num = df[df['correct_answer'] == correct_answer].iloc[0]['question_number']
    content_accuracy = generate_content_accuracy_feedback(user_answer, question_num)
    detailed_feedback = ""
    if score < 70:
        detailed_feedback = "Review the missing keywords listed in the Content Accuracy feedback to improve your response."
    app.logger.info(f"Generate detailed feedback took {time.time() - start_time:.2f} seconds")
    return {
        "content_accuracy": content_accuracy["comment"],
        "detailed_feedback": detailed_feedback
    }

# Middleware to check if user is authenticated
def login_required(f):
    def wrap(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrap.__name__ = f.__name__
    return wrap

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        conn = sqlite3.connect('chatbot.db')
        c = conn.cursor()
        c.execute('SELECT password_hash FROM users WHERE email = ?', (email,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user[0], password):
            session['logged_in'] = True
            session.permanent = False
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid email or password.')
    return render_template('login.html')

@app.route('/logout', methods=['GET'])
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        conn = sqlite3.connect('chatbot.db')
        c = conn.cursor()
        c.execute('SELECT email FROM users WHERE email = ?', (email,))
        user = c.fetchone()
        if user:
            token = secrets.token_urlsafe(32)
            expires_at = int(time.time()) + 3600
            c.execute('INSERT INTO password_resets (email, token, expires_at) VALUES (?, ?, ?)', (email, token, expires_at))
            conn.commit()
            reset_link = url_for('reset_password', token=token, _external=True)
            msg = Message('Password Reset Request', recipients=[email], body=f'Click the following link to reset your password: {reset_link}\nThis link will expire in 1 hour.')
            try:
                mail.send(msg)
                conn.close()
                return render_template('forgot_password.html', message='A password reset link has been sent to your email.')
            except Exception as e:
                conn.close()
                app.logger.error(f"Failed to send email to {email}: {str(e)}")
                return render_template('forgot_password.html', error=f'Failed to send email: {str(e)}. Please try again later.')
        else:
            conn.close()
            return render_template('forgot_password.html', error='Email not found.')
    return render_template('forgot_password.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    token = request.args.get('token')
    if not token:
        return redirect(url_for('login'))
    conn = sqlite3.connect('chatbot.db')
    c = conn.cursor()
    current_time = int(time.time())
    c.execute('SELECT email, expires_at FROM password_resets WHERE token = ?', (token,))
    reset_request = c.fetchone()
    if not reset_request or reset_request[1] < current_time:
        conn.close()
        return render_template('reset_password.html', error='Invalid or expired token.')
    email = reset_request[0]
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if new_password != confirm_password:
            return render_template('reset_password.html', token=token, error='Passwords do not match.')
        password_hash = generate_password_hash(new_password)
        c.execute('UPDATE users SET password_hash = ? WHERE email = ?', (password_hash, email))
        c.execute('DELETE FROM password_resets WHERE token = ?', (token,))
        conn.commit()
        conn.close()
        return redirect(url_for('login'))
    conn.close()
    return render_template('reset_password.html', token=token)

@app.route('/')
@login_required
def index():
    return render_template('index.html', sections=sections, section_questions=section_questions)

@app.route('/start_assessment', methods=['POST'])
@login_required
def start_assessment():
    user_id = request.json.get('user_id', 'default_user')
    requested_section = request.json.get('section')
    if user_id not in user_progress:
        user_progress[user_id] = {
            'current_section': 1,
            'section_scores': {},
            'current_questions': [],
            'current_index': 0,
            'scores': [],
            'answered_question_numbers': []
        }
    if requested_section is not None:
        requested_section = int(requested_section)
        if requested_section in sections:
            user_progress[user_id]['current_section'] = requested_section
            user_progress[user_id]['current_questions'] = []
            user_progress[user_id]['current_index'] = 0
            user_progress[user_id]['scores'] = []
            user_progress[user_id]['answered_question_numbers'] = []
        else:
            app.logger.error(f"Invalid section requested: {requested_section}")
            return jsonify({'error': f"Invalid section: {requested_section}"}), 400
    section = user_progress[user_id]['current_section']
    app.logger.info(f"Starting assessment for user {user_id}, current_section: {section}")
    expected_questions = sections[section]['questions']
    if not user_progress[user_id]['current_questions']:
        user_progress[user_id]['current_questions'] = expected_questions.copy()
        user_progress[user_id]['current_index'] = 0
    if user_progress[user_id]['current_questions'] != expected_questions:
        app.logger.warning(f"current_questions mismatch for section {section}. Expected: {expected_questions}, Got: {user_progress[user_id]['current_questions']}")
        user_progress[user_id]['current_questions'] = expected_questions.copy()
        user_progress[user_id]['current_index'] = 0
    if not user_progress[user_id]['current_questions']:
        return jsonify({'error': 'No questions available for this section'}), 500
    question_num = user_progress[user_id]['current_questions'][0]
    question_row = df[df['question_number'] == question_num].iloc[0]
    question_section = question_row['section']
    if question_section != section:
        app.logger.error(f"Question {question_num} is from section {question_section}, but user is in section {section}")
        return jsonify({'error': f"Question {question_num} does not belong to section {section}"}), 500
    total_questions = len(sections[section]['questions'])
    section_start_question = sections[section]['questions'][0]
    display_question_number = question_num - section_start_question + 1
    response = {
        'section': section,
        'section_name': sections[section]['name'],
        'question_number': question_num,
        'display_question_number': display_question_number,
        'question': question_row['question'],
        'answered': user_progress[user_id]['current_index'],
        'total_questions': total_questions
    }
    app.logger.info(f"Sending response for section {section}: {response}")
    return jsonify(response)

@app.route('/get_question', methods=['POST'])
@login_required
def get_question():
    user_id = request.json.get('user_id', 'default_user')
    question_num = int(request.json.get('question_number'))
    section = None
    for sec, info in sections.items():
        if question_num in info['questions']:
            section = sec
            break
    if section is None:
        app.logger.error(f"Question {question_num} does not belong to any section")
        return jsonify({'error': f"Question {question_num} does not belong to any section"}), 400
    if user_id not in user_progress:
        user_progress[user_id] = {
            'current_section': section,
            'section_scores': {},
            'current_questions': [],
            'current_index': 0,
            'scores': [],
            'answered_question_numbers': []
        }
    user_progress[user_id]['current_section'] = section
    expected_questions = sections[section]['questions']
    user_progress[user_id]['current_questions'] = expected_questions.copy()
    current_index = expected_questions.index(question_num)
    user_progress[user_id]['current_index'] = current_index
    question_row = df[df['question_number'] == question_num].iloc[0]
    question_section = question_row['section']
    if question_section != section:
        app.logger.error(f"Question {question_num} is from section {question_section}, but expected section {section}")
        return jsonify({'error': f"Question {question_num} does not belong to section {section}"}), 500
    total_questions = len(sections[section]['questions'])
    section_start_question = sections[section]['questions'][0]
    display_question_number = question_num - section_start_question + 1
    response = {
        'section': section,
        'section_name': sections[section]['name'],
        'question_number': question_num,
        'display_question_number': display_question_number,
        'question': question_row['question'],
        'answered': user_progress[user_id]['current_index'],
        'total_questions': total_questions
    }
    app.logger.info(f"Sending response for question {question_num}: {response}")
    return jsonify(response)

@app.route('/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    start_time = time.time()
    user_id = request.json.get('user_id', 'default_user')
    user_answer = request.json.get('answer')
    question_num = request.json.get('question_number')
    start_fetch = time.time()
    question_row = df[df['question_number'] == question_num].iloc[0]
    try:
        correct_answer = question_row['correct_answer']
    except KeyError as e:
        app.logger.error(f"KeyError: {str(e)} - Available columns: {question_row.index.tolist()}")
        return jsonify({'error': 'Internal server error: Missing correct_answer column'}), 500
    app.logger.info(f"Fetching question data took {time.time() - start_fetch:.2f} seconds")
    start_validate = time.time()
    current_section = user_progress[user_id]['current_section']
    question_section = question_row['section']
    if question_section != current_section:
        app.logger.error(f"Submitted question {question_num} is from section {question_section}, but user is in section {current_section}")
        return jsonify({'error': f"Question {question_num} does not belong to section {current_section}"}), 500
    app.logger.info(f"Section validation took {time.time() - start_validate:.2f} seconds")
    score = evaluate_answer(user_answer, question_num)
    start_feedback = time.time()
    feedback_data = generate_detailed_feedback(user_answer, correct_answer, score)
    app.logger.info(f"Feedback generation took {time.time() - start_feedback:.2f} seconds")
    start_progress = time.time()
    user_progress[user_id]['scores'].append(score)
    user_progress[user_id]['answered_question_numbers'].append(question_num)
    if user_progress[user_id]['current_questions'] and user_progress[user_id]['current_questions'][0] == question_num:
        user_progress[user_id]['current_questions'].pop(0)
        user_progress[user_id]['current_index'] += 1
    else:
        app.logger.error(f"Question {question_num} does not match expected next question in current_questions: {user_progress[user_id]['current_questions']}")
        user_progress[user_id]['current_questions'] = sections[current_section]['questions'].copy()[user_progress[user_id]['current_index']:]
    app.logger.info(f"User progress update took {time.time() - start_progress:.2f} seconds")
    start_section_check = time.time()
    if not user_progress[user_id]['current_questions']:
        section_score = sum(user_progress[user_id]['scores']) / len(sections[user_progress[user_id]['current_section']]['questions'])
        user_progress[user_id]['section_scores'][user_progress[user_id]['current_section']] = section_score
        feedback = ""
        low_score_questions = [(q_num, score) for q_num, score in zip(user_progress[user_id]['answered_question_numbers'], user_progress[user_id]['scores']) if score <= 60]
        question_scores = [{'question_number': q_num, 'score': score} for q_num, score in zip(user_progress[user_id]['answered_question_numbers'], user_progress[user_id]['scores'])]
        if low_score_questions:
            feedback = "Feedback: Your responses for the following questions scored 60 points or less:\n"
            feedback += ", ".join([f"Question {q_num} ({score} points)" for q_num, score in low_score_questions])
            feedback += "\nConsider reviewing these topics to improve your answers."
        user_progress[user_id]['scores'] = []
        user_progress[user_id]['answered_question_numbers'] = []
        user_progress[user_id]['current_index'] = 0
        current_section = user_progress[user_id]['current_section']
        if section_score >= 75:
            user_progress[user_id]['current_section'] += 1
            if user_progress[user_id]['current_section'] > 12:
                app.logger.info(f"Assessment completed: {user_progress[user_id]['section_scores']}")
                app.logger.info(f"Total submit_answer took {time.time() - start_time:.2f} seconds")
                return jsonify({'status': 'completed', 'scores': user_progress[user_id]['section_scores']})
        else:
            user_progress[user_id]['current_questions'] = sections[current_section]['questions'].copy()
        new_section = user_progress[user_id]['current_section']
        user_progress[user_id]['current_questions'] = sections[new_section]['questions'].copy()
        app.logger.info(f"After section {current_section} completion, reset current_questions for section {new_section}: {user_progress[user_id]['current_questions']}")
        app.logger.info(f"Total submit_answer took {time.time() - start_time:.2f} seconds")
        return jsonify({
            'status': 'section_completed',
            'section': user_progress[user_id]['current_section'],
            'section_name': sections[user_progress[user_id]['current_section']]['name'],
            'section_score': section_score,
            'feedback': feedback,
            'question_scores': question_scores
        })
    app.logger.info(f"Section completion check took {time.time() - start_section_check:.2f} seconds")
    start_next_question = time.time()
    question_num = user_progress[user_id]['current_questions'][0]
    question_row = df[df['question_number'] == question_num].iloc[0]
    question_section = question_row['section']
    if question_section != user_progress[user_id]['current_section']:
        app.logger.error(f"Next question {question_num} is from section {question_section}, but user is in section {user_progress[user_id]['current_section']}")
        return jsonify({'error': f"Question {question_num} does not belong to section {user_progress[user_id]['current_section']}"}), 500
    total_questions = len(sections[user_progress[user_id]['current_section']]['questions'])
    answered = user_progress[user_id]['current_index']
    section_start_question = sections[user_progress[user_id]['current_section']]['questions'][0]
    display_question_number = question_num - section_start_question + 1
    response = {
        'section': user_progress[user_id]['current_section'],
        'section_name': sections[user_progress[user_id]['current_section']]['name'],
        'question_number': question_num,
        'display_question_number': display_question_number,
        'question': question_row['question'],
        'answered': answered,
        'total_questions': total_questions,
        'match_percentage': score,
        'score_points': score,
        'content_accuracy': feedback_data['content_accuracy'],
        'detailed_feedback': feedback_data['detailed_feedback'],
        'correct_answer': correct_answer  # Include correct answer in response
    }
    app.logger.info(f"Preparing next question took {time.time() - start_next_question:.2f} seconds")
    app.logger.info(f"Moving to next question: {question_num}, display number: {display_question_number}")
    app.logger.info(f"Feedback data being sent: {feedback_data}")
    app.logger.info(f"Full response being sent: {response}")
    app.logger.info(f"Total submit_answer took {time.time() - start_time:.2f} seconds")
    return jsonify(response)

if __name__ == '__main__':
    init_db()
    try:
        app.run(debug=True)
    finally:
        pass