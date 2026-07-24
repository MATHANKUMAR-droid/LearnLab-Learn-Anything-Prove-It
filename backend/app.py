"""
app.py
LearnLab -- AI-powered topic learning platform.

Flow:
  1. Sign up / sign in -> email OTP verification
  2. Type a topic -> AI-generated lesson + example cases + mock questions + video
  3. 20-question auto-generated test on that topic
  4. Certificate of completion (PDF) on passing

Every user, OTP, session, test attempt, and certificate is logged to
data/learnlab.xlsx via datastore.py.

Run:
  pip install -r requirements.txt
  python app.py
  open http://localhost:5000
"""

import os
import random
import secrets
import string
import uuid
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()  # reads backend/.env if present, so ANTHROPIC_API_KEY / SMTP_* can just be dropped in a file

from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

import datastore
import mailer
import content_generator
import certificate

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

# In-memory session token store: token -> {email, name, user_id}
# (Kept in memory rather than Excel since tokens are ephemeral; all durable
# facts -- users, OTPs, attempts, certificates -- are logged to Excel.)
SESSIONS = {}
# In-memory cache of the last generated test per session_id, so we can grade
# it server-side without trusting the client to send back correct answers.
TEST_CACHE = {}

OTP_TTL_MINUTES = 10
PASS_THRESHOLD = 60.0  # percentage required to pass and unlock the certificate


def _gen_otp():
    return "".join(random.choices(string.digits, k=6))


def _gen_token():
    return secrets.token_urlsafe(32)


def _require_auth():
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "").strip()
    return SESSIONS.get(token)


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(FRONTEND_DIR, path)


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "smtp_configured": mailer.smtp_configured(),
                     "ai_configured": content_generator._client() is not None})


# ---------------------------------------------------------------------------
# AUTH: sign up
# ---------------------------------------------------------------------------
@app.route("/api/auth/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are all required."}), 400
    if "@" not in email or "." not in email:
        return jsonify({"error": "Please enter a valid email address."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    existing = datastore.get_user_by_email(email)
    if existing and existing.get("email_verified"):
        return jsonify({"error": "An account with this email already exists. Try signing in instead."}), 409

    if not existing:
        user_id = str(uuid.uuid4())
        datastore.create_user(user_id, name, email, generate_password_hash(password))

    otp = _gen_otp()
    expires_at = (datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)).isoformat()
    datastore.save_otp(email, otp, "signup", expires_at)
    result = mailer.send_otp_email(email, otp, purpose="complete your sign-up")

    response = {"message": "Verification code sent.", "email": email, "dev_mode": result.get("dev_mode", False)}
    if result.get("dev_mode"):
        response["otp_code"] = result.get("otp_code")  # shown on-screen since no SMTP is configured
    return jsonify(response)


# ---------------------------------------------------------------------------
# AUTH: sign in (existing, verified user)
# ---------------------------------------------------------------------------
@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = datastore.get_user_by_email(email)
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Incorrect email or password."}), 401
    if not user.get("email_verified"):
        return jsonify({"error": "Please finish verifying your email first.", "needs_verification": True}), 403

    otp = _gen_otp()
    expires_at = (datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)).isoformat()
    datastore.save_otp(email, otp, "login", expires_at)
    result = mailer.send_otp_email(email, otp, purpose="sign in")

    response = {"message": "Verification code sent.", "email": email, "dev_mode": result.get("dev_mode", False)}
    if result.get("dev_mode"):
        response["otp_code"] = result.get("otp_code")
    return jsonify(response)


# ---------------------------------------------------------------------------
# AUTH: verify OTP (shared by signup + login)
# ---------------------------------------------------------------------------
@app.route("/api/auth/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    code = str(data.get("otp") or "").strip()
    purpose = data.get("purpose", "signup")

    record = datastore.get_latest_valid_otp(email, purpose)
    if not record:
        return jsonify({"error": "No pending verification code found. Please request a new one."}), 400
    if str(record["otp_code"]) != code:
        return jsonify({"error": "Incorrect code. Please try again."}), 400
    if datetime.utcnow() > datetime.fromisoformat(record["expires_at"]):
        return jsonify({"error": "This code has expired. Please request a new one."}), 400

    datastore.mark_otp_used(email, code)
    if purpose == "signup":
        datastore.mark_user_verified(email)

    user = datastore.get_user_by_email(email)
    token = _gen_token()
    SESSIONS[token] = {"email": email, "name": user["name"], "user_id": user["user_id"]}

    return jsonify({
        "message": "Verified.",
        "token": token,
        "user": {"name": user["name"], "email": email},
    })


@app.route("/api/auth/resend-otp", methods=["POST"])
def resend_otp():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    purpose = data.get("purpose", "signup")

    user = datastore.get_user_by_email(email)
    if not user:
        return jsonify({"error": "No account found for this email."}), 404

    otp = _gen_otp()
    expires_at = (datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)).isoformat()
    datastore.save_otp(email, otp, purpose, expires_at)
    result = mailer.send_otp_email(email, otp, purpose="verify your account")

    response = {"message": "A new code has been sent.", "dev_mode": result.get("dev_mode", False)}
    if result.get("dev_mode"):
        response["otp_code"] = result.get("otp_code")
    return jsonify(response)


# ---------------------------------------------------------------------------
# LEARNING: generate a lesson for a student-described topic
# ---------------------------------------------------------------------------
@app.route("/api/learn/generate", methods=["POST"])
def learn_generate():
    user = _require_auth()
    if not user:
        return jsonify({"error": "Please sign in first."}), 401

    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "Please describe a topic you'd like to learn about."}), 400
    if len(topic) > 200:
        return jsonify({"error": "Topic is too long -- please keep it under 200 characters."}), 400

    lesson = content_generator.generate_lesson(topic)

    session_id = str(uuid.uuid4())
    datastore.create_session(session_id, user["user_id"], user["email"], topic)

    lesson["session_id"] = session_id
    lesson["topic"] = topic
    return jsonify(lesson)


# ---------------------------------------------------------------------------
# TEST: generate the 20-question test, and submit it for grading
# ---------------------------------------------------------------------------
@app.route("/api/test/generate", methods=["POST"])
def test_generate():
    user = _require_auth()
    if not user:
        return jsonify({"error": "Please sign in first."}), 401

    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or "").strip()
    session_id = data.get("session_id")
    if not topic:
        return jsonify({"error": "Missing topic."}), 400

    questions = content_generator.generate_full_test(topic, num_questions=20)

    # Cache full questions (with answers) server-side, only send safe view to client
    TEST_CACHE[session_id] = questions
    safe_questions = [
        {"question": q["question"], "options": q["options"]} for q in questions
    ]
    return jsonify({"session_id": session_id, "topic": topic, "questions": safe_questions})


@app.route("/api/test/submit", methods=["POST"])
def test_submit():
    user = _require_auth()
    if not user:
        return jsonify({"error": "Please sign in first."}), 401

    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    topic = (data.get("topic") or "").strip()
    answers = data.get("answers", [])  # list of selected option indices (or null)

    questions = TEST_CACHE.get(session_id)
    if not questions:
        return jsonify({"error": "Test session expired. Please regenerate the test."}), 400

    results = []
    score = 0
    for i, q in enumerate(questions):
        selected = answers[i] if i < len(answers) else None
        correct = q["answer_index"]
        is_correct = selected == correct
        if is_correct:
            score += 1
        results.append({
            "question": q["question"],
            "options": q["options"],
            "selected_index": selected,
            "correct_index": correct,
            "is_correct": is_correct,
            "explanation": q.get("explanation", ""),
        })

    total = len(questions)
    percentage = round((score / total) * 100, 1) if total else 0
    passed = percentage >= PASS_THRESHOLD

    attempt_id = str(uuid.uuid4())
    datastore.record_test_attempt(attempt_id, session_id, user["user_id"], user["email"],
                                   topic, score, total, percentage, passed)

    return jsonify({
        "attempt_id": attempt_id,
        "score": score,
        "total": total,
        "percentage": percentage,
        "passed": passed,
        "pass_threshold": PASS_THRESHOLD,
        "results": results,
    })


# ---------------------------------------------------------------------------
# CERTIFICATE
# ---------------------------------------------------------------------------
@app.route("/api/certificate/generate", methods=["POST"])
def certificate_generate():
    user = _require_auth()
    if not user:
        return jsonify({"error": "Please sign in first."}), 401

    data = request.get_json(silent=True) or {}
    topic = (data.get("topic") or "").strip()
    percentage = float(data.get("percentage", 0))

    if percentage < PASS_THRESHOLD:
        return jsonify({"error": f"A score of at least {PASS_THRESHOLD}% is required for a certificate."}), 400

    certificate_id = str(uuid.uuid4())[:8].upper()
    path = certificate.generate_certificate_pdf(
        certificate_id=certificate_id,
        user_name=user["name"],
        topic=topic,
        score_percentage=percentage,
    )
    file_name = os.path.basename(path)
    datastore.record_certificate(certificate_id, user["user_id"], user["email"],
                                  user["name"], topic, percentage, file_name)

    return jsonify({"certificate_id": certificate_id, "download_url": f"/api/certificate/{certificate_id}/download"})


@app.route("/api/certificate/<certificate_id>/download")
def certificate_download(certificate_id):
    cert_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "certificates")
    filename = f"certificate_{certificate_id}.pdf"
    full_path = os.path.join(cert_dir, filename)
    if not os.path.exists(full_path):
        return jsonify({"error": "Certificate not found."}), 404
    return send_file(full_path, as_attachment=True, download_name=f"LearnLab_Certificate_{certificate_id}.pdf")


# ---------------------------------------------------------------------------
# ADMIN / TRANSPARENCY: download the full Excel workbook of logged data
# ---------------------------------------------------------------------------
@app.route("/api/data/export")
def data_export():
    path = datastore.workbook_path()
    return send_file(path, as_attachment=True, download_name="learnlab_data.xlsx")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
