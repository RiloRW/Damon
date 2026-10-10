import os
import requests
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# Environment Variables
EVOLUTION_URL = os.getenv("EVOLUTION_URL")  # e.g., https://evolution-api-9n1n.onrender.com
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
INSTANCE_NAME = os.getenv("INSTANCE_NAME", "assistant")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PRIMARY_NUMBER = os.getenv("PRIMARY_NUMBER")  # e.g., 6281234567890

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

SYSTEM_INSTRUCTION = """You are acting as an Executive Assistant and Proxy for Rilo. You handle incoming queries sent to this WhatsApp number.

RULES:
1. Answer routine questions using general knowledge directly.
2. For scheduling requests, gathering information, or general inquiries, collect details (Name, Purpose) before notifying Rilo.
3. If an issue is URGENT, involves MONEY, or requires DIRECT APPROVAL/DECISION, output [URGENT] at the very beginning of your response.
"""

def send_whatsapp_msg(number, text):
    url = f"{EVOLUTION_URL}/message/sendText/{INSTANCE_NAME}"
    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "number": number,
        "text": text
    }
    requests.post(url, json=payload, headers=headers)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    
    # Process only incoming text messages
    if not data or data.get("event") != "messages.upsert":
        return jsonify({"status": "ignored"}), 200

    msg_data = data.get("data", {})
    key = msg_data.get("key", {})
    
    # Ignore messages sent by the bot itself
    if key.get("fromMe"):
        return jsonify({"status": "ignored_self"}), 200

    remote_jid = key.get("remoteJid", "")
    sender_number = remote_jid.split("@")[0]
    
    # Extract message text
    message_content = msg_data.get("message", {})
    user_text = message_content.get("conversation") or message_content.get("extendedTextMessage", {}).get("text")
    
    if not user_text:
        return jsonify({"status": "no_text"}), 200

    # Prompt Gemini
    prompt = f"{SYSTEM_INSTRUCTION}\n\nUser Message from {sender_number}: {user_text}"
    response = model.generate_content(prompt)
    reply_text = response.text.strip()

    # Check for urgent escalation
    if reply_text.startswith("[URGENT]"):
        clean_reply = reply_text.replace("[URGENT]", "").strip()
        # Reply to sender
        send_whatsapp_msg(sender_number, clean_reply)
        # Escalate to primary number
        alert_msg = f"🚨 *APPROVAL / ALERT NEEDED*\n*Sender:* +{sender_number}\n*Context:* {user_text}"
        send_whatsapp_msg(PRIMARY_NUMBER, alert_msg)
    else:
        send_whatsapp_msg(sender_number, reply_text)

    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
  
