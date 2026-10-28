import csv
import io
import json
import os
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from detector import analyze_message as rule_analyze_message
from ml_detector import predict_fraud_probability

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "payguard.db"
app.config["SECRET_KEY"] = os.environ.get("PAYGUARD_SECRET_KEY", "dev-only-change-this-secret-key")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
MAX_HISTORY = 50


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with get_db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user','admin')),
            created_at TEXT NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            message TEXT NOT NULL,
            score INTEGER NOT NULL,
            level TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            signals_json TEXT NOT NULL,
            tips_json TEXT NOT NULL,
            urls_found INTEGER NOT NULL DEFAULT 0,
            ml_score REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )""")
        # Migrate databases created by the previous version without losing history.
        columns = {r["name"] for r in con.execute("PRAGMA table_info(analysis_history)").fetchall()}
        if "user_id" not in columns:
            con.execute("ALTER TABLE analysis_history ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
        if "ml_score" not in columns:
            con.execute("ALTER TABLE analysis_history ADD COLUMN ml_score REAL NOT NULL DEFAULT 0")
        con.execute("CREATE INDEX IF NOT EXISTS idx_history_user_created ON analysis_history(user_id, created_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        # Seed one demo admin only when no account exists for that email.
        admin_email = os.environ.get("PAYGUARD_ADMIN_EMAIL", "admin@payguard.local").strip().lower()
        admin_password = os.environ.get("PAYGUARD_ADMIN_PASSWORD", "Admin@12345")
        exists = con.execute("SELECT id FROM users WHERE email = ?", (admin_email,)).fetchone()
        if not exists:
            con.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)", (
                "PayGuard Administrator", admin_email, generate_password_hash(admin_password), "admin", now_iso()))


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.startswith("/api/") or request.is_json:
                return jsonify({"error": "Please log in to continue.", "login_url": url_for("login")}), 401
            flash("Please log in to continue.", "error")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Administrator access required."}), 403
            flash("Administrator access required.", "error")
            return redirect(url_for("index"))
        return view(*args, **kwargs)
    return wrapped


def current_user_id():
    return int(session["user_id"])


def save_analysis(user_id, message, result, ml_score):
    with get_db() as con:
        cursor = con.execute("""INSERT INTO analysis_history
            (user_id,message,score,level,title,summary,signals_json,tips_json,urls_found,ml_score,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (
            user_id, message, int(result["score"]), result["level"], result["title"], result["summary"],
            json.dumps(result.get("signals", []), ensure_ascii=False), json.dumps(result.get("tips", []), ensure_ascii=False),
            int(result.get("urls_found", 0)), float(ml_score), now_iso()))
        return cursor.lastrowid


def row_to_record(row, include_message=False):
    record = {"id": row["id"], "score": row["score"], "level": row["level"], "title": row["title"],
        "summary": row["summary"], "signals": json.loads(row["signals_json"]), "tips": json.loads(row["tips_json"]),
        "urls_found": row["urls_found"], "ml_score": round(float(row["ml_score"] or 0), 4), "created_at": row["created_at"]}
    if include_message:
        record["message"] = row["message"]
    return record


@app.context_processor
def inject_user():
    return {"logged_in_user": {"name": session.get("name"), "role": session.get("role")} if session.get("user_id") else None}


@app.get("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("index"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if len(name) < 2 or len(name) > 80:
            flash("Name must be between 2 and 80 characters.", "error")
        elif len(email) > 254 or "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            flash("Enter a valid email address.", "error")
        elif len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        else:
            try:
                with get_db() as con:
                    con.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                        (name, email, generate_password_hash(password), "user", now_iso()))
                flash("Account created. Please log in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("An account with that email already exists.", "error")
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("admin_dashboard" if session.get("role") == "admin" else "index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with get_db() as con:
            user = con.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            next_url = request.args.get("next", "")
            if not next_url.startswith("/") or next_url.startswith("//"):
                next_url = url_for("admin_dashboard" if user["role"] == "admin" else "index")
            return redirect(next_url)
    return render_template("auth.html", mode="login")


@app.post("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.post("/analyze")
@login_required
def analyze():
    data = request.get_json(silent=True) or request.form
    message = (data.get("message") or "").strip()
    if len(message) < 8:
        return jsonify({"error": "Please enter a message with at least 8 characters so it can be analyzed."}), 400
    if len(message) > 5000:
        return jsonify({"error": "Please keep the message under 5,000 characters."}), 400
    ml_score = predict_fraud_probability(message)
    result = rule_analyze_message(message)
    # Combine model output with rule-based signals: the displayed score is an educational
    # hybrid indicator, not a calibrated real-world probability.
    hybrid_score = round(0.65 * (ml_score * 100) + 0.35 * result["score"])
    result["score"] = max(0, min(100, hybrid_score))
    if result["score"] >= 60:
        result.update(level="high", title="High risk indicators", summary="The model and/or text rules found several patterns that deserve careful verification.")
    elif result["score"] >= 30:
        result.update(level="medium", title="Some warning signs found", summary="This message has patterns worth checking carefully through official channels.")
    else:
        result.update(level="low", title="Fewer warning signs detected", summary="Fewer known patterns were detected. This does not prove the message is safe.")
    result["ml_probability"] = round(ml_score * 100, 1)
    result["model_note"] = "Illustrative scikit-learn model trained on a small bundled teaching dataset; not validated for real-world fraud decisions."
    record_id = save_analysis(current_user_id(), message, result, ml_score)
    result["record_id"] = record_id
    return jsonify(result)


@app.get("/history")
@login_required
def history():
    with get_db() as con:
        rows = con.execute("""SELECT id,score,level,title,summary,signals_json,tips_json,urls_found,ml_score,created_at
            FROM analysis_history WHERE user_id=? ORDER BY id DESC LIMIT ?""", (current_user_id(), MAX_HISTORY)).fetchall()
    return jsonify({"records": [row_to_record(row) for row in rows]})


@app.get("/history/<int:record_id>")
@login_required
def history_detail(record_id):
    with get_db() as con:
        row = con.execute("SELECT * FROM analysis_history WHERE id=? AND user_id=?", (record_id, current_user_id())).fetchone()
    if row is None:
        return jsonify({"error": "Analysis record not found."}), 404
    return jsonify(row_to_record(row, include_message=True))


@app.delete("/history")
@login_required
def clear_history():
    with get_db() as con:
        con.execute("DELETE FROM analysis_history WHERE user_id=?", (current_user_id(),))
    return jsonify({"message": "Your analysis history has been cleared."})


@app.get("/export.csv")
@login_required
def export_csv():
    with get_db() as con:
        rows = con.execute("""SELECT id,created_at,score,level,title,summary,urls_found,ml_score,message
            FROM analysis_history WHERE user_id=? ORDER BY id DESC""", (current_user_id(),)).fetchall()
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["id", "created_at", "risk_score", "risk_level", "title", "summary", "urls_found", "ml_fraud_score_percent", "message"])
    for row in rows:
        # Prefix formula-like text to reduce CSV formula injection risk in spreadsheet apps.
        values = list(row)
        for index, value in enumerate(values):
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
                values[index] = "'" + value
        values[7] = round(float(row["ml_score"] or 0) * 100, 1)
        writer.writerow(values)
    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=payguard_analysis_history.csv"
    return response


@app.get("/admin")
@admin_required
def admin_dashboard():
    with get_db() as con:
        users = con.execute("SELECT id,name,email,role,created_at FROM users ORDER BY id DESC").fetchall()
        stats = {
            "users": con.execute("SELECT COUNT(*) FROM users WHERE role='user'").fetchone()[0],
            "analyses": con.execute("SELECT COUNT(*) FROM analysis_history").fetchone()[0],
            "high": con.execute("SELECT COUNT(*) FROM analysis_history WHERE level='high'").fetchone()[0],
            "medium": con.execute("SELECT COUNT(*) FROM analysis_history WHERE level='medium'").fetchone()[0],
            "low": con.execute("SELECT COUNT(*) FROM analysis_history WHERE level='low'").fetchone()[0],
        }
        recent = con.execute("""SELECT h.id,h.created_at,h.score,h.level,h.title,u.name,u.email
            FROM analysis_history h LEFT JOIN users u ON h.user_id=u.id ORDER BY h.id DESC LIMIT 100""").fetchall()
    return render_template("admin.html", stats=stats, users=users, recent=recent)


@app.get("/admin/export.csv")
@admin_required
def admin_export_csv():
    with get_db() as con:
        rows = con.execute("""SELECT h.id,h.created_at,u.name,u.email,h.score,h.level,h.title,h.summary,h.urls_found,h.ml_score,h.message
            FROM analysis_history h LEFT JOIN users u ON h.user_id=u.id ORDER BY h.id DESC""").fetchall()
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["id", "created_at", "user_name", "user_email", "risk_score", "risk_level", "title", "summary", "urls_found", "ml_fraud_score_percent", "message"])
    for row in rows:
        values = list(row)
        for index, value in enumerate(values):
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
                values[index] = "'" + value
        values[9] = round(float(row["ml_score"] or 0) * 100, 1)
        writer.writerow(values)
    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=payguard_all_analysis_history.csv"
    return response


init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("PAYGUARD_DEBUG", "0") == "1")
