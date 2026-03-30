import json
import time
import requests
from datetime import datetime, timezone, timedelta

TELEGRAM_TOKEN = "8274486251:AAERpZL8rwtncgpp10lQAITIxDG-OccgD_c"
CHAT_ID = "7355977539"
GROQ_API_KEY = "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"
TWELVEDATA_KEY = "649938dfc63f4ea0bd2ab3d90044bd71"
SCAN_INTERVAL = 300

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_dubai_time():
    return datetime.now(timezone(timedelta(hours=4)))

def get_session(hour):
    if 17 <= hour < 19: return "London/NY Overlap - BEST"
    elif hour >= 17 or hour < 1: return "New York"
    elif 11 <= hour < 19: return "London"
    elif 1 <= hour < 9: return "Asia"
    else: return "Off-hours"

def get_live_price():
    try:
        url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={TWELVEDATA_KEY}"
        r = requests.get(url, timeout=10)
        data = r.json()
        price = float(data["price"])
        print(f"Live price: {price}")
        return price
    except Exception as e:
        print(f"Price error: {e}")
        return None

def get_candles():
    try:
        url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=5min&outputsize=50&apikey={TWELVEDATA_KEY}"
        r = requests.get(url, timeout=15)
        data = r.json()
        candles = data.get("values", [])
        result = []
        for c in candles[:20]:
            result.append({
                "time": c["datetime"],
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"])
            })
        result.reverse()
        return result
    except Exception as e:
        print(f"Candles error: {e}")
        return []

def analyze(price, candles, session, dubai_time):
    time_str = dubai_time.strftime("%A %d %b %Y %H:%M")
    candles_str = json.dumps(candles[-10:])

    prompt = f"""You are an expert XAUUSD scalp trader using the ToriTrades trendline strategy.

Current time: {time_str} Dubai. Session: {session}.
Current LIVE gold price: {price}

Last 10 candles (5min): {candles_str}

STRATEGY RULES:
1. Draw uptrend line connecting swing lows (at least 2-3 touch points)
2. Draw downtrend line connecting swing highs (at least 2-3 touch points)
3. ACTION LINE = the trendline that breaks (triggers the trade)
4. SAFETY LINE = opposite trendline (our stop loss reference)
5. BUY signal: price breaks ABOVE downtrend line with momentum
6. SELL signal: price breaks BELOW uptrend line with momentum
7. Entry = current price after break confirmation
8. SL = below/above the broken trendline (10-15 pips away)
9. TP = next Point of Interest or opposite trendline
10. Only trade during London or NY sessions
11. Minimum R:R = 2:1

Analyze the candles and give signal based on real price {price}.

Respond ONLY with raw JSON:
{{"signal":"BUY","entry":{price},"sl":0.0,"tp":0.0,"rr":0.0,"action_line":"downtrend broken","safety_line":"uptrend support","reason":"explanation"}}

If no setup use signal "NONE" and 0 for numbers."""

    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "max_tokens": 300, "temperature": 0.2},
            timeout=30)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()
        s, e = content.find("{"), content.rfind("}") + 1
        return json.loads(content[s:e])
    except Exception as e:
        print(f"Groq error: {e}")
        return None

def format_msg(r, t, price):
    sig = r.get("signal")
    if sig == "NONE": return None
    entry = r.get("entry", price)
    sl = r.get("sl", 0)
    tp = r.get("tp", 0)
    rr = r.get("rr", 0)
    emoji = "🟢" if sig == "BUY" else "🔴"
    action = "▲ اشتري" if sig == "BUY" else "▼ بيع"
    sl_pips = abs(entry - sl)
    tp_pips = abs(tp - entry)

    return f"""{emoji} <b>XAUUSD — {action} دلوقتي!</b>
🕐 {t.strftime("%H:%M")} دبي | {r.get("session_quality", "")}

💰 <b>السعر الحالي: ${price:.2f}</b>

📍 <b>ادخل عند:</b> {entry:.2f}
🛑 <b>Stop Loss:</b> {sl:.2f} ({sl_pips:.1f} نقطة)
🎯 <b>Take Profit:</b> {tp:.2f} ({tp_pips:.1f} نقطة)
⚖️ <b>R:R:</b> {rr:.1f}:1

📊 <b>السبب:</b>
{r.get("reason", "")}

⚠️ <i>دايما استخدم ادارة رأس المال</i>"""

def main():
    print("Bot started with LIVE prices!")
    send_telegram("🤖 <b>XAUUSD Bot شغال بأسعار حقيقية!</b>\nهيبعتلك إشارة لما يلاقي فرصة ✅")
    while True:
        try:
            t = get_dubai_time()
            session = get_session(t.hour)
            print(f"\n[{t.strftime('%H:%M')}] Scanning | {session}")
            price = get_live_price()
            if not price:
                print("No price, retrying...")
                time.sleep(60)
                continue
            candles = get_candles()
            result = analyze(price, candles, session, t)
            if result and result.get("signal") != "NONE":
                msg = format_msg(result, t, price)
                if msg:
                    send_telegram(msg)
                    print(f"Signal: {result.get('signal')} @ {price}")
            else:
                print(f"No setup. Price: {price}")
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main()
