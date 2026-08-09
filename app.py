import os
import stripe
from flask import Flask, request, jsonify

app = Flask(__name__)

# اقرأ المفتاح من متغيرات البيئة (سنضيفها في Render لاحقًا)
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

@app.route('/create-payment-intent', methods=['POST'])
def create_payment_intent():
    try:
        data = request.get_json()
        amount = data.get('amount')  # بالسنت (مثلاً 1000 = 10.00 دولار)
        
        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='usd',
            automatic_payment_methods={'enabled': True}
        )
        
        return jsonify({'client_secret': intent.client_secret})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    # ستضيف كود التحقق من التوقيع لاحقًا
    event = request.get_json()
    # تعامل مع حدث payment_intent.succeeded هنا
    return 'OK', 200

@app.route('/')
def home():
    return 'Stripe server is running!'

if __name__ == '__main__':
    app.run(debug=True)