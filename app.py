"""
KIDZEE Jammu - Institutional Preschool Web Portal & Admissions Engine
"""

import os
import re
import urllib.parse
import sqlite3
from pathlib import Path
from flask import Flask, render_template, request, jsonify, redirect, url_for, session

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "kidzee_jammu.db"

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "kidzee-jammu-secret-2026")

ADMIN_USERNAME = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASS", "KidzeeJammu@2026")
CENTRE_WHATSAPP_NUMBER = "919086800000"

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS site_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS programmes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                age_group TEXT NOT NULL,
                tagline TEXT NOT NULL,
                description TEXT NOT NULL,
                display_order INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS enquiries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT,
                child_name TEXT,
                child_dob_or_age TEXT,
                programme_code TEXT NOT NULL,
                visit_date TEXT,
                message TEXT,
                status TEXT DEFAULT 'New',
                admin_notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS page_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        defaults = [
            ("branch_name", "KIDZEE Jammu"),
            ("branch_address", "H.No : 125, New Rehari, Behind Shakuntla, Near Trikuta City Scan - 180001"),
            ("branch_phone", "+91 9086800000"),
            ("whatsapp_number", CENTRE_WHATSAPP_NUMBER),
            ("branch_email", "admissions.jammu@kidzee.org"),
            ("visiting_hours", "Monday to Saturday: 9:00 AM – 3:30 PM")
        ]
        conn.executemany("INSERT OR IGNORE INTO site_settings (key, value) VALUES (?, ?)", defaults)

        progs = [
            ("NUVO", "Nuvo", "1.5 – 2.5 Years", "Sensory Discovery & Motor Readiness",
             "A secure, gently scaffolded environment designed to ease the toddler's transition from home to social exploration with love and continuous care.", 1),
            ("PLAYGROUP", "Playgroup", "2.5 – 3.5 Years", "Curiosity & Social Immersion",
             "Encourages linguistic expression, peer play, tactile exploration, self-awareness, and foundational motor mastery.", 2),
            ("NURSERY", "Nursery", "3.5 – 4.5 Years", "Structured Inquiry & Expression",
             "Introduces phonemic recognition, early number sense, dynamic storytelling, spatial awareness, and collaborative habits.", 3),
            ("KINDERGARTEN", "Kindergarten", "4.5 – 6.0 Years", "Cognitive Synthesis & School Readiness",
             "Fosters full primary-school readiness through structured phonics, early arithmetic, and creative synthesis.", 4)
        ]
        conn.executemany("""
            INSERT OR IGNORE INTO programmes (code, name, age_group, tagline, description, display_order)
            VALUES (?, ?, ?, ?, ?, ?)
        """, progs)
    conn.close()

init_db()

def record_traffic(endpoint_name):
    try:
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        ua = request.headers.get("User-Agent", "Unknown")[:255]
        conn = get_db()
        with conn:
            conn.execute("INSERT INTO page_views (endpoint, ip_address, user_agent) VALUES (?, ?, ?)",
                         (endpoint_name, ip, ua))
        conn.close()
    except Exception:
        pass

@app.route("/")
def home():
    record_traffic("Home")
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM site_settings").fetchall()
    settings = {r["key"]: r["value"] for r in rows}

    prog_rows = conn.execute("SELECT * FROM programmes ORDER BY display_order ASC").fetchall()
    programmes = [dict(r) for r in prog_rows]
    conn.close()
    return render_template("index.html", settings=settings, programmes=programmes)

@app.route("/api/enquiry", methods=["POST"])
def submit_enquiry():
    data = request.get_json() or {}
    parent_name = data.get("parent_name", "").strip()
    phone = data.get("phone", "").strip()
    child_dob = data.get("child_dob_or_age", "").strip()
    programme_code = data.get("programme_code", "").strip()
    visit_date = data.get("visit_date", "").strip()
    message = data.get("message", "").strip()

    if not parent_name:
        return jsonify({"success": False, "message": "Parent/Guardian name is required."}), 400

    clean_phone = re.sub(r"[^\d+]", "", phone)
    digits_only = re.sub(r"[^\d]", "", clean_phone)
    if len(digits_only) < 10:
        return jsonify({"success": False, "message": "Please enter a valid 10-digit mobile number."}), 400

    conn = get_db()
    with conn:
        conn.execute("""
            INSERT INTO enquiries 
            (parent_name, phone, child_dob_or_age, programme_code, visit_date, message)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (parent_name, clean_phone, child_dob, programme_code, visit_date, message))
    conn.close()

    wa_text = (
        f"🎒 *New Admission Enquiry - KIDZEE Jammu*\n\n"
        f"👤 *Parent:* {parent_name}\n"
        f"📞 *Phone:* {phone}\n"
        f"👶 *Child Age/DOB:* {child_dob or 'N/A'}\n"
        f"📚 *Programme:* {programme_code}\n"
        f"📅 *Visit Requested:* {visit_date or 'None specified'}\n"
    )
    if message:
        wa_text += f"📝 *Note:* {message}\n"

    encoded = urllib.parse.quote(wa_text)
    wa_url = f"https://wa.me/{CENTRE_WHATSAPP_NUMBER}?text={encoded}"

    return jsonify({
        "success": True,
        "message": "Enquiry registered successfully! Redirecting to WhatsApp...",
        "whatsapp_url": wa_url
    })

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "").strip()
        if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        error = "Invalid credentials. Please verify your administrative access."
    return render_template("admin_login.html", error=error)

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.route("/admin")
def admin_dashboard():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    conn = get_db()
    total_views = conn.execute("SELECT COUNT(*) as cnt FROM page_views").fetchone()["cnt"]
    today_views = conn.execute("SELECT COUNT(*) as cnt FROM page_views WHERE date(timestamp) = date('now')").fetchone()["cnt"]

    enquiries_raw = conn.execute("SELECT * FROM enquiries ORDER BY created_at DESC").fetchall()
    enquiries = [dict(r) for r in enquiries_raw]
    total_enquiries = len(enquiries)
    new_enquiries = sum(1 for e in enquiries if e["status"] == "New")
    conv_rate = round((total_enquiries / total_views * 100), 1) if total_views > 0 else 0

    rows = conn.execute("SELECT key, value FROM site_settings").fetchall()
    settings = {r["key"]: r["value"] for r in rows}
    conn.close()

    stats = {
        "total_views": total_views,
        "today_views": today_views,
        "total_enquiries": total_enquiries,
        "new_enquiries": new_enquiries,
        "conversion_rate": conv_rate
    }
    return render_template("admin.html", enquiries=enquiries, stats=stats, settings=settings)

@app.route("/admin/save-settings", methods=["POST"])
def save_settings():
    if not session.get("is_admin"):
        return redirect(url_for("admin_login"))

    address = request.form.get("branch_address", "").strip()
    email = request.form.get("branch_email", "").strip()
    phone = request.form.get("branch_phone", "").strip()
    hours = request.form.get("visiting_hours", "").strip()

    conn = get_db()
    with conn:
        conn.execute("UPDATE site_settings SET value = ? WHERE key = 'branch_address'", (address,))
        conn.execute("UPDATE site_settings SET value = ? WHERE key = 'branch_email'", (email,))
        conn.execute("UPDATE site_settings SET value = ? WHERE key = 'branch_phone'", (phone,))
        conn.execute("UPDATE site_settings SET value = ? WHERE key = 'visiting_hours'", (hours,))
    conn.close()

    return redirect(url_for("admin_dashboard"))

@app.route("/admin/update-status", methods=["POST"])
def update_status():
    if not session.get("is_admin"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json() or {}
    eid, status = data.get("id"), data.get("status")
    if eid and status:
        conn = get_db()
        with conn:
            conn.execute("UPDATE enquiries SET status = ? WHERE id = ?", (status, eid))
        conn.close()
        return jsonify({"success": True})
    return jsonify({"success": False}), 400

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8000)