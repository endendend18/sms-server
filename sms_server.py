from flask import Flask, request, jsonify, render_template_string
from datetime import datetime
import re
from collections import defaultdict

app = Flask(__name__)
messages = []

# HTML 테이블 페이지 템플릿
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>문자 내역</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        input { padding: 6px; width: 300px; margin-bottom: 15px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
        th { background-color: #f4f4f4; }
        .입금 { color: blue; font-weight: bold; }
        .출금 { color: red; font-weight: bold; }
    </style>
</head>
<body>
    <h1>입출금 문자 내역</h1>
    <form method="get">
        <input type="text" name="q" placeholder="검색어를 입력하세요 (이름, 날짜, 입금 등)" value="{{ q }}" />
        <button type="submit">검색</button>
    </form>
    <table>
        <thead>
            <tr>
                <th>은행</th>
                <th>날짜</th>
                <th>시간</th>
                <th>구분</th>
                <th>금액</th>
                <th>이름</th>
                <th>잔액</th>
            </tr>
        </thead>
        <tbody>
            {% for msg in messages %}
            <tr>
                <td>{{ msg.device }}</td>
                <td>{{ msg.date }}</td>
                <td>{{ msg.time }}</td>
                <td class="{{ msg.type }}">{{ msg.type }}</td>
                <td>{{ "{:,}".format(msg.amount) }}</td>
                <td>{{ msg.name }}</td>
                <td>{{ "{:,}".format(msg.balance) }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</body>
</html>
"""

# 통계용 템플릿
STATS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>통계</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <h1>월별/일별 입출금 통계</h1>
    <canvas id="monthlyChart" width="800" height="400"></canvas>
    <canvas id="dailyChart" width="800" height="400"></canvas>
    <script>
        const monthlyData = {{ monthly_data | safe }};
        const dailyData = {{ daily_data | safe }};
        new Chart(document.getElementById('monthlyChart'), {
            type: 'bar',
            data: {
                labels: monthlyData.labels,
                datasets: [
                    { label: '입금', backgroundColor: 'blue', data: monthlyData.income },
                    { label: '출금', backgroundColor: 'red', data: monthlyData.expense }
                ]
            }
        });

        new Chart(document.getElementById('dailyChart'), {
            type: 'line',
            data: {
                labels: dailyData.labels,
                datasets: [
                    { label: '입금', borderColor: 'blue', data: dailyData.income, fill: false },
                    { label: '출금', borderColor: 'red', data: dailyData.expense, fill: false }
                ]
            }
        });
    </script>
</body>
</html>
"""

def parse_message(raw):
    lines = raw.strip().split("\n")

    type_ = ""
    amount = 0
    name = ""
    balance = 0
    date = ""
    time = ""

    for line in lines:
        if "입금" in line or "출금" in line:
            type_ = "입금" if "입금" in line else "출금"
            amount_match = re.search(r'[\d,]+', line)
            if amount_match:
                amount = int(amount_match.group().replace(",", ""))
        elif "잔액" in line:
            balance_match = re.search(r'[\d,]+', line)
            if balance_match:
                balance = int(balance_match.group().replace(",", ""))
        elif re.match(r'\d{2}/\d{2}', line):
            date, time = line.strip().split(" ")
    
    # 이름은 마지막 줄 기준으로
    name = lines[-2].strip() if len(lines) >= 2 else ""

    return type_, amount, name, balance, date, time

@app.route("/receive", methods=["POST"])
def receive_sms():
    data = request.json
    print("[DEBUG] 수신된 문자:", data.get("message", ""))  # ← 요 줄 추가!
    type_, amount, name, balance, date, time = parse_message(data.get("message", ""))

    entry = {
        "device": data.get("device", ""),
        "message": data.get("message", ""),
        "date": date,
        "time": time,
        "type": type_,
        "amount": amount,
        "name": name,
        "balance": balance,
        "received_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    messages.append(entry)
    return jsonify({"status": "ok"})

@app.route("/data", methods=["GET"])
def show_messages():
    q = request.args.get("q", "").lower()
    filtered = [msg for msg in messages if q in msg["name"].lower() or q in msg["type"] or q in msg["date"] or q in msg["device"]]
    return render_template_string(HTML_TEMPLATE, messages=filtered, q=q)

@app.route("/stats")
def show_stats():
    monthly_income = defaultdict(int)
    monthly_expense = defaultdict(int)
    daily_income = defaultdict(int)
    daily_expense = defaultdict(int)

    for msg in messages:
        if not msg['date']:
            continue
        date_obj = datetime.strptime(f"2025/{msg['date']}", "%Y/%m/%d")
        month_key = date_obj.strftime("%Y-%m")
        day_key = date_obj.strftime("%Y-%m-%d")

        if msg['type'] == '입금':
            monthly_income[month_key] += msg['amount']
            daily_income[day_key] += msg['amount']
        elif msg['type'] == '출금':
            monthly_expense[month_key] += msg['amount']
            daily_expense[day_key] += msg['amount']

    months = sorted(set(monthly_income.keys()) | set(monthly_expense.keys()))
    days = sorted(set(daily_income.keys()) | set(daily_expense.keys()))

    monthly_data = {
        "labels": months,
        "income": [monthly_income[m] for m in months],
        "expense": [monthly_expense[m] for m in months]
    }
    daily_data = {
        "labels": days,
        "income": [daily_income[d] for d in days],
        "expense": [daily_expense[d] for d in days]
    }

    return render_template_string(STATS_TEMPLATE, monthly_data=monthly_data, daily_data=daily_data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
