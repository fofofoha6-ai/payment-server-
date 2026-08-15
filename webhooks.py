import hashlib
import hmac
import json
from flask import request, jsonify
from config import Config
import logging

logger = logging.getLogger(__name__)

class SquareWebhookHandler:
    @staticmethod
    def verify_signature(payload: str, signature: str) -> bool:
        """التحقق من توقيع Webhook للتأكد من أنه من Square"""
        if not Config.SQUARE_WEBHOOK_SIGNATURE_KEY:
            return True  # إذا لم يتم تعيين المفتاح، تخطي التحقق
        
        expected_signature = hmac.new(
            Config.SQUARE_WEBHOOK_SIGNATURE_KEY.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    @staticmethod
    def handle_webhook(data):
        """معالجة أحداث Webhook من Square"""
        try:
            event_type = data.get('type')
            event_data = data.get('data', {})
            object_type = event_data.get('type')
            object_id = event_data.get('id')
            merchant_id = data.get('merchant_id')
            
            logger.info(f"Webhook received: {event_type} for {object_type} {object_id}")
            
            # معالجة أنواع الأحداث المختلفة
            if event_type == 'payment.created':
                return SquareWebhookHandler._handle_payment_created(event_data)
            elif event_type == 'payment.updated':
                return SquareWebhookHandler._handle_payment_updated(event_data)
            elif event_type == 'payment.cancelled':
                return SquareWebhookHandler._handle_payment_cancelled(event_data)
            elif event_type == 'payment.failed':
                return SquareWebhookHandler._handle_payment_failed(event_data)
            elif event_type == 'payment.refund.created':
                return SquareWebhookHandler._handle_refund_created(event_data)
            elif event_type == 'payment.refund.updated':
                return SquareWebhookHandler._handle_refund_updated(event_data)
            elif event_type == 'order.created':
                return SquareWebhookHandler._handle_order_created(event_data)
            elif event_type == 'order.updated':
                return SquareWebhookHandler._handle_order_updated(event_data)
            else:
                logger.warning(f"Unhandled webhook event type: {event_type}")
                return {'handled': False, 'message': f'Unhandled event type: {event_type}'}
                
        except Exception as e:
            logger.error(f"Error handling webhook: {str(e)}")
            return {'handled': False, 'error': str(e)}
    
    @staticmethod
    def _handle_payment_created(event_data):
        """معالجة حدث إنشاء الدفع"""
        payment = event_data.get('object', {}).get('payment', {})
        payment_id = payment.get('id')
        amount = payment.get('amount_money', {}).get('amount')
        status = payment.get('status')
        
        logger.info(f"Payment created: {payment_id}, Amount: {amount}, Status: {status}")
        
        # هنا يمكنك تحديث قاعدة البيانات وتغيير حالة الطلب
        # update_order_status(payment_id, status)
        
        return {
            'handled': True,
            'payment_id': payment_id,
            'status': status,
            'action': 'update_order_status'
        }
    
    @staticmethod
    def _handle_payment_updated(event_data):
        """معالجة حدث تحديث الدفع"""
        payment = event_data.get('object', {}).get('payment', {})
        payment_id = payment.get('id')
        status = payment.get('status')
        
        logger.info(f"Payment updated: {payment_id}, Status: {status}")
        
        # تحديث حالة الدفع في قاعدة البيانات
        # update_payment_status(payment_id, status)
        
        return {
            'handled': True,
            'payment_id': payment_id,
            'status': status,
            'action': 'update_payment_status'
        }
    
    @staticmethod
    def _handle_payment_cancelled(event_data):
        """معالجة حدث إلغاء الدفع"""
        payment = event_data.get('object', {}).get('payment', {})
        payment_id = payment.get('id')
        
        logger.info(f"Payment cancelled: {payment_id}")
        
        # تحديث حالة الطلب إلى ملغي
        # cancel_order_by_payment(payment_id)
        
        return {
            'handled': True,
            'payment_id': payment_id,
            'action': 'cancel_order'
        }
    
    @staticmethod
    def _handle_payment_failed(event_data):
        """معالجة حدث فشل الدفع"""
        payment = event_data.get('object', {}).get('payment', {})
        payment_id = payment.get('id')
        error = payment.get('error', {})
        
        logger.error(f"Payment failed: {payment_id}, Error: {error}")
        
        # تحديث حالة الطلب إلى فشل
        # update_order_status_by_payment(payment_id, 'failed')
        
        return {
            'handled': True,
            'payment_id': payment_id,
            'error': error,
            'action': 'handle_failed_payment'
        }
    
    @staticmethod
    def _handle_refund_created(event_data):
        """معالجة حدث إنشاء استرداد"""
        refund = event_data.get('object', {}).get('refund', {})
        refund_id = refund.get('id')
        payment_id = refund.get('payment_id')
        amount = refund.get('amount_money', {}).get('amount')
        
        logger.info(f"Refund created: {refund_id} for payment {payment_id}, Amount: {amount}")
        
        return {
            'handled': True,
            'refund_id': refund_id,
            'payment_id': payment_id,
            'amount': amount,
            'action': 'process_refund'
        }
    
    @staticmethod
    def _handle_refund_updated(event_data):
        """معالجة حدث تحديث الاسترداد"""
        refund = event_data.get('object', {}).get('refund', {})
        refund_id = refund.get('id')
        status = refund.get('status')
        
        logger.info(f"Refund updated: {refund_id}, Status: {status}")
        
        return {
            'handled': True,
            'refund_id': refund_id,
            'status': status,
            'action': 'update_refund_status'
        }
    
    @staticmethod
    def _handle_order_created(event_data):
        """معالجة حدث إنشاء طلب"""
        order = event_data.get('object', {}).get('order', {})
        order_id = order.get('id')
        
        logger.info(f"Order created in Square: {order_id}")
        
        return {
            'handled': True,
            'order_id': order_id,
            'action': 'sync_order'
        }
    
    @staticmethod
    def _handle_order_updated(event_data):
        """معالجة حدث تحديث الطلب"""
        order = event_data.get('object', {}).get('order', {})
        order_id = order.get('id')
        state = order.get('state')
        
        logger.info(f"Order updated: {order_id}, State: {state}")
        
        return {
            'handled': True,
            'order_id': order_id,
            'state': state,
            'action': 'update_order_state'
        }