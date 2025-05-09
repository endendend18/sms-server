from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
from datetime import datetime, timezone, timedelta
import re
import uuid
from collections import defaultdict
import pandas as pd  # 엑셀 저장용
import os

app = Flask(__name__)
app.secret_key = "아무거나_복잡한_문자열"  # 세션 유지를 위한 키

# 사용자 목록 (아이디: 비밀번호)
USERS = {
    "대장": "dldkdus1!",
    "뚱이": "dlwkdgns1!",
    "순두부": "18184848a",
    "대봉": "18184848a"
}

messages = []
current_date = None 

# 날짜 변경 시 엑셀 저장 + 초기화
def check_date_reset():
    global current_date, messages
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    if current_date is None:
        current_date = today
    elif today != current_date:
        save_to_excel()
        current_date = today
        messages = []

# 로그인 페이지 템플릿
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>로그인</title>
    <style>
        body {
            background-color: #3C3F41;
            color: #f1f1f1;
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        .login-box {
            background-color: #2E2E2E;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0,0,0,0.4);
            text-align: center;
        }
        input {
            padding: 10px;
            width: 250px;
            margin: 10px 0;
            background-color: #4B4E50;
            color: white;
            border: 1px solid #666;
            border-radius: 4px;
        }
        input[type="submit"] {
            background-color: #5C5C5C;
            cursor: pointer;
        }
        input[type="submit"]:hover {
            background-color: #7A7A7A;
        }
        label {
            display: block;
            margin-top: 15px;
            text-align: left;
        }
        .error {
            color: #FF7373;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>로그인</h2>
        <form method="POST" action="/login">
            <label for="id">ID:</label>
            <input type="text" name="id" id="id"><br>
            <label for="pw">비밀번호:</label>
            <input type="password" name="pw" id="pw"><br>
            <input type="submit" value="로그인">
        </form>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
    </div>
</body>
</html>
"""

ADD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>수동 데이터 추가</title>
    <style>
        body {
            background-color: #3C3F41;
            color: #f1f1f1;
            font-family: Arial, sans-serif;
            padding: 10px; /* 수정: 20px → 10px */
        }
        input, select {
            padding: 6px;
            margin: 5px;
            background-color: #4B4E50;
            color: white;
            border: 1px solid #666;
        }
        input[type="submit"] {
            background-color: #5C5C5C;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <h2>수동 데이터 추가</h2>
    <form method="POST">
        은행:
        <select name="device">
            <option value="모모">모모</option>
            <option value="타이틀">타이틀</option>
            <option value="블루">블루</option>
        </select><br>
        날짜 (MM/DD): <input type="text" name="date"><br>
        시간 (HH:MM): <input type="text" name="time"><br>
        구분:
        <select name="type">
            <option value="입금">입금</option>
            <option value="출금">출금</option>
        </select><br>
        금액: <input type="text" name="amount"><br>
        이름: <input type="text" name="name"><br>
        잔액: <input type="text" name="balance"><br>
        <input type="submit" value="추가">
    </form>
    <br><a href="/data" style="color: #aaa;">← 돌아가기</a>
</body>
</html>
"""

EDIT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>항목 수정</title>
    <style>
        body {
            background-color: #3C3F41;
            color: #f1f1f1;
            font-family: Arial, sans-serif;
            padding: 20px;
        }
        input, select {
            padding: 8px;
            margin: 5px;
            background-color: #4B4E50;
            color: white;
            border: 1px solid #666;
        }
        input[type="submit"] {
            background-color: #5C5C5C;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <h2>항목 수정</h2>
    <form method="POST">
        은행:
        <select name="device">
            <option value="모모" {% if msg.device == '모모' %}selected{% endif %}>모모</option>
            <option value="타이틀" {% if msg.device == '타이틀' %}selected{% endif %}>타이틀</option>
            <option value="블루" {% if msg.device == '블루' %}selected{% endif %}>블루</option>
        </select><br>
        날짜 (MM/DD): <input type="text" name="date" value="{{ msg.date }}"><br>
        시간 (HH:MM): <input type="text" name="time" value="{{ msg.time }}"><br>
        구분:
        <select name="type">
            <option value="입금" {% if msg.type == '입금' %}selected{% endif %}>입금</option>
            <option value="출금" {% if msg.type == '출금' %}selected{% endif %}>출금</option>
        </select><br>
        금액: <input type="text" name="amount" value="{{ "{:,}".format(msg.amount) }}"><br>
        이름: <input type="text" name="name" value="{{ msg.name }}"><br>
        잔액: <input type="text" name="balance" value="{{ "{:,}".format(msg.balance) }}"><br>
        <input type="submit" value="수정 완료">
    </form>
    <br><a href="/data" style="color: #aaa;">← 돌아가기</a>
</body>
</html>
"""

# HTML 테이블 페이지 템플릿
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>List</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            padding: 10px;
            background-color: #3C3F41;
            color: #f1f1f1;
        }

            input {
            padding: 6px;
            width: 150px;
            margin-bottom: 5px;  /* 수정: 15px → 5px */
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
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
        <!-- 왼쪽: 검색창 -->
        <form method="get" style="margin: 0;">
            <input type="text" name="q" placeholder="검색어를 입력하세요" value="{{ q }}">
        </form>

        <!-- 오른쪽: 추가/로그아웃 버튼 -->
        <div>
            <a href="#" onclick="openModal()" style="
                font-size: 12px;
                background-color: #555;
                color: white;
                padding: 3px 6px;
                text-decoration: none;
                border-radius: 3px;
                margin-left: 5px;
            ">📝</a>

            <a href="/logout" style="
                font-size: 12px;
                background-color: #555;
                color: white;
                padding: 3px 6px;
                text-decoration: none;
                border-radius: 3px;
            ">✖️</a>
        </div>
    </div>

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
                <th>수정</th>
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
                <td style="text-align: center;">
                    <a href="#" onclick="openEditModal('{{ msg.id }}')" style="text-decoration: none; color: #4FC3F7;">✏️</a>
                </td>
            </tr>
            {% endfor %}
        </tbody>
        </table>

<script>
    // ✅ 테이블 데이터 5초마다 갱신
    setInterval(() => {
        fetch('/data-part')
            .then(res => res.text())
            .then(html => {
                document.getElementById('table-body').innerHTML = html;
            });
    }, 5000);

    // ✅ 현재 수정하려는 ID (없으면 추가로 처리)
    let editTargetId = null;

    // ✅ 추가 버튼 클릭 → 모달 열기
    function openModal() {
        editTargetId = null;
        showPasswordModal();
    }

    // ✅ 수정 버튼 클릭 → 모달 열기
    function openEditModal(id) {
        editTargetId = id;
        showPasswordModal();
    }

    // ✅ 비밀번호 모달 열기
    function showPasswordModal() {
        document.getElementById('passwordModal').style.display = 'block';
        document.getElementById('passwordInput').value = '';
    }

    // ✅ 비밀번호 모달 닫기
    function closeModal() {
        document.getElementById('passwordModal').style.display = 'none';
        editTargetId = null;
    }

    // ✅ 비밀번호 확인 후 이동
    function checkPassword() {
        const password = document.getElementById('passwordInput').value;
        if (password === '1234') {
            if (editTargetId) {
                // 수정 페이지로
                window.location.href = "/edit/" + editTargetId;
            } else {
                // 추가 페이지로
                window.location.href = "/add";
            }
        } else {
            alert("비밀번호가 틀렸습니다.");
    // 비밀번호 틀렸을 때 입력창 비우기 (편의성 향상)
            document.getElementById('passwordInput').value = '';
        }
    }
</script>

<!-- 비밀번호 입력 모달 -->
    <div id="passwordModal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background-color: rgba(0,0,0,0.5); z-index: 9999;">
        <div style="background-color: #2E2E2E; color: white; padding: 20px; border-radius: 10px; width: 300px; margin: 100px auto; text-align: center;">
            <h3>비밀번호 입력</h3>
            <input type="password" id="passwordInput"
                style="padding: 8px; width: 80%; background-color: #4B4E50; color:white; border: 1px solid #666;"
                onkeydown="if(event.key === 'Enter') checkPassword();"><br><br>
            <button onclick="checkPassword()" style="padding: 6px 12px; background-color: #5C5C5C; color:white;">확인</button>
            <button onclick="closeModal()" style="padding: 6px 12px; background-color: #555;">취소</button>
        </div>
    </div>
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

        now = datetime.now(timezone(timedelta(hours=9)))
        date = now.strftime("%m/%d")
        time = now.strftime("%H:%M")
        return type_, amount, name, balance, date, time

    if device == "타이틀":
        try:
            for i, line in enumerate(lines):
                line = line.strip()

                # 1행: 입금/출금
                if i == 0 and ("입금" in line or "출금" in line):
                    type_ = "입금" if "입금" in line else "출금"
                    amount_match = re.search(r'\d[\d,]*', line)
                    if amount_match:
                        amount = int(amount_match.group().replace(",", ""))

                # 2행: 날짜 + 시간
                elif i == 1:
                    dt_match = re.match(r'(\d{2}/\d{2}) (\d{2}:\d{2})', line)
                    if dt_match:
                        date, time = dt_match.groups()

                # 3행: 이름 + 잔액
                elif i == 2 and "잔액" in line:
                    parts = line.split("잔액")
                    name_candidate = parts[0].strip() if len(parts) > 0 else ""
                    if name_candidate:
                        name = name_candidate
                    balance_match = re.search(r'\d[\d,]*', parts[1]) if len(parts) > 1 else None
                    if balance_match:
                        balance = int(balance_match.group().replace(",", ""))

        except Exception as e:
            print("타이틀 파싱 오류:", e)

        return type_, amount, name, balance, date, time
        
    if device == "블루":
        for i, line in enumerate(lines):
            line = line.strip()
            if re.match(r'\d{2}/\d{2} \d{2}:\d{2}', line):
                date, time = line.split()
            elif "입금" in line or "출금" in line:
                type_ = "입금" if "입금" in line else "출금"
                amount_match = re.search(r'[\d,]+', line)
                if amount_match:
                    amount = int(amount_match.group().replace(",", ""))
            elif "잔액" in line:
                balance_match = re.search(r'[\d,]+', line)
                if balance_match:
                    balance = int(balance_match.group().replace(",", ""))
            elif not name and type_ in ["입금", "출금"]:
                if "잔액" not in line and not re.match(r'\d{2}/\d{2} \d{2}:\d{2}', line):
                    name = line.strip()

        return type_, amount, name, balance, date, time

    return type_, amount, name, balance, date, time

# 날짜/시간 처리 함수나 변수 아래
# ↓↓↓ 여기에 추가 ↓↓↓
def save_to_excel():
    global messages
    if not messages:
        return

    now = datetime.now(timezone(timedelta(hours=9)))
    today_str = now.strftime("%Y-%m-%d")
    folder = "history"
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, f"{today_str}.xlsx")

    df = pd.DataFrame(messages)
    df.to_excel(filepath, index=False)

@app.route("/receive", methods=["POST"])
def receive_sms():
    check_date_reset()
    
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



@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        user_id = request.form.get("id")
        user_pw = request.form.get("pw")
        if user_id in USERS and USERS[user_id] == user_pw:
            session["logged_in"] = True
            return redirect(url_for("show_messages"))
        else:
            error = "ID 또는 비밀번호가 잘못되었습니다."
    return render_template_string(LOGIN_TEMPLATE, error=error)

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect("/login")

@app.route("/data", methods=["GET"])
def show_messages():
    if not session.get("logged_in"):
        return redirect("/login")
        
    q = request.args.get("q", "").lower()
    filtered = [
        msg for msg in messages
        if q in msg["name"].lower() or q in f"{msg['amount']}"
    ]

    # ✅ date + time 기준으로 최신순 정렬
    filtered.sort(
        key=lambda x: datetime.strptime(f"2025/{x['date']} {x['time']}", "%Y/%m/%d %H:%M"),
        reverse=True
    )

    return render_template_string(HTML_TEMPLATE, messages=filtered, q=q)

@app.route("/add", methods=["GET", "POST"])
def add_entry():
    if not session.get("logged_in"):
        return redirect("/login")

    if request.method == "POST":
        entry = {
            "id": str(uuid.uuid4()),
            "device": request.form.get("device"),
            "date": request.form.get("date"),
            "time": request.form.get("time"),
            "type": request.form.get("type"),
            "amount": int(request.form.get("amount", "0").replace(",", "") or "0"),
            "name": request.form.get("name"),
            "balance": int(request.form.get("balance", "0").replace(",", "") or "0"),
            "message": "수동 입력",
            "received_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        messages.append(entry)
        return redirect("/data")

    return render_template_string(ADD_TEMPLATE)

@app.route("/edit/<id>", methods=["GET", "POST"])
def edit_entry(id):
    if not session.get("logged_in"):
        return redirect("/login")

    # 수정할 메시지 찾기
    msg = next((m for m in messages if m["id"] == id), None)
    if not msg:
        return "해당 항목을 찾을 수 없습니다.", 404

    if request.method == "POST":
        msg["device"] = request.form.get("device")
        msg["date"] = request.form.get("date")
        msg["time"] = request.form.get("time")
        msg["type"] = request.form.get("type")
        msg["amount"] = int(request.form.get("amount", "0").replace(",", "") or "0")
        msg["name"] = request.form.get("name")
        msg["balance"] = int(request.form.get("balance", "0").replace(",", "") or "0")
        return redirect("/data")

    return render_template_string(EDIT_TEMPLATE, msg=msg)

@app.route("/data-part")
def data_part():
    q = request.args.get("q", "").lower()
    filtered = [
        msg for msg in messages
        if q in msg["name"].lower() or q in f"{msg['amount']}"
    ]

    # ✅ date + time 기준으로 최신순 정렬
    filtered.sort(
        key=lambda x: datetime.strptime(f"2025/{x['date']} {x['time']}", "%Y/%m/%d %H:%M"),
        reverse=True
    )

    return render_template_string("""
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
            <td style="text-align: center;">
                <a href="#" onclick="openEditModal('{{ msg.id }}')" style="text-decoration: none; color: #4FC3F7;">✏️</a>
            </td>
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
    app.run(host="0.0.0.0", port=10000, debug=True)
