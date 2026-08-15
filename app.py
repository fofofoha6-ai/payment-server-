import os
import hashlib
import time
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from square.client import Client

# إعدادات بسيطة
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# جلب المتغيرات من البيئة (Render)
SQUARE_ACCESS_TOKEN = os.environ.get('SQUARE_ACCESS_TOKEN')
SQUARE_ENVIRONMENT = os.environ.get('SQUARE_ENVIRONMENT', 'sandbox')
SQUARE_LOCATION_ID = os.environ.get('SQUARE_LOCATION_ID')

# التحقق من وجود المفاتيح
if not SQUARE_ACCESS_TOKEN:
    logger.error("SQUARE_ACCESS_TOKEN not set!")
if not SQUARE_LOCATION_ID:
    logger.error("SQUARE_LOCATION_ID not set!")

# تهيئة Square
client = Client(
    access_token=SQUARE_ACCESS_TOKEN,
    environment='production' if SQUARE_ENVIRONMENT == 'production' else 'sandbox'
)
payments_api = client.payments

def generate_idempotency_key(identifier):
    return hashlib.md5(f"{identifier}_{time.time()}".encode()).hexdigest()

# ========== نقاط النهاية ==========

@app.route('/api/payment/process', methods=['POST'])
def process_payment():
    try:
        data = request.get_json()
        
        if not data or not data.get('nonce') or not data.get('amount'):
            return jsonify({'success': False, 'error': 'Missing nonce or amount'}), 400
        
        request_body = {
            "idempotency_key": generate_idempotency_key('payment'),
            "source_id": data.get('nonce'),
            "amount_money": {
                "amount": data.get('amount'),
                "currency": data.get('currency', 'USD')
            },
            "location_id": SQUARE_LOCATION_ID,
            "autocomplete": True
        }
        
        if data.get('order_id'):
            request_body["order_id"] = str(data.get('order_id'))
        
        result = payments_api.create_payment(request_body)
        
        if result.is_success():
            payment = result.body.get('payment', {})
            return jsonify({
                'success': True,
                'payment_id': payment.get('id'),
                'status': payment.get('status'),
                'amount': payment.get('amount_money', {}).get('amount'),
                'receipt_url': payment.get('receipt_url')
            }), 200
        else:
            error = result.errors[0] if result.errors else None
            return jsonify({
                'success': False,
                'error': error.get('detail') if error else 'Payment failed'
            }), 400
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/payment/status/<payment_id>', methods=['GET'])
def get_payment_status(payment_id):
    try:
        result = payments_api.get_payment(payment_id)
        if result.is_success():
            payment = result.body.get('payment', {})
            return jsonify({
                'success': True,
                'status': payment.get('status'),
                'payment': payment
            }), 200
        return jsonify({'success': False, 'error': 'Payment not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/payment/refund', methods=['POST'])
def refund_payment():
    try:
        data = request.get_json()
        payment_id = data.get('payment_id')
        amount = data.get('amount')
        
        if not payment_id:
            return jsonify({'success': False, 'error': 'Missing payment_id'}), 400
        
        if not amount:
            payment_info = payments_api.get_payment(payment_id)
            if payment_info.is_success():
                amount = payment_info.body.get('payment', {}).get('amount_money', {}).get('amount')
            else:
                return jsonify({'success': False, 'error': 'Could not get payment'}), 400
        
        request_body = {
            "idempotency_key": generate_idempotency_key(f"{payment_id}_refund"),
            "payment_id": payment_id,
            "amount_money": {
                "amount": amount,
                "currency": "USD"
            },
            "reason": data.get('reason', 'Refund')
        }
        
        result = payments_api.refund_payment(request_body)
        
        if result.is_success():
            return jsonify({
                'success': True,
                'refund': result.body.get('refund', {})
            }), 200
        return jsonify({'success': False, 'error': 'Refund failed'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
