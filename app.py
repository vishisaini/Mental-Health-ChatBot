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
if os.path.isfile("bot_brain.brn"):
    kernel.bootstrap(brainFile="bot_brain.brn")
else:
    kernel.learn("std-startup.xml")
    kernel.respond("load aiml b")
    kernel.saveBrain("bot_brain.brn")

# Initialize database
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

# Keywords for stress detection
CASUAL_WORDS = {"hello", "hi", "good", "thanks", "okay"}
STRESS_WORDS = {"stressed", "anxious", "scored bad", "worried", "sad"}
CRISIS_WORDS = {"die", "suicide", "kill myself", "end my life", "want to die"}

def detect_stress_level(user_message):
    words = set(user_message.lower().split())
    if any(word in words for word in CRISIS_WORDS):
        return "CRISIS"
    elif any(word in words for word in STRESS_WORDS):
        return "STRESS"
    return "NEUTRAL"

def analyze_sentiment(text):
    sentiment = TextBlob(text).sentiment.polarity
    if sentiment < -0.3:
        return "CRISIS"
    elif sentiment < 0:
        return "STRESS"
    return "NEUTRAL"

def save_chat_history(user_message, bot_response, stress_level):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_history (user_message, bot_response, stress_level) VALUES (?, ?, ?)",
                   (user_message, bot_response, stress_level))
    conn.commit()
    conn.close()

def recognize_speech():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)
    try:
        return recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        return "Sorry, I couldn't understand."
    except sr.RequestError:
        return "Speech recognition service unavailable."

@app.route("/")
def home():
    return render_template("chat.html")

@app.route("/get", methods=["POST"])
def chat():
    user_message = request.json.get("message")
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
    return jsonify({"response": bot_response, "stress_level": stress_level})

@app.route("/live-voice", methods=["POST"])
def live_voice_chat():
    user_message = recognize_speech()
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
