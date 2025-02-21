from flask import Flask, render_template, request, jsonify, session
import aiml
import os
import speech_recognition as sr
import sqlite3
from textblob import TextBlob

app = Flask(__name__)
app.secret_key = "secret123"  # For session storage

# Initialize AIML Kernel
kernel = aiml.Kernel()

# Load AIML files
if os.path.isfile("bot_brain.brn"):
    kernel.bootstrap(brainFile="bot_brain.brn")
else:
    kernel.learn("std-startup.xml")
    kernel.respond("load aiml b")
    kernel.saveBrain("bot_brain.brn")

# Initialize database for chat history
DB_FILE = "chat_history.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_message TEXT,
            bot_response TEXT,
            stress_level TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Keywords for stress level detection
CASUAL_WORDS = {"hello", "hi", "good", "thanks", "okay"}
STRESS_WORDS = {"stressed", "anxious", "scored bad", "worried", "sad"}
CRISIS_WORDS = {"die", "suicide", "kill myself", "end my life", "want to die"}

def detect_stress_level(user_message):
    words = set(user_message.lower().split())

    if any(word in words for word in CRISIS_WORDS):
        return "CRISIS"
    elif any(word in words for word in STRESS_WORDS):
        return "STRESS"
    else:
        return "NEUTRAL"

def analyze_sentiment(text):
    sentiment = TextBlob(text).sentiment.polarity
    if sentiment < -0.3:
        return "CRISIS"
    elif sentiment < 0:
        return "STRESS"
    else:
        return "NEUTRAL"

def save_chat_history(user_message, bot_response, stress_level):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_history (user_message, bot_response, stress_level) VALUES (?, ?, ?)",
                   (user_message, bot_response, stress_level))
    conn.commit()
    conn.close()

def speech_to_text(audio_file_path):
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_file_path) as source:
        audio = recognizer.record(source)

    try:
        text = recognizer.recognize_google(audio)
        return text
    except sr.UnknownValueError:
        return "Sorry, I couldn't understand the audio."
    except sr.RequestError:
        return "Speech recognition service unavailable."

@app.route("/")
def home():
    return render_template("chat.html")

@app.route("/get", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    
    # Detect stress level using both keyword matching & NLP sentiment analysis
    keyword_stress = detect_stress_level(user_message)
    sentiment_stress = analyze_sentiment(user_message)
    stress_level = max(keyword_stress, sentiment_stress, key=lambda x: ["NEUTRAL", "STRESS", "CRISIS"].index(x))

    # Generate bot response based on stress level
    if stress_level == "CRISIS":
        bot_response = "I'm really sorry you're feeling this way. 💙 You're not alone. Please talk to someone you trust or seek professional help."
    elif stress_level == "STRESS":
        bot_response = "I understand that you're feeling stressed. Take a deep breath. Do you want to share what's on your mind?"
    else:
        bot_response = kernel.respond(user_message)

    save_chat_history(user_message, bot_response, stress_level)
    
    return jsonify({"response": bot_response, "stress_level": stress_level})

@app.route("/voice-input", methods=["POST"])
def voice_chat():
    audio_file_path = request.json.get("audio_file_path")
    user_message = speech_to_text(audio_file_path)

    # Detect mood and generate response
    keyword_stress = detect_stress_level(user_message)
    sentiment_stress = analyze_sentiment(user_message)
    stress_level = max(keyword_stress, sentiment_stress, key=lambda x: ["NEUTRAL", "STRESS", "CRISIS"].index(x))

    if stress_level == "CRISIS":
        bot_response = "You're not alone. Please reach out to someone you trust."
    elif stress_level == "STRESS":
        bot_response = "Take a deep breath. Want to talk about it?"
    else:
        bot_response = kernel.respond(user_message)

    save_chat_history(user_message, bot_response, stress_level)

    return jsonify({"response": bot_response, "stress_level": stress_level, "transcribed_text": user_message})

@app.route("/history")
def chat_history():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chat_history")
    history = cursor.fetchall()
    conn.close()

    return jsonify({"history": history})

if __name__ == "__main__":
    app.run(debug=True)
