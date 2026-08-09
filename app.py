import os
import json
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# اقرأ المفاتيح من متغيرات البيئة في Render
SQUARE_APPLICATION_ID = os.environ.get('SQUARE_APPLICATION_ID')
SQUARE_ACCESS_TOKEN = os.environ.get('SQUARE_ACCESS_TOKEN')

# رابط Square API (للاختبار)
SQUARE_API_URL = "https://connect.squareupsandbox.com/v2/payments"

@app.route('/')
def home():
    return 'Square backend is running!'

@app.route('/create-payment', methods=['POST'])
def create_payment():
    try:
        data = request.get_json()
        
        # المبلغ المطلوب من Flutter (بالسنت)
        amount = data.get('amount')
        currency = data.get('currency', 'USD')
        source_id = data.get('source_id')  # معرف بطاقة العميل من Flutter

        # تحضير الطلب لـ Square API
        payload = {
            "source_id": source_id,
            "idempotency_key": os.urandom(24).hex(),  # مفتاح فريد لمنع الدفع المكرر
            "amount_money": {
                "amount": amount,
                "currency": currency
            }
        }

        headers = {
            "Authorization": f"Bearer {SQUARE_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "Square-Version": "2023-10-18"
        }

        # إرسال الطلب إلى Square
        response = requests.post(SQUARE_API_URL, json=payload, headers=headers)
        result = response.json()

        if response.status_code == 200:
            return jsonify({"success": True, "payment": result})
        else:
            return jsonify({"success": False, "error": result}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    # استقبال إشعارات الدفع من Square (ستضيفه لاحقًا)
    event = request.get_json()
    print(f"Webhook received: {event}")
    return 'OK', 200

if __name__ == '__main__':
    app.run(debug=True)
