from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)
messages = []

@app.route("/receive", methods=["POST"])
def receive_sms():
    data = request.json
    data["received_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    messages.append(data)
    return jsonify({"status": "ok"}), 200

@app.route("/data", methods=["GET"])
def get_messages():
    return jsonify(messages)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
