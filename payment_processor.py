import logging
from square.client import Client
from config import Config
from decimal import Decimal

logger = logging.getLogger(__name__)

class SquarePaymentProcessor:
    def __init__(self):
        self.client = Client(
            access_token=Config.SQUARE_ACCESS_TOKEN,
            environment=Config.get_square_environment()
        )
        self.payments_api = self.client.payments
        self.locations_api = self.client.locations
        self.orders_api = self.client.orders
        
    def process_payment(self, nonce: str, amount: int, order_id: int = None, 
                       currency: str = 'USD'):
        """
        معالجة الدفع باستخدام Square
        
        Args:
            nonce (str): رمز الدفع المأخوذ من Square SDK
            amount (int): المبلغ بالسنتات (مثال: 1000 = 10.00$)
            order_id (int): معرف الطلب في نظامك
            currency (str): العملة (USD افتراضياً)
        
        Returns:
            dict: نتيجة الدفع
        """
        try:
            # تحويل المبلغ إلى دولار
            amount_dollars = Decimal(amount) / 100
            
            # إنشاء جسم الطلب
            request_body = {
                "idempotency_key": self._generate_idempotency_key(order_id),
                "source_id": nonce,
                "amount_money": {
                    "amount": amount,
                    "currency": currency
                },
                "order_id": order_id if order_id else None,
                "location_id": Config.SQUARE_LOCATION_ID,
                "autocomplete": True,
                "note": f"Order #{order_id} payment" if order_id else "Payment",
                "statement_description_identifier": f"Aynur Order {order_id}"
            }
            
            # إزالة المفاتيح التي تحتوي على None
            request_body = {k: v for k, v in request_body.items() if v is not None}
            
            # تنفيذ الدفع
            result = self.payments_api.create_payment(request_body)
            
            if result.is_success():
                payment = result.body.get('payment', {})
                logger.info(f"Payment successful: {payment.get('id')}")
                return {
                    'success': True,
                    'payment_id': payment.get('id'),
                    'status': payment.get('status'),
                    'amount': payment.get('amount_money', {}).get('amount'),
                    'currency': payment.get('amount_money', {}).get('currency'),
                    'receipt_url': payment.get('receipt_url'),
                    'order_id': order_id
                }
            else:
                error = result.errors[0] if result.errors else None
                logger.error(f"Payment failed: {error}")
                return {
                    'success': False,
                    'error': {
                        'code': error.get('code') if error else 'UNKNOWN',
                        'detail': error.get('detail') if error else 'Unknown error',
                        'field': error.get('field') if error else None
                    }
                }
                
        except Exception as e:
            logger.error(f"Payment processing exception: {str(e)}")
            return {
                'success': False,
                'error': {
                    'code': 'EXCEPTION',
                    'detail': str(e)
                }
            }
    
    def get_payment_status(self, payment_id: str):
        """الحصول على حالة الدفع"""
        try:
            result = self.payments_api.get_payment(payment_id)
            if result.is_success():
                payment = result.body.get('payment', {})
                return {
                    'success': True,
                    'payment': payment
                }
            else:
                return {
                    'success': False,
                    'error': result.errors
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def cancel_payment(self, payment_id: str):
        """إلغاء الدفع"""
        try:
            result = self.payments_api.cancel_payment(payment_id)
            if result.is_success():
                return {
                    'success': True,
                    'message': 'Payment cancelled successfully'
                }
            else:
                return {
                    'success': False,
                    'error': result.errors
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def complete_payment(self, payment_id: str):
        """إكمال الدفع (إذا كان في حالة مؤقتة)"""
        try:
            result = self.payments_api.complete_payment(payment_id)
            if result.is_success():
                return {
                    'success': True,
                    'payment': result.body.get('payment', {})
                }
            else:
                return {
                    'success': False,
                    'error': result.errors
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def refund_payment(self, payment_id: str, amount: int = None, 
                       reason: str = "Customer requested refund"):
        """استرداد المبلغ"""
        try:
            # إذا لم يتم تحديد المبلغ، يسترد كامل المبلغ
            if amount is None:
                # الحصول على معلومات الدفع أولاً
                payment_info = self.get_payment_status(payment_id)
                if not payment_info.get('success'):
                    return {
                        'success': False,
                        'error': 'Could not retrieve payment info'
                    }
                amount = payment_info['payment']['amount_money']['amount']
            
            request_body = {
                "idempotency_key": self._generate_idempotency_key(f"{payment_id}_refund"),
                "payment_id": payment_id,
                "amount_money": {
                    "amount": amount,
                    "currency": "USD"
                },
                "reason": reason
            }
            
            result = self.payments_api.refund_payment(request_body)
            
            if result.is_success():
                return {
                    'success': True,
                    'refund': result.body.get('refund', {})
                }
            else:
                return {
                    'success': False,
                    'error': result.errors
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_location(self):
        """الحصول على معلومات الموقع"""
        try:
            result = self.locations_api.retrieve_location(Config.SQUARE_LOCATION_ID)
            if result.is_success():
                return {
                    'success': True,
                    'location': result.body.get('location', {})
                }
            else:
                return {
                    'success': False,
                    'error': result.errors
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_idempotency_key(self, identifier):
        """توليد مفتاح Idempotency لتجنب الدفع المكرر"""
        import hashlib
        import time
        
        # استخدام معرف الطلب والوقت لضمان uniqueness
        key_string = f"{identifier}_{time.time()}"
        return hashlib.md5(key_string.encode()).hexdigest()