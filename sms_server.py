from flask import Flask, request, jsonify, render_template_string, request
from datetime import datetime
import re
from collections import defaultdict
app = Flask(name)
messages = []
HTML_TEMPLATE = """



    문자 내역
    
        body { font-family: Arial, sans-serif; padding: 20px; }
        input { padding: 6px; width: 300px; margin-bottom: 15px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
        th { background-color: #f4f4f4; }
        .입금 { color: blue; font-weight: bold; }
        .출금 { color: red; font-weight: bold; }
    


    입출금 문자 내역
    
        
        검색
    
    
        
            
                은행
                날짜
                시간
                구분
                금액
                이름
                잔액
            
        
        
            {% for msg in messages %}
            
                {{ msg.device }}
                {{ msg.date }}
                {{ msg.time }}
                {{ msg.type }}
                {{ "{:,}".format(msg.amount) }}
                {{ msg.name }}
                {{ "{:,}".format(msg.balance) }}
            
            {% endfor %}
        
    


"""
STATS_TEMPLATE = """



    통계
    


    월별/일별 입출금 통계
    
    
    
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



"""
def parse_message(raw):
type_match = re.search(r'(입금|출금)', raw)
amount_match = re.search(r'(입금|출금) ([\d,]+)원', raw)
name_match = re.search(r'\n(.*?)\n잔액', raw)
balance_match = re.search(r'잔액 ([\d,]+)', raw)
datetime_match = re.search(r'(\d{2}/\d{2}) (\d{2}:\d{2})', raw)
type_ = type_match.group(1) if type_match else ""
amount = int(amount_match.group(2).replace(",", "")) if amount_match else 0
name = name_match.group(1).strip() if name_match else ""
balance = int(balance_match.group(1).replace(",", "")) if balance_match else 0
date = datetime_match.group(1) if datetime_match else ""
time = datetime_match.group(2) if datetime_match else ""

return type_, amount, name, balance, date, time

@app.route("/receive", methods=["POST"])
def receive_sms():
data = request.json
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
    if not msg['date']: continue
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

if name == "main":
app.run(host="0.0.0.0", port=10000)
