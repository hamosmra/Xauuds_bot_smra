import json
import time
import requests
from datetime import datetime, timezone, timedelta

TELEGRAM_TOKEN = “8274486251:AAERpZL8rwtncgpp10lQAITIxDG-OccgD_c”
CHAT_ID = “7355977539”
GROQ_API_KEY = “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”
TWELVEDATA_KEY = “649938dfc63f4ea0bd2ab3d90044bd71”
SCAN_INTERVAL = 300  # 5 minutes
MIN_RR = 1.5

def send_telegram(msg):
url = f”https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage”
try:
requests.post(url, json={“chat_id”: CHAT_ID, “text”: msg, “parse_mode”: “HTML”}, timeout=10)
except Exception as e:
print(f”Telegram error: {e}”)

def get_dubai_time():
return datetime.now(timezone(timedelta(hours=4)))

def get_session(hour):
if 17 <= hour < 21: return “London/NY Overlap”
elif hour >= 17 or hour < 1: return “New York”
elif 11 <= hour < 17: return “London”
elif 1 <= hour < 9: return “Asia”
else: return “Off-hours”

def get_live_price():
try:
url = f”https://api.twelvedata.com/price?symbol=XAU/USD&apikey={TWELVEDATA_KEY}”
r = requests.get(url, timeout=10)
price = float(r.json()[“price”])
print(f”Live price: {price}”)
return price
except Exception as e:
print(f”Price error: {e}”)
return None

def get_candles(interval, outputsize=30):
try:
url = f”https://api.twelvedata.com/time_series?symbol=XAU/USD&interval={interval}&outputsize={outputsize}&apikey={TWELVEDATA_KEY}”
r = requests.get(url, timeout=15)
candles = r.json().get(“values”, [])
result = []
for c in candles:
result.append({
“time”: c[“datetime”],
“open”: float(c[“open”]),
“high”: float(c[“high”]),
“low”: float(c[“low”]),
“close”: float(c[“close”])
})
result.reverse()
return result
except Exception as e:
print(f”Candles error ({interval}): {e}”)
return []

def analyze(price, candles_m5, candles_h1, session, dubai_time):
time_str = dubai_time.strftime(”%A %d %b %Y %H:%M”)
m5_str = json.dumps(candles_m5[-20:])
h1_str = json.dumps(candles_h1[-10:])

```
prompt = f"""You are an expert XAUUSD scalp trader. Time: {time_str} Dubai. Session: {session}.
```

Live gold price: {price}

H1 candles (last 10, for trend & S/R): {h1_str}
M5 candles (last 20, for entry): {m5_str}

STRATEGY - Mixed approach (only signal if ALL conditions met):

STEP 1 - H1 Trend:

- Identify overall trend from H1 (uptrend/downtrend/ranging)
- Draw trendline with MINIMUM 2 touch points on H1
- Identify key Support and Resistance levels from H1

STEP 2 - M5 Entry Zone:

- Price must be near H1 Support (for BUY) or H1 Resistance (for SELL)
- Look for Fair Value Gap (FVG) near the S/R zone
- RSI on M5: oversold (<35) for BUY, overbought (>65) for SELL
- NOT in neutral RSI zone (40-60)

STEP 3 - Entry Trigger:

- BUY: H1 uptrend + price at support + FVG above + M5 breaks recent high + retest + RSI oversold
- SELL: H1 downtrend + price at resistance + FVG below + M5 breaks recent low + retest + RSI overbought

STEP 4 - Filters:

- R:R minimum {MIN_RR}:1
- Only trade London or NY session
- Ranging H1 market = NONE
- No confirmation = NONE

Respond ONLY with raw JSON, no extra text:
{{“signal”:“BUY”,“entry”:{price},“sl”:0.0,“tp”:0.0,“rr”:0.0,“support”:0.0,“resistance”:0.0,“h1_trend”:“uptrend”,“fvg_present”:true,“rsi_m5”:0.0,“trendline_touches”:2,“reason”:“short explanation”}}”””

```
try:
    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={"model": "llama-3.3-70b-versatile",
              "messages": [{"role": "user", "content": prompt}],
              "max_tokens": 400, "temperature": 0.1},
        timeout=30)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"].strip()
    s, e = content.find("{"), content.rfind("}") + 1
    result = json.loads(content[s:e])

    if result.get("signal") != "NONE":
        rr = float(result.get("rr", 0))
        fvg = result.get("fvg_present", False)
        rsi = float(result.get("rsi_m5", 50))
        h1_trend = result.get("h1_trend", "ranging")
        signal = result.get("signal")

        # Filter checks
        if rr < MIN_RR:
            print(f"Rejected: RR={rr} too low")
            result["signal"] = "NONE"
        elif not fvg:
            print(f"Rejected: No FVG")
            result["signal"] = "NONE"
        elif h1_trend == "ranging":
            print(f"Rejected: H1 ranging")
            result["signal"] = "NONE"
        elif signal == "BUY" and rsi > 45:
            print(f"Rejected: RSI={rsi} not oversold for BUY")
            result["signal"] = "NONE"
        elif signal == "SELL" and rsi < 55:
            print(f"Rejected: RSI={rsi} not overbought for SELL")
            result["signal"] = "NONE"

    return result
except Exception as e:
    print(f"Groq error: {e}")
    return None
```

def format_msg(r, t, price):
sig = r.get(“signal”)
if sig == “NONE”: return None
entry = float(r.get(“entry”, price))
sl = float(r.get(“sl”, 0))
tp = float(r.get(“tp”, 0))
rr = float(r.get(“rr”, 0))
rsi = float(r.get(“rsi_m5”, 0))
h1_trend = r.get(“h1_trend”, “”)
support = float(r.get(“support”, 0))
resistance = float(r.get(“resistance”, 0))
sl_pips = abs(entry - sl)
tp_pips = abs(tp - entry)
emoji = “🟢” if sig == “BUY” else “🔴”
action = “▲ اشتري” if sig == “BUY” else “▼ بيع”
trend_ar = “📈 صاعد” if h1_trend == “uptrend” else “📉 هابط”

```
return f"""{emoji} <b>XAUUSD — {action} دلوقتي!</b>
```

🕐 {t.strftime(”%H:%M”)} دبي

💰 <b>السعر الحالي: ${price:.2f}</b>

📍 <b>ادخل عند:</b> {entry:.2f}
🛑 <b>Stop Loss:</b> {sl:.2f} ({sl_pips:.1f} نقطة)
🎯 <b>Take Profit:</b> {tp:.2f} ({tp_pips:.1f} نقطة)
⚖️ <b>R:R:</b> {rr:.1f}:1

📊 <b>الاتجاه H1:</b> {trend_ar}
🔵 <b>دعم:</b> {support:.2f} | <b>مقاومة:</b> {resistance:.2f}
✅ <b>FVG:</b> موجود
📉 <b>RSI M5:</b> {rsi:.0f}

📝 {r.get(“reason”,””)}
⚠️ <i>دايما استخدم ادارة رأس المال</i>”””

def main():
print(“Bot started - Mixed Strategy (H1 trend + M5 entry)!”)
send_telegram(“🤖 <b>XAUUSD Bot شغال!</b>\n📊 استراتيجية مدمجة: H1 اتجاه + M5 دخول\n✅ دعم/مقاومة + FVG + RSI + Trendline”)
last_signal = None
last_signal_time = None

```
while True:
    try:
        t = get_dubai_time()
        session = get_session(t.hour)
        print(f"\n[{t.strftime('%H:%M')}] Scanning | {session}")

        if session in ["Off-hours", "Asia"]:
            print("Outside trading hours, skipping...")
            time.sleep(300)
            continue

        price = get_live_price()
        if not price:
            time.sleep(60)
            continue

        candles_m5 = get_candles("5min", 30)
        candles_h1 = get_candles("1h", 15)

        if not candles_m5 or not candles_h1:
            print("No candles data")
            time.sleep(60)
            continue

        result = analyze(price, candles_m5, candles_h1, session, t)

        if result and result.get("signal") != "NONE":
            sig = result.get("signal")
            if last_signal == sig and last_signal_time:
                diff = (t - last_signal_time).seconds / 60
                if diff < 30:
                    print(f"Same signal {sig} {diff:.0f} mins ago, skip")
                    time.sleep(SCAN_INTERVAL)
                    continue
            msg = format_msg(result, t, price)
            if msg:
                send_telegram(msg)
                print(f"Signal sent: {sig} @ {price}")
                last_signal = sig
                last_signal_time = t
        else:
            print(f"No setup. Price: {price}")

    except Exception as e:
        print(f"Error: {e}")
    time.sleep(SCAN_INTERVAL)
```

if **name** == “**main**”:
main()
