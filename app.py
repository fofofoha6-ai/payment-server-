from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import square
from square.client import Client
from square.http.auth.o_auth_2 import BearerAuth
import os
import uuid
import logging
from typing import Optional, Dict, Any

# ============================================
# إعدادات التسجيل (Logging)
# ============================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================
# قراءة المتغيرات البيئية
# ============================================
SQUARE_APPLICATION_ID = os.getenv("SQUARE_APPLICATION_ID", "")
SQUARE_ACCESS_TOKEN = os.getenv("SQUARE_ACCESS_TOKEN", "")
SQUARE_LOCATION_ID = os.getenv("SQUARE_LOCATION_ID", "")
SQUARE_ENVIRONMENT = os.getenv("SQUARE_ENVIRONMENT", "SANDBOX")  # SANDBOX أو PRODUCTION

# التحقق من وجود المفاتيح
if not all([SQUARE_APPLICATION_ID, SQUARE_ACCESS_TOKEN, SQUARE_LOCATION_ID]):
    logger.warning("⚠️ بعض المفاتيح البيئية غير موجودة! تأكد من تعيينها في Render")

# تحديد البيئة (Sandbox أو Production)
environment = square.Environment.SANDBOX if SQUARE_ENVIRONMENT == "SANDBOX" else square.Environment.PRODUCTION

# ============================================
# تهيئة تطبيق FastAPI
# ============================================
app = FastAPI(
    title="Square Payment API",
    description="API لمعالجة المدفوعات عبر Square من تطبيق Flutter",
    version="1.0.0"
)

# ============================================
# إعدادات CORS (السماح لـ Flutter بالاتصال)
# ============================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",  # في الإنتاج، استبدل بعنوان تطبيقك الفعلي
        # "https://your-flutter-app.com",
        # "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# تهيئة عميل Square
# ============================================
try:
    client = Client(
        bearer_auth_settings=BearerAuth(SQUARE_ACCESS_TOKEN),
        environment=environment,
    )
    logger.info(f"✅ تم تهيئة Square Client بنجاح في بيئة: {SQUARE_ENVIRONMENT}")
except Exception as e:
    logger.error(f"❌ فشل تهيئة Square Client: {e}")
    client = None

# ============================================
# نماذج البيانات (Pydantic Models)
# ============================================
class PaymentRequest(BaseModel):
    nonce: str
    amount: str
    currency: str = "USD"
    reference_id: Optional[str] = None
    note: Optional[str] = None

class PaymentResponse(BaseModel):
    status: str
    payment_id: Optional[str] = None
    order_id: Optional[str] = None
    amount: Optional[int] = None
    currency: Optional[str] = None
    payment_status: Optional[str] = None
    created_at: Optional[str] = None
    message: Optional[str] = None
    code: Optional[str] = None

# ============================================
# نقاط النهاية (Endpoints)
# ============================================

@app.get("/")
async def root():
    """نقطة البداية للتحقق من عمل الخادم"""
    return {
        "status": "online",
        "service": "Square Payment API",
        "environment": SQUARE_ENVIRONMENT,
        "location_id": SQUARE_LOCATION_ID[:10] + "..." if SQUARE_LOCATION_ID else "Not set"
    }

@app.get("/health")
async def health_check():
    """نقطة للتحقق من صحة الخادم (يستخدمها Render)"""
    return {
        "status": "healthy",
        "square_configured": client is not None,
        "environment": SQUARE_ENVIRONMENT
    }

@app.post("/api/create-payment", response_model=PaymentResponse)
async def create_payment(request: PaymentRequest):
    """
    معالجة طلب الدفع من Flutter
    """
    # التحقق من تهيئة العميل
    if client is None:
        raise HTTPException(
            status_code=500,
            detail="Square client not initialized. Check your API keys."
        )

    # التحقق من صحة المبلغ
    try:
        amount_cents = int(float(request.amount) * 100)
        if amount_cents <= 0:
            raise ValueError("المبلغ يجب أن يكون أكبر من 0")
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"status": "error", "message": f"مبلغ غير صالح: {str(e)}"}
        )

    # توليد معرف فريد لمنع تكرار الدفع
    idempotency_key = str(uuid.uuid4())
    
    # بناء بيانات الدفع
    payment_data = {
        "source_id": request.nonce,
        "idempotency_key": idempotency_key,
        "amount_money": {
            "amount": amount_cents,
            "currency": request.currency
        },
        "location_id": SQUARE_LOCATION_ID,
        "autocomplete": True,
    }
    
    # إضافة بيانات اختيارية
    if request.reference_id:
        payment_data["reference_id"] = request.reference_id
    if request.note:
        payment_data["note"] = request.note
    else:
        payment_data["note"] = f"دفع من تطبيق Flutter - {idempotency_key[:8]}"

    logger.info(f"🔑 بدء عملية دفع: {idempotency_key[:8]} - المبلغ: {request.amount} {request.currency}")

    try:
        # إرسال طلب الدفع إلى Square
        payments_api = client.payments
        result = payments_api.create_payment(payment_data)

        if result.is_success():
            payment = result.body["payment"]
            logger.info(f"✅ تم الدفع بنجاح: {payment['id']}")
            
            return PaymentResponse(
                status="success",
                payment_id=payment["id"],
                order_id=payment.get("order_id"),
                amount=payment["amount_money"]["amount"],
                currency=payment["amount_money"]["currency"],
                payment_status=payment["status"],
                created_at=payment.get("created_at"),
                message="تمت عملية الدفع بنجاح"
            )
        else:
            # فشل الدفع - معالجة الأخطاء
            error = result.errors[0] if result.errors else None
            error_detail = error.detail if error else "Unknown error"
            error_code = error.code if error else "UNKNOWN"
            
            logger.error(f"❌ فشل الدفع: {error_detail} (الكود: {error_code})")
            
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": f"فشل الدفع: {error_detail}",
                    "code": error_code
                }
            )
            
    except HTTPException:
        # إعادة رفع استثناءات HTTPException كما هي
        raise
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": f"حدث خطأ داخلي في الخادم: {str(e)}"
            }
        )

# ============================================
# تشغيل السيرفر (للتطوير المحلي)
# ============================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,  # إيقاف التشغيل التلقائي في الإنتاج
        log_level="info"
    )
