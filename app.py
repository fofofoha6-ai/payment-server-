import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from config import Config
from square_payment.payment_processor import SquarePaymentProcessor
from square_payment.webhooks import SquareWebhookHandler

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# تهيئة التطبيق
app = Flask(__name__)
app.config.from_object(Config)
CORS(app)  # للسماح بالطلبات من تطبيق Flutter

# تهيئة معالج الدفع
payment_processor = SquarePaymentProcessor()
webhook_handler = SquareWebhookHandler()

# ==================== نقاط النهاية (Endpoints) ====================

@app.route('/api/payment/process', methods=['POST'])
def process_payment():
    """
    معالجة الدفع
    المتطلبات:
    {
        "nonce": "cnon:card-nonce-ok",
        "amount": 1000,  # بالسنتات
        "order_id": 12345
    }
    """
    try:
        data = request.get_json()
        
        # التحقق من البيانات
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        nonce = data.get('nonce')
        amount = data.get('amount')
        order_id = data.get('order_id')
        currency = data.get('currency', 'USD')
        
        if not nonce:
            return jsonify({
                'success': False,
                'error': 'Missing card nonce'
            }), 400
        
        if not amount:
            return jsonify({
                'success': False,
                'error': 'Missing amount'
            }), 400
        
        # معالجة الدفع
        result = payment_processor.process_payment(
            nonce=nonce,
            amount=amount,
            order_id=order_id,
            currency=currency
        )
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error in process_payment: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/payment/status/<payment_id>', methods=['GET'])
def get_payment_status(payment_id):
    """الحصول على حالة الدفع"""
    try:
        result = payment_processor.get_payment_status(payment_id)
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 404
    except Exception as e:
        logger.error(f"Error in get_payment_status: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/payment/cancel/<payment_id>', methods=['POST'])
def cancel_payment(payment_id):
    """إلغاء الدفع"""
    try:
        result = payment_processor.cancel_payment(payment_id)
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error in cancel_payment: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/payment/complete/<payment_id>', methods=['POST'])
def complete_payment(payment_id):
    """إكمال الدفع المؤقت"""
    try:
        result = payment_processor.complete_payment(payment_id)
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error in complete_payment: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/payment/refund', methods=['POST'])
def refund_payment():
    """استرداد المبلغ"""
    try:
        data = request.get_json()
        payment_id = data.get('payment_id')
        amount = data.get('amount')  # اختياري
        reason = data.get('reason', 'Customer requested refund')
        
        if not payment_id:
            return jsonify({
                'success': False,
                'error': 'Missing payment_id'
            }), 400
        
        result = payment_processor.refund_payment(
            payment_id=payment_id,
            amount=amount,
            reason=reason
        )
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    except Exception as e:
        logger.error(f"Error in refund_payment: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/payment/location', methods=['GET'])
def get_location():
    """الحصول على معلومات الموقع"""
    try:
        result = payment_processor.get_location()
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 404
    except Exception as e:
        logger.error(f"Error in get_location: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ==================== Webhook Endpoint ====================

@app.route('/api/webhook/square', methods=['POST'])
def square_webhook():
    """
    استقبال Webhook من Square
    """
    try:
        # الحصول على التوقيع للتحقق
        signature = request.headers.get('x-square-hmacsha256-signature')
        payload = request.get_data(as_text=True)
        
        # التحقق من التوقيع
        if signature and Config.SQUARE_WEBHOOK_SIGNATURE_KEY:
            if not webhook_handler.verify_signature(payload, signature):
                logger.warning("Invalid webhook signature")
                return jsonify({'error': 'Invalid signature'}), 401
        
        # معالجة البيانات
        data = request.get_json()
        result = webhook_handler.handle_webhook(data)
        
        # إرجاع استجابة 200 لمنع إعادة المحاولة
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ==================== الصحة (Health Check) ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """التحقق من صحة الخادم"""
    return jsonify({
        'status': 'healthy',
        'version': '1.0.0',
        'environment': Config.SQUARE_ENVIRONMENT
    }), 200

# ==================== تشغيل الخادم ====================

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=Config.DEBUG
    )