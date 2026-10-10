import os
import requests
from flask import Flask, request, jsonify
from google import genai
from google.genai import types

app = Flask(__name__)

# Environment Variables
EVOLUTION_URL = os.getenv("EVOLUTION_URL", "").rstrip("/")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
INSTANCE_NAME = os.getenv("INSTANCE_NAME", "assistant")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PRIMARY_NUMBER = os.getenv("PRIMARY_NUMBER")

# Initialize Google GenAI Client
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTION = """You are acting as an Executive Assistant and Proxy. You handle incoming queries sent to this WhatsApp number.

RULES:
1. Answer routine questions using general knowledge directly.
2. For scheduling requests, gathering information, or general inquiries, collect details (Name, Purpose) before notifying the owner.
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
    try:
        requests.post(url, json=payload, headers=headers, timeout=10)
    except Exception as e:
        print(f"Error sending WhatsApp message: {e}")

@app.route("/", methods=["GET"])
def home():
    return "WhatsApp Proxy Backend is Active", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    
    event = data.get("event")
    if event != "messages.upsert":
        return jsonify({"status": "ignored_event"}), 200

    msg_data = data.get("data", {})
    key = msg_data.get("key", {})
    
    # Do not process messages sent by the bot itself
    if key.get("fromMe"):
        return jsonify({"status": "ignored_self"}), 200

    remote_jid = key.get("remoteJid", "")
    if "@g.us" in remote_jid:
        return jsonify({"status": "ignored_group"}), 200
        
    sender_number = remote_jid.split("@")[0]
    
    message_obj = msg_data.get("message", {})
    user_text = (
        message_obj.get("conversation") 
        or message_obj.get("extendedTextMessage", {}).get("text")
    )
    
    if not user_text:
        return jsonify({"status": "no_text"}), 200

    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=f"User Message from {sender_number}: {user_text}",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                max_output_tokens=500,
            ),
        )
        reply_text = response.text.strip() if response.text else ""
    except Exception as err:
        print(f"Gemini API Error: {err}")
        return jsonify({"status": "error_gemini"}), 500

    if reply_text.startswith("[URGENT]"):
        clean_reply = reply_text.replace("[URGENT]", "").strip()
        send_whatsapp_msg(sender_number, clean_reply)
        alert_msg = f"🚨 *APPROVAL / ALERT NEEDED*\n*Sender:* +{sender_number}\n*Context:* {user_text}"
        send_whatsapp_msg(PRIMARY_NUMBER, alert_msg)
    else:
        send_whatsapp_msg(sender_number, reply_text)

    return jsonify({"status": "success"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
