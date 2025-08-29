import os
import re
import secrets
import datetime
import pathlib
from flask import Flask, request, render_template, jsonify, session, send_from_directory
import google.generativeai as genai
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.utils import secure_filename

# ---------------- Config ----------------
# NOTE: This uses the same style you provided. Keep the API key as-is.
genai.configure(api_key="GEMINI API KEY")
MODEL_NAME = "gemini-1.5-flash-latest"

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# folders
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------------- In-memory state ----------------
conversation_histories = {}   # session_id -> list(history parts)
patient_logs = {}            # session_id -> {pain:[], medication:[], mobility:[], mood:[], symptoms:[], wound:[], alerts:[], reminders:[]}
alerts_store = {}            # session_id -> list of active alerts
reminders_store = {}         # reminder_id -> {session_id, when, text, sent}

# Scheduler to deliver reminders
scheduler = BackgroundScheduler()
scheduler.start()

# ---------------- Helper utilities ----------------
def get_session_id():
    sid = session.get("session_id")
    if not sid:
        sid = secrets.token_hex(8)
        session["session_id"] = sid
        conversation_histories[sid] = []
        patient_logs[sid] = {"pain": [], "medication": [], "mobility": [], "mood": [], "symptoms": [], "wound": [], "alerts": [], "reminders": []}
        alerts_store[sid] = []
    # ensure dict exists
    if sid not in patient_logs:
        patient_logs[sid] = {"pain": [], "medication": [], "mobility": [], "mood": [], "symptoms": [], "wound": [], "alerts": [], "reminders": []}
    if sid not in conversation_histories:
        conversation_histories[sid] = []
    if sid not in alerts_store:
        alerts_store[sid] = []
    return sid

def ts_now():
    return datetime.datetime.utcnow().isoformat()

def get_current_time_info():
    """Get current time information in a readable format"""
    now = datetime.datetime.now()
    utc_now = datetime.datetime.utcnow()
    return {
        "local_time": now.strftime("%I:%M %p"),
        "local_date": now.strftime("%A, %B %d, %Y"),
        "utc_time": utc_now.strftime("%I:%M %p UTC"),
        "timestamp": now.isoformat()
    }

def _update_history(session_id, user, bot):
    history = conversation_histories.get(session_id, [])
    history.append({"role": "user", "parts": [user]})
    history.append({"role": "model", "parts": [bot]})
    conversation_histories[session_id] = history

def log_patient_data(session_id, category, value):
    now = ts_now()
    if session_id not in patient_logs:
        get_session_id()  # create
    if category not in patient_logs[session_id]:
        patient_logs[session_id][category] = []
    patient_logs[session_id][category].append({"time": now, "value": value})

def detect_and_log_basic(session_id, text):
    t = text.lower()
    # Pain: parse "pain 7" or "pain is 7/10"
    m = re.search(r'pain\s*(?:is|=|:)?\s*(\d{1,2})', t)
    if m:
        log_patient_data(session_id, "pain", f"{m.group(1)}/10")
    # steps
    s = re.search(r'(\d{2,6})\s*steps', t)
    if s:
        log_patient_data(session_id, "mobility", f"{s.group(1)} steps")
    # medication confirm
    if re.search(r'\b(took|taken|took my|took the|medicine|medication|tablet|pill)\b', t):
        log_patient_data(session_id, "medication", text)
    # mood
    if re.search(r'\b(mood|feeling|anxious|sad|depressed|happy|ok)\b', t):
        log_patient_data(session_id, "mood", text)
    # symptoms (keywords)
    symptoms_kw = ["fever", "dizzy", "dizziness", "nausea", "bleeding", "swelling", "pus", "infection", "shortness of breath", "chest pain"]
    for kw in symptoms_kw:
        if kw in t:
            log_patient_data(session_id, "symptoms", text)
            break
    # wound
    if "wound" in t or "photo" in t or "upload" in t:
        log_patient_data(session_id, "wound", text)

def triage_simple(text):
    """Return (severity, reason) where severity in ('low','medium','high') or None."""
    t = text.lower()
    high = ["chest pain", "severe bleeding", "difficulty breathing", "unconscious", "passing out"]
    medium = ["fever", "dizzy", "dizziness", "severe pain", "swelling", "pus", "infection"]
    for kw in high:
        if kw in t:
            return ("high", f"Immediate attention required: {kw}")
    for kw in medium:
        if kw in t:
            return ("medium", f"Possible complication: {kw}")
    # numeric pain check
    m = re.search(r'pain\s*(?:is|=|:)?\s*(\d{1,2})', t)
    if m:
        pain = int(m.group(1))
        if pain >= 8:
            return ("medium", f"High pain reported ({pain}/10)")
    return (None, None)

def format_response_points(response_text):
    """Format bot response into bullet points when naturally containing multiple actionable items"""
    # If response already has bullet points or numbered lists, return as is
    if re.search(r'^\s*[\d•\-\*]\s', response_text, re.MULTILINE):
        return response_text
    
    # Look for natural list indicators that suggest bullet formatting would help
    list_indicators = [
        'first', 'second', 'third', 'also', 'additionally', 'next', 'then',
        'try', 'consider', 'remember', 'make sure', 'don\'t forget'
    ]
    
    # Split by sentences
    sentences = re.split(r'[.!?]\s+', response_text.strip())
    sentences = [s.strip() for s in sentences if s.strip() and len(s) > 5]
    
    # Check if response naturally contains actionable advice or multiple suggestions
    has_actionable_content = any(indicator in response_text.lower() for indicator in list_indicators)
    has_multiple_suggestions = len(sentences) > 2 and has_actionable_content
    
    # Format as bullets only for actionable multi-point advice
    if has_multiple_suggestions and len(sentences) <= 4:  # Keep it concise
        formatted = ""
        for sentence in sentences:
            if sentence:
                if not sentence.endswith(('.', '!', '?')):
                    sentence += '.'
                formatted += f"• {sentence}\n"
        return formatted.strip()
    
    return response_text

def schedule_reminder_job(reminder_id, session_id, when_iso, text):
    # Called by scheduler at time -> push a bot message into conversation and mark as sent
    try:
        # deliver into history as bot message
        delivered_text = f"🔔 Reminder: {text} (scheduled at {when_iso})"
        _update_history(session_id, f"(system reminder triggered)", delivered_text)
        # mark in patient logs
        log_patient_data(session_id, "medication", f"Reminder triggered: {text}")
        # mark stored reminder as sent
        if reminder_id in reminders_store:
            reminders_store[reminder_id]["sent"] = True
            # also add to patient's reminders list
            patient_logs[session_id]["reminders"].append({"id": reminder_id, "when": when_iso, "text": text, "sent": True})
    except Exception as e:
        print("Error delivering reminder:", e)

# ---------------- Routes ----------------
@app.route("/")
def home():
    sid = get_session_id()
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        session_id = get_session_id()
        user_input = request.json.get("message", "") or request.form.get("message", "")
        if not user_input:
            return jsonify({"response": "Please write a message."}), 400

        # 1) Pre-log common data automatically from user input
        detect_and_log_basic(session_id, user_input)

        # 2) Run triage rules
        severity, reason = triage_simple(user_input)
        if severity:
            # store alert
            alert = {"time": ts_now(), "severity": severity, "reason": reason}
            alerts_store[session_id].append(alert)
            # auto-respond escalation
            if severity == "high":
                bot_text = f"⚠️ This sounds serious: {reason}. Please call emergency services or contact your doctor immediately."
                _update_history(session_id, user_input, bot_text)
                return jsonify({"response": bot_text})
            elif severity == "medium":
                bot_text = f"I noticed: {reason}. Please consider contacting your doctor — I will log this and notify them if needed."
                _update_history(session_id, user_input, bot_text)
                return jsonify({"response": bot_text})

        # 3) Handle time-related queries
        if re.search(r'\b(what time|current time|time now|what\'s the time)\b', user_input, re.IGNORECASE):
            time_info = get_current_time_info()
            bot_text = f"Current time information:\n\n• Local time: {time_info['local_time']}\n• Date: {time_info['local_date']}\n• UTC time: {time_info['utc_time']}"
            _update_history(session_id, user_input, bot_text)
            return jsonify({"response": bot_text})

        # 4) Handle some quick actions locally before sending to LLM
        # If user asks to set a reminder e.g., "Remind me at 17:00 to take antibiotic"
        rem_match = re.search(r'remind me (?:at|on|in)?\s*(.*) to (.+)', user_input, re.IGNORECASE)
        if rem_match:
            when_part = rem_match.group(1).strip()
            text_part = rem_match.group(2).strip()
            # Try simple parse: if the when_part looks like HH:MM or contains digits
            when_iso = None
            now = datetime.datetime.utcnow()
            # support "5 pm" or "17:00" naive parsing
            hm = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', when_part, re.IGNORECASE)
            if hm:
                hour = int(hm.group(1))
                minute = int(hm.group(2)) if hm.group(2) else 0
                ampm = (hm.group(3) or "").lower()
                if ampm == "pm" and hour < 12:
                    hour += 12
                if ampm == "am" and hour == 12:
                    hour = 0
                when_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                # if scheduled time already passed, schedule for next day
                if when_dt <= now:
                    when_dt = when_dt + datetime.timedelta(days=1)
                when_iso = when_dt.isoformat()
            else:
                # fallback: schedule in 1 minute (demo)
                when_dt = now + datetime.timedelta(minutes=1)
                when_iso = when_dt.isoformat()

            # register reminder
            reminder_id = secrets.token_hex(8)
            reminders_store[reminder_id] = {"session_id": session_id, "when": when_iso, "text": text_part, "sent": False}
            # schedule job
            run_date = datetime.datetime.fromisoformat(when_iso)
            scheduler.add_job(schedule_reminder_job, 'date', run_date=run_date, args=[reminder_id, session_id, when_iso, text_part])
            # store in patient logs
            patient_logs[session_id]["reminders"].append({"id": reminder_id, "when": when_iso, "text": text_part, "sent": False})
            bot_text = f"✅ Reminder scheduled at {when_dt.strftime('%Y-%m-%d %H:%M')} to: {text_part}"
            _update_history(session_id, user_input, bot_text)
            return jsonify({"response": bot_text})

        # 5) Wound photo prompt handling
        if re.search(r'\b(upload (a )?wound|i have uploaded|i uploaded|wound photo)\b', user_input, re.IGNORECASE):
            bot_text = "Thanks — when you upload the wound photo using the 'Upload Photo' button, I'll log it and remind your doctor if anything looks concerning."
            log_patient_data(session_id, "wound", user_input)
            _update_history(session_id, user_input, bot_text)
            return jsonify({"response": bot_text})

        # 6) Requests for report
        if re.search(r'\b(report|weekly report|progress report|show my progress)\b', user_input, re.IGNORECASE):
            # generate simple textual report
            report_text = generate_report_text(session_id)
            _update_history(session_id, user_input, report_text)
            return jsonify({"response": report_text})

        # 7) All other queries -> use Gemini LLM
        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            generation_config={
                "temperature": 0.35,
                "max_output_tokens": 400,
                "top_p": 0.9,
                "top_k": 40
            }
        )

        # build a clear system prompt + capabilities summary so the model acts consistently
        time_info = get_current_time_info()
        system_prompt = f"""
You are CareNest — a caring post-surgery recovery companion. Current time: {time_info['local_time']} on {time_info['local_date']}.

Your Core Mission:
Be a supportive, caring digital companion who helps patients recover while keeping responses friendly but concise (2-3 sentences max, unless giving specific medical guidance).

Key Responsibilities:
1. Daily Check-ins: Ask about pain, medication, mobility in a conversational caring way
2. Symptom Triage: Provide basic self-care tips, escalate serious symptoms to doctors
3. Medication Reminders: Set personalized reminders and track adherence 
4. Exercise & Mobility Coach: Surgery-specific exercise suggestions and motivation
5. Wound Monitoring: Encourage photo uploads and track healing
6. Educational Support: Answer recovery FAQs with helpful guidance
7. Mental Health: Daily motivation, mood check-ins, emotional support
8. Progress Tracking: Generate reports and celebrate improvements
9. Doctor Bridge: Help communicate with medical team
10. Predictive Alerts: Flag concerning patterns for medical attention

Response Style:
- Be warm, empathetic, and encouraging like a caring nurse
- Keep responses concise but show you care about their wellbeing
- Give relevant tips and suggestions based on context
- Use emojis occasionally to be friendly 😊
- Ask follow-up questions to stay engaged
- Remember their surgery type and recovery stage when possible
- Offer specific, actionable advice
- Celebrate small wins and progress

For Emergencies: Immediately recommend calling doctor/emergency services for: chest pain, severe bleeding, difficulty breathing, high fever, severe swelling.

Be conversational and caring, not clinical or robotic."""

        # Compose user message and recent history
        history = conversation_histories.get(session_id, [])
        chat = model.start_chat(history=history)
        
        # Add context from recent logs to make responses more personalized
        recent_context = ""
        logs = patient_logs.get(session_id, {})
        
        # Include recent pain levels
        if logs.get("pain") and len(logs["pain"]) > 0:
            recent_pain = logs["pain"][-1]["value"]
            recent_context += f"Recent pain level: {recent_pain}. "
        
        # Include recent medication info
        if logs.get("medication") and len(logs["medication"]) > 0:
            recent_med = len(logs["medication"])
            recent_context += f"Medication logs: {recent_med} entries. "
        
        # Include mobility info
        if logs.get("mobility") and len(logs["mobility"]) > 0:
            recent_mobility = logs["mobility"][-1]["value"]
            recent_context += f"Recent mobility: {recent_mobility}. "
        
        combined = f"{system_prompt}\n\nPatient Context: {recent_context}\n\nUSER: {user_input}"
        response = chat.send_message(combined)
        response_text = response.text.strip()
        
        # Clean up response
        response_text = re.sub(r"^(As an AI assistant|As CareNest)[,]*\s*", "", response_text).strip()
        response_text = re.sub(r"Here's what I (found|recommend):\s*", "", response_text).strip()
        
        # Format response appropriately
        response_text = format_response_points(response_text)

        # Log and return
        _update_history(session_id, user_input, response_text)
        return jsonify({"response": response_text})

    except Exception as e:
        print("Chat error:", e)
        return jsonify({"response": "⚠️ Sorry — I had trouble. Please try again."})

@app.route("/upload-photo", methods=["POST"])
def upload_photo():
    """
    multipart form: file + optional 'note'
    saves file under uploads/<session_id>_<securefilename>
    """
    try:
        session_id = get_session_id()
        if 'file' not in request.files:
            return jsonify({"error": "file missing"}), 400
        f = request.files['file']
        if f.filename == "":
            return jsonify({"error": "empty filename"}), 400
        filename = secure_filename(f.filename)
        saved_name = f"{session_id}_{secrets.token_hex(6)}_{filename}"
        path = os.path.join(UPLOAD_DIR, saved_name)
        f.save(path)
        # log
        log_patient_data(session_id, "wound", f"uploaded:{saved_name}")
        # Add a message that photo was uploaded
        bot_text = "Photo upload successful:\n\n• Photo received and saved securely\n• Added to your medical records\n• Will be included in doctor notifications if needed\n• Thank you for keeping track of your recovery!"
        _update_history(session_id, f"(uploaded photo {saved_name})", bot_text)
        return jsonify({"status": "ok", "file": saved_name, "message": bot_text})
    except Exception as e:
        print("upload error:", e)
        return jsonify({"error": "upload failed"}), 500

@app.route("/uploads/<path:fn>")
def serve_upload(fn):
    return send_from_directory(UPLOAD_DIR, fn)

@app.route("/report", methods=["GET"])
def report_http():
    session_id = get_session_id()
    return jsonify({"weekly_report": generate_report_text(session_id)})

# ---------------- Report generator ----------------
def generate_report_text(session_id):
    logs = patient_logs.get(session_id, {})
    lines = []
    # Pain summary
    pains = logs.get("pain", [])
    if pains:
        lines.append(f"📌 Pain logs: {len(pains)} entries — last: {pains[-1]['value']}")
    else:
        lines.append("📌 Pain logs: no entries yet.")
    # Medication
    meds = logs.get("medication", [])
    lines.append(f"💊 Medication logs: {len(meds)} entries.")
    # Mobility
    mobility = logs.get("mobility", [])
    if mobility:
        total_steps = 0
        for m in mobility:
            mm = re.search(r'(\d+)\s*steps', m["value"])
            if mm:
                total_steps += int(mm.group(1))
        if total_steps > 0:
            lines.append(f"🚶 Mobility: total steps recorded {total_steps}. Last: {mobility[-1]['value']}")
        else:
            lines.append(f"🚶 Mobility logs: {len(mobility)} entries.")
    else:
        lines.append("🚶 Mobility: no logs yet.")
    # Mood
    mood = logs.get("mood", [])
    if mood:
        sample = [m["value"] for m in mood[-7:]]  # last 7
        lines.append(f"🙂 Recent mood samples: {', '.join(sample[-3:])}")
    else:
        lines.append("🙂 Mood: no entries yet.")
    # Symptoms & wounds
    sym = logs.get("symptoms", [])
    lines.append(f"⚠️ Symptom reports: {len(sym)}")
    wounds = logs.get("wound", [])
    lines.append(f"🩺 Wound/photo uploads: {len(wounds)}")
    # Alerts
    alerts = alerts_store.get(session_id, [])
    if alerts:
        lines.append(f"🚨 Active alerts: {len(alerts)} — last: {alerts[-1]['reason']}")
    else:
        lines.append("🔍 No active alerts.")
    return "\n".join(lines)

# ---------------- Run ----------------
if __name__ == "__main__":
    try:
        print("Starting CareNest app...")
        app.run(debug=True)
    finally:
        try:
            scheduler.shutdown()
        except Exception:
            pass