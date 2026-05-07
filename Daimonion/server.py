from flask import Flask, request, jsonify
import json
import requests

app = Flask(__name__)

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "daimonio"

def load_profile():
    with open("user_profile.json", "r", encoding="utf-8") as f:
        return json.load(f)

def load_memory():
    with open("memory.txt", "r", encoding="utf-8") as f:
        return f.read()

@app.route("/chat", methods=["POST"])
def chat():

    user_input = request.json["message"]

    profile = load_profile()
    memory = load_memory()

    system_context = f"""
PROFIL UŽIVATELE:
{json.dumps(profile, indent=2, ensure_ascii=False)}

DOSAVADNÍ POZNATKY:
{memory}
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system_context},
                {"role": "user", "content": user_input}
            ]
        }
    )

    reply = response.json()["message"]["content"]

    return jsonify({"reply": reply})

app.run(host="0.0.0.0", port=5000)