from flask import Flask, request, jsonify, render_template, redirect, url_for
import sqlite3
import requests
from datetime import datetime
import os
from dotenv import load_dotenv

# ---------------------------
# Load .env
# ---------------------------
dotenv_path = r"C:\Users\hamid\OneDrive\Desktop\weather\.env"
load_dotenv(dotenv_path=dotenv_path)

API_KEY = os.getenv("OWM_API_KEY")
if not API_KEY:
    raise RuntimeError(f"Set OWM_API_KEY in .env at {dotenv_path}")

# ---------------------------
# Flask setup
# ---------------------------
app = Flask(__name__, template_folder="templates")
DB_FILE = "weather.db"

# ---------------------------
# Database helper
# ---------------------------
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# Create table if not exists
with get_db() as db:
    db.execute("""
        CREATE TABLE IF NOT EXISTS weather (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT,
            temperature REAL,
            description TEXT,
            dt TEXT
        )
    """)
    db.commit()

# ---------------------------
# Routes
# ---------------------------

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        city = request.form.get("city", "").strip()
        if city:
            return redirect(url_for("show_weather_page", city=city))
    return render_template("main.html")

@app.route("/api/weather", methods=["POST"])
def api_weather():
    data = request.get_json(force=True)
    city = data.get("city", "").strip()
    if not city:
        return jsonify({"error": "City required"}), 400
    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "appid": API_KEY, "units": "metric"},
            timeout=8
        )
        if resp.status_code != 200:
            return jsonify({"error": "City not found or API error"}), 404

        js = resp.json()
        out = {
            "city": city,
            "temperature": js.get("main", {}).get("temp"),
            "description": (js.get("weather") or [{}])[0].get("description", ""),
            "dt": datetime.now().strftime("%d-%b-%Y %I:%M:%S %p")
        }

        db = get_db()
        db.execute(
            "INSERT INTO weather (city, temperature, description, dt) VALUES (?, ?, ?, ?)",
            (out["city"], out["temperature"], out["description"], out["dt"])
        )
        db.commit()
        db.close()
        return jsonify(out), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Current weather
@app.route("/weather/<city>")
def show_weather_page(city):
    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "appid": API_KEY, "units": "metric"},
            timeout=8
        )
        if resp.status_code != 200:
            return f"No data found for '{city}'", 404
        js = resp.json()
        row = {
            "city": city,
            "temperature": js["main"]["temp"],
            "description": js["weather"][0]["description"],
            "dt": datetime.now().strftime("%d-%b-%Y %I:%M:%S %p")
        }
        db = get_db()
        db.execute(
            "INSERT INTO weather (city, temperature, description, dt) VALUES (?, ?, ?, ?)",
            (row["city"], row["temperature"], row["description"], row["dt"])
        )
        db.commit()
        db.close()
        return render_template(
            "result.html",
            city=row["city"],
            temp=row["temperature"],
            desc=row["description"],
            dt=row["dt"]
        )
    except Exception as e:
        return f"Error: {e}", 500

# Today weather
@app.route("/weather/<city>/today")
def today_weather(city):
    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "appid": API_KEY, "units": "metric"},
            timeout=8
        )
        if resp.status_code != 200:
            return f"No data found for '{city}'", 404
        js = resp.json()
        today_high = js.get("main", {}).get("temp_max")
        today_low = js.get("main", {}).get("temp_min")
        icon = (js.get("weather") or [{}])[0].get("description", "☀️")
        return render_template(
            "today.html",
            city=city,
            today_high=today_high,
            today_low=today_low,
            icon=icon
        )
    except Exception as e:
        return f"Error: {e}", 500

# Hourly weather (next 24 hours)
@app.route("/weather/<city>/hourly")
def hourly_weather(city):
    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/forecast",
            params={"q": city, "appid": API_KEY, "units": "metric"},
            timeout=8
        )
        if resp.status_code != 200:
            return f"No hourly data found for '{city}'", 404
        data = resp.json().get("list", [])[:8]  # next 24 hours (3-hour intervals)
        return render_template("hourly.html", city=city, data=data)
    except Exception as e:
        return f"Error: {e}", 500

# Daily weather (next 5 days)
@app.route("/weather/<city>/daily")
def daily_weather(city):
    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/forecast",
            params={"q": city, "appid": API_KEY, "units": "metric"},
            timeout=8
        )
        if resp.status_code != 200:
            return f"No daily data found for '{city}'", 404

        raw = resp.json().get("list", [])
        daily = {}
        for item in raw:
            date = item["dt_txt"].split()[0]
            temp = item["main"]["temp"]
            if date not in daily:
                daily[date] = {"min": temp, "max": temp}
            else:
                daily[date]["min"] = min(daily[date]["min"], temp)
                daily[date]["max"] = max(daily[date]["max"], temp)

        daily_list = [{"date": k, "min": v["min"], "max": v["max"]} for k, v in daily.items()]
        return render_template("daily.html", city=city, data=daily_list)
    except Exception as e:
        return f"Error: {e}", 500

# Weekly weather (uses same 5-day forecast)
@app.route("/weather/<city>/weekly")
def weekly_weather(city):
    return daily_weather(city)  # for simplicity, show same as daily

# History API
@app.route("/api/history")
def api_history():
    try:
        db = get_db()
        rows = db.execute(
            "SELECT city, temperature, description, dt FROM weather ORDER BY id DESC LIMIT 6"
        ).fetchall()
        db.close()
        return jsonify([dict(row) for row in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------
# Run Flask
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
