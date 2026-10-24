import os
from functools import wraps
from flask import Flask, render_template, redirect, url_for, session, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

from gmail_service import GmailAnalyzer

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def oauth_is_configured():
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
    secret_key = (os.getenv("SECRET_KEY") or "").strip()

    placeholder_values = {
        "GOOGLE_CLIENT_ID": client_id,
        "GOOGLE_CLIENT_SECRET": client_secret,
        "SECRET_KEY": secret_key,
    }

    for value in placeholder_values.values():
        if not value:
            return False
        lowered = value.lower()
        if "your_" in lowered or "your-" in lowered or "change-me" in lowered or "example" in lowered or "replace-me" in lowered:
            return False

    return True


def app_base_url():
    configured = os.getenv("APP_BASE_URL") or ""
    candidates = []
    for item in configured.split(","):
        item = item.strip()
        if item:
            candidates.append(item.rstrip("/"))
    if not candidates:
        host = request.host or "127.0.0.1:5000"
        scheme = "https" if request.is_secure else "http"
        candidates = [f"{scheme}://{host}"]
    for candidate in candidates:
        if candidate.startswith("http://127.0.0.1") or candidate.startswith("http://localhost"):
            return candidate
    return candidates[0]


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY") or "dev-secret-change-me"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "app.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
oauth = OAuth(app)

google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile https://www.googleapis.com/auth/gmail.readonly",
        "access_type": "offline",
        "prompt": "consent",
    },
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True, nullable=False)
    picture = db.Column(db.Text)

class GmailToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    access_token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text)
    token_uri = db.Column(db.Text, default="https://oauth2.googleapis.com/token")

with app.app_context():
    db.create_all()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({
                    "error": "Your session has expired. Please log in again."
                }), 401
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def analyzer_for_current_user():
    token = GmailToken.query.filter_by(user_id=session["user_id"]).first()
    if not token:
        return None
    return GmailAnalyzer(
        access_token=token.access_token,
        refresh_token=token.refresh_token,
        token_uri=token.token_uri,
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    )

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/login")
def login():
    if not oauth_is_configured():
        return render_template(
            "oauth_error.html",
            message="Google OAuth is not configured yet.",
            details="Add valid GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and SECRET_KEY values to your .env file before signing in.",
        ), 503

    redirect_uri = url_for("auth_callback", _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route("/auth/callback")
def auth_callback():
    token = google.authorize_access_token()
    userinfo = token.get("userinfo")
    if not userinfo:
        userinfo = google.userinfo()

    google_id = userinfo["sub"]
    email = userinfo["email"]

    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        user = User.query.filter_by(email=email).first()

    if not user:
        user = User(
            google_id=google_id,
            name=userinfo.get("name", email.split("@")[0]),
            email=email,
            picture=userinfo.get("picture"),
        )
        db.session.add(user)
        db.session.flush()
    else:
        user.google_id = google_id
        user.name = userinfo.get("name", user.name)
        user.picture = userinfo.get("picture", user.picture)

    refresh_token = token.get("refresh_token")
    old = GmailToken.query.filter_by(user_id=user.id).first()

    if old:
        old.access_token = token["access_token"]
        if refresh_token:
            old.refresh_token = refresh_token
    else:
        db.session.add(GmailToken(
            user_id=user.id,
            access_token=token["access_token"],
            refresh_token=refresh_token,
        ))

    db.session.commit()
    session["user_id"] = user.id
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
@login_required
def dashboard():
    user = db.session.get(User, session["user_id"])
    return render_template("dashboard.html", user=user)


import traceback

@app.route("/api/emails")
@login_required
def api_emails():
    try:
        # Keep analyzer creation inside try:
        # Gmail credentials, API connection, or model loading can fail here.
        analyzer = analyzer_for_current_user()

        if not analyzer:
            return jsonify({
                "error": "Gmail is not connected. Please sign in again."
            }), 401

        limit = min(max(int(request.args.get("limit", 25)), 1), 50)
        emails = analyzer.fetch_and_classify(limit)

        return jsonify({"emails": emails})

    except Exception as exc:
        traceback.print_exc()

        app.logger.exception("Failed to fetch or classify Gmail messages")

        return jsonify({
            "error": f"{type(exc).__name__}: {str(exc)}"
        }), 500


@app.route("/api/stats")
@login_required
def api_stats():
    analyzer = analyzer_for_current_user()
    if not analyzer:
        return jsonify({"error": "Gmail is not connected."}), 401

    try:
        emails = analyzer.fetch_and_classify(50)
        total = len(emails)
        spam = sum(e["spam"] for e in emails)
        categories = {}
        for e in emails:
            categories[e["category"]] = categories.get(e["category"], 0) + 1
        return jsonify({
            "total": total,
            "spam": spam,
            "safe": total - spam,
            "spam_rate": round((spam / total) * 100, 1) if total else 0,
            "categories": categories,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
