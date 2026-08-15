import logging
import hashlib
import time
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from square.client import Client

load_dotenv()

# إعداد التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# إعدادات Square
SQUARE_ACCESS_TOKEN = os.getenv('SQUARE_ACCESS_TOKEN')
SQUARE_ENVIRONMENT = os.getenv('SQUARE_ENVIRONMENT', 'sandbox')
SQUARE_LOCATION_ID = os.getenv('SQUARE_LOCATION_ID')
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

# تهيئة التطبيق
app = Flask(__name__)
CORS(app)

# تهيئة Square Client
def get_square_client():
    env = 'production' if SQUARE_ENVIRONMENT == 'production' else 'sandbox'
    return Client(access_token=SQUARE_ACCESS_TOKEN, environment=env)

client = get_square_client()
payments_api = client.payments

# دالة مساعدة لتوليد مفتاح idempotency
def generate_idempotency_key(identifier):
    key_string = f"{identifier}_{time.time()}"
    return hashlib.md5(key_string.encode()).hexdigest()

# ==================== نقاط النهاية ====================

@app.route('/api/payment/process', methods=['POST'])
def process_payment():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        nonce = data.get('nonce')
        amount = data.get('amount')
        order_id = data.get('order_id')
        currency = data.get('currency', 'USD')
        
        if not nonce:
            return jsonify({'success': False, 'error': 'Missing card nonce'}), 400
        
        if not amount:
            return jsonify({'success': False, 'error': 'Missing amount'}), 400
        
        # بناء طلب الدفع
        request_body = {
            "idempotency_key": generate_idempotency_key(order_id or 'payment'),
            "source_id": nonce,
            "amount_money": {
                "amount": amount,
                "currency": currency
            },
            "location_id": SQUARE_LOCATION_ID,
            "autocomplete": True
        }
        
        if order_id:
            request_body["note"] = f"Order #{order_id}"
            request_body["order_id"] = str(order_id)
        
        # تنفيذ الدفع
        result = payments_api.create_payment(request_body)
        
        if result.is_success():
            payment = result.body.get('payment', {})
            logger.info(f"Payment successful: {payment.get('id')}")
            return jsonify({
                'success': True,
                'payment_id': payment.get('id'),
                'status': payment.get('status'),
                'amount': payment.get('amount_money', {}).get('amount'),
                'currency': payment.get('amount_money', {}).get('currency'),
                'receipt_url': payment.get('receipt_url')
            }), 200
        else:
            error = result.errors[0] if result.errors else None
            return jsonify({
                'success': False,
                'error': error.get('detail') if error else 'Unknown error'
            }), 400
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/payment/status/<payment_id>', methods=['GET'])
def get_payment_status(payment_id):
    try:
        result = payments_api.get_payment(payment_id)
        if result.is_success():
            return jsonify({
                'success': True,
                'payment': result.body.get('payment', {})
            }), 200
        else:
            return jsonify({'success': False, 'error': 'Payment not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/payment/cancel/<payment_id>', methods=['POST'])
def cancel_payment(payment_id):
    try:
        result = payments_api.cancel_payment(payment_id)
        if result.is_success():
            return jsonify({'success': True, 'message': 'Payment cancelled'}), 200
        else:
            return jsonify({'success': False, 'error': 'Could not cancel payment'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/payment/refund', methods=['POST'])
def refund_payment():
    try:
        data = request.get_json()
        payment_id = data.get('payment_id')
        amount = data.get('amount')
        reason = data.get('reason', 'Refund')
        
        if not payment_id:
            return jsonify({'success': False, 'error': 'Missing payment_id'}), 400
        
        # إذا لم يحدد المبلغ، نسترد المبلغ كامل
        if not amount:
            payment_info = payments_api.get_payment(payment_id)
            if payment_info.is_success():
                amount = payment_info.body.get('payment', {}).get('amount_money', {}).get('amount')
            else:
                return jsonify({'success': False, 'error': 'Could not get payment amount'}), 400
        
        request_body = {
            "idempotency_key": generate_idempotency_key(f"{payment_id}_refund"),
            "payment_id": payment_id,
            "amount_money": {
                "amount": amount,
                "currency": "USD"
            },
            "reason": reason
        }
        
        result = payments_api.refund_payment(request_body)
        
        if result.is_success():
            return jsonify({
                'success': True,
                'refund': result.body.get('refund', {})
            }), 200
        else:
            return jsonify({'success': False, 'error': 'Refund failed'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/webhook/square', methods=['POST'])
def square_webhook():
    """استقبال Webhook من Square - بدون تحقق (للتسهيل)"""
    try:
        data = request.get_json()
        event_type = data.get('type')
        logger.info(f"Webhook received: {event_type}")
        
        # هنا تقدر تسوي اللي تبي بالحدث
        if event_type == 'payment.created':
            payment = data.get('data', {}).get('object', {}).get('payment', {})
            logger.info(f"Payment created: {payment.get('id')}")
        
        return jsonify({'handled': True}), 200
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'environment': SQUARE_ENVIRONMENT
    }), 200


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=DEBUG)
