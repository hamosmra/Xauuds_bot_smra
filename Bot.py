import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta

TELEGRAM_TOKEN = "8274486251:AAERpZL8rwtncgpp10lQAITIxDG-OccgD_c"
CHAT_ID = "7355977539"
GROQ_API_KEY = "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"
SCAN_INTERVAL = 300
MIN_RR = 2.0
TIMEFRAME = "5m"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_dubai_time():
    return datetime.now(timezone(timedelta(hours=4)))

def get_session(hour):
    if 17 <= hour < 19: return "London/NY Overlap BEST"
    elif hour >= 17 or hour < 1: return "New York"
    elif 11 <= hour < 19: return "London"
    elif 1 <= hour < 9: return "Asia"
    else: return "Off-hours"

def analyze(dubai_time, session):
    prompt = f"""You are an expert XAUUSD scalp trader. Time: {dubai_time.strftime("%A %d %b %Y %H:%M")} Dubai. Session: {session}.

Analyze gold market on {TIMEFRAME} chart using:
1. Trendline identification and break
2. Fair Value Gap (FVG) at break zone
3. Formed High (FH) and Formed Low (FL)
Entry = trendline break + FVG confirmed. Min R:R = {MIN_RR}:1

Respond ONLY with raw JSON starting with {{ ending with }}:
{{"signal":"BUY","estimated_price":3050.00,"entry":3048.00,"sl":3038.00,"tp":3068.00,"rr":2.0,"fh":3065.00,"fl":3035.00,"trendline_broken":true,"fvg_present":true,"session_quality":"BEST","reason":"explanation here"}}
If no setup: signal = "NONE" and entry/sl/tp/rr/fh/fl = null"""

    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "max_tokens": 400, "temperature": 0.3},
            timeout=30)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()
        s, e = content.find("{"), content.rfind("}") + 1
        return json.loads(content[s:e])
    except Exception as e:
        print(f"Groq error: {e}")
        return None

def format_msg(r, t):
    sig = r.get("signal")
    if sig == "NONE": return None
    e, sl, tp, rr = r.get("entry"), r.get("sl"), r.get("tp"), r.get("rr")
    fh, fl = r.get("fh"), r.get("fl")
    emoji = "🟢" if sig == "BUY" else "🔴"
    return f"""{emoji} <b>XAUUSD {"▲" if sig=="BUY" else "▼"} {sig}</b>
🕐 {t.strftime("%H:%M")} Dubai | {r.get("session_quality","—")}
💰 Gold ~${r.get("estimated_price"):.2f}

📍 <b>Entry:</b> {e:.2f}
🛑 <b>Stop Loss:</b> {sl:.2f}
🎯 <b>Take Profit:</b> {tp:.2f}
⚖️ <b>R:R:</b> {rr:.1f}:1

✅ Trendline Break: {"Yes" if r.get("trendline_broken") else "No"}
✅ FVG: {"Yes" if r.get("fvg_present") else "No"}
FH: {f"{fh:.2f}" if fh else "—"} | FL: {f"{fl:.2f}" if fl else "—"}

📝 {r.get("reason","")}
⚠️ <i>AI analysis only. Use risk management.</i>"""

def main():
    print("Bot started!")
    send_telegram("🤖 <b>XAUUSD Bot Started!</b>\nScanning every 5 mins. Will alert you on signals ✅")
    while True:
        try:
            t = get_dubai_time()
            session = get_session(t.hour)
            print(f"[{t.strftime('%H:%M')}] Scanning... Session: {session}")
            result = analyze(t, session)
            if result and result.get("signal") != "NONE":
                msg = format_msg(result, t)
                if msg:
                    send_telegram(msg)
                    print(f"Signal sent: {result.get('signal')}")
            else:
                print("No setup found")
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main()
