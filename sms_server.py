from flask import Flask, request, jsonify, render_template_string
from datetime import datetime, timezone, timedelta
import re
import uuid
from collections import defaultdict

app = Flask(__name__)
messages = []

# HTML 테이블 페이지 템플릿
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>문자 내역</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            padding: 20px;
            background-color: #3C3F41;
            color: #f1f1f1;
        }

        input {
            padding: 6px;
            width: 300px;
            margin-bottom: 15px;
            background-color: #4B4E50;
            color: #ffffff;
            border: 1px solid #666;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            background-color: #2E2E2E;
            color: #f1f1f1;
        }

        th, td {
            border: 1px solid #555;
            padding: 8px;
            text-align: left;
        }

        th {
            background-color: #4B4E50;
            color: #ffffff;
        }

        .입금 {
            color: #4FC3F7;
            font-weight: bold;
        }

        .출금 {
            color: #FF8A65;
            font-weight: bold;
        }
        th {
            text-align: center;
        }

        td.bank,
        td.date,
        td.time,
        td.type,
        td.name {
            text-align: center;
        }

        td.amount,
        td.balance {
            text-align: right;
            padding-right: 12px;
        }

        /* 은행별 글자 색 (연한 색상 + 굵은 글씨) */
        td.bank.모모 {
            color: #F8CBAD;
            font-weight: bold;
        }
        td.bank.타이틀 {
            color: #BDD7EE;
            font-weight: bold;
        }
        td.bank.블루 {
            color: #C6E0B4;
            font-weight: bold;
        }

        /* 금액 / 잔액 컬러도 통일 */
        td.amount.모모,
        td.balance.모모 {
            color: #F8CBAD;
            font-weight: bold;
        }
        td.amount.타이틀,
        td.balance.타이틀 {
            color: #BDD7EE;
            font-weight: bold;
        }
        td.amount.블루,
        td.balance.블루 {
            color: #C6E0B4;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <h2>입출금 문자 내역</h2>
    <form method="get">
        <input type="text" name="q" placeholder="검색어를 입력하세요" value="{{ q }}">
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
        <tbody id="table-body">
            {% for msg in messages %}
            <tr>
                <td class="bank {% if msg.device == '모모' %}모모{% elif msg.device == '타이틀' %}타이틀{% elif msg.device == '블루' %}블루{% endif %}">
                    {{ msg.device }}
                </td>
                <td class="date">{{ msg.date }}</td>
                <td class="time">{{ msg.time }}</td>
                <td class="type {{ msg.type }}">{{ msg.type }}</td>
                <td class="amount {% if msg.device == '모모' %}모모{% elif msg.device == '타이틀' %}타이틀{% elif msg.device == '블루' %}블루{% endif %}">
                    {{ "{:,}".format(msg.amount) }}
                </td>
                <td class="name">{{ msg.name }}</td>
                <td class="balance {% if msg.device == '모모' %}모모{% elif msg.device == '타이틀' %}타이틀{% elif msg.device == '블루' %}블루{% endif %}">
                    {{ "{:,}".format(msg.balance) }}
                </td>
            </tr>
            {% endfor %}
        </tbody>
        </table>

<script>
    setInterval(() => {
        fetch('/data-part')
            .then(res => res.text())
            .then(html => {
                document.getElementById('table-body').innerHTML = html;
            });
    }, 5000);
</script>

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

def parse_message(raw, device):
    lines = raw.strip().split("\n")

    type_ = ""
    amount = 0
    name = ""
    balance = 0
    date = ""
    time = ""

    if device == "모모":
        # 모모폰 전용 파싱
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
        
        name = lines[-1].strip() if len(lines) >= 1 else ""

        # 날짜/시간은 서버 시간 기준으로 처리
        now = datetime.now(timezone(timedelta(hours=9)))
        date = now.strftime("%m/%d")
        time = now.strftime("%H:%M")
        return type_, amount, name, balance, date, time

    if device in ["타이틀", "블루"]:
        # 타이틀 & 블루폰 파싱
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

        name = lines[-2].strip() if len(lines) >= 2 else ""
        return type_, amount, name, balance, date, time

    return type_, amount, name, balance, date, time

@app.route("/receive", methods=["POST"])
def receive_sms():
    data = request.json
    device = data.get("device", "")
    raw_message = data.get("message", "")

    type_, amount, name, balance, date, time = parse_message(raw_message, device)

    entry = {
        "id": str(uuid.uuid4()),
        "device": device,
        "message": raw_message,
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
    filtered = [
        msg for msg in messages
        if q in msg["name"].lower() or q in f"{msg['amount']}"
    ]
    # 최신 순 정렬
    filtered.sort(key=lambda x: x["received_at"], reverse=True)
    return render_template_string(HTML_TEMPLATE, messages=filtered, q=q)

@app.route("/data-part")
def data_part():
    q = request.args.get("q", "").lower()
    filtered = [
        msg for msg in messages
        if q in msg["name"].lower() or q in f"{msg['amount']}"
    ]
    filtered.sort(key=lambda x: x["received_at"], reverse=True)
    return render_template_string("""
        {% for msg in messages %}
        <tr>
            <td class="bank {{ msg.device }}">{{ msg.device }}</td>
            <td class="date">{{ msg.date }}</td>
            <td class="time">{{ msg.time }}</td>
            <td class="type {{ msg.type }}">{{ msg.type }}</td>
            <td class="amount">{{ "{:,}".format(msg.amount) }}</td>
            <td class="name">{{ msg.name }}</td>
            <td class="balance">{{ "{:,}".format(msg.balance) }}</td>
        </tr>
        {% endfor %}
    """, messages=filtered)

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
