from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from square_legacy.client import Client
from square_legacy.http.auth.o_auth_2 import BearerAuth
import square_legacy

import os
import uuid
import logging
from typing import Optional


# ============================================================
# Logging
# ============================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# Environment Variables
# ============================================================

SQUARE_APPLICATION_ID = os.getenv(
    "SQUARE_APPLICATION_ID",
    ""
)

SQUARE_ACCESS_TOKEN = os.getenv(
    "SQUARE_ACCESS_TOKEN",
    ""
)

SQUARE_LOCATION_ID = os.getenv(
    "SQUARE_LOCATION_ID",
    ""
)

SQUARE_ENVIRONMENT = os.getenv(
    "SQUARE_ENVIRONMENT",
    "SANDBOX"
).upper()


# ============================================================
# Check configuration
# ============================================================

if not SQUARE_ACCESS_TOKEN:
    logger.warning(
        "⚠️ SQUARE_ACCESS_TOKEN is not configured"
    )

if not SQUARE_LOCATION_ID:
    logger.warning(
        "⚠️ SQUARE_LOCATION_ID is not configured"
    )

if not SQUARE_APPLICATION_ID:
    logger.warning(
        "⚠️ SQUARE_APPLICATION_ID is not configured"
    )


# ============================================================
# Square Environment
# ============================================================

if SQUARE_ENVIRONMENT == "PRODUCTION":

    environment = square_legacy.Environment.PRODUCTION

else:

    environment = square_legacy.Environment.SANDBOX


# ============================================================
# FastAPI Application
# ============================================================

app = FastAPI(
    title="Square Payment API",
    description="FastAPI backend for Flutter + Square payments",
    version="1.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


# ============================================================
# Square Client
# ============================================================

client = None

try:

    if SQUARE_ACCESS_TOKEN:

        client = Client(
            bearer_auth_settings=BearerAuth(
                SQUARE_ACCESS_TOKEN
            ),
            environment=environment,
        )

        logger.info(
            "✅ Square Client initialized successfully"
        )

        logger.info(
            f"Environment: {SQUARE_ENVIRONMENT}"
        )

    else:

        logger.warning(
            "⚠️ Square Client was not initialized because "
            "SQUARE_ACCESS_TOKEN is missing"
        )

except Exception as e:

    logger.exception(
        f"❌ Failed to initialize Square Client: {e}"
    )

    client = None


# ============================================================
# Pydantic Models
# ============================================================

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


# ============================================================
# Root
# ============================================================

@app.get("/")
async def root():

    return {
        "status": "online",
        "service": "Square Payment API",
        "environment": SQUARE_ENVIRONMENT,
        "square_configured": client is not None,
        "location_configured": bool(SQUARE_LOCATION_ID),
    }


# ============================================================
# Health Check
# ============================================================

@app.get("/health")
async def health_check():

    return {
        "status": "healthy",
        "square_configured": client is not None,
        "environment": SQUARE_ENVIRONMENT,
        "location_configured": bool(SQUARE_LOCATION_ID),
    }


# ============================================================
# Create Payment
# ============================================================

@app.post(
    "/api/create-payment",
    response_model=PaymentResponse
)
async def create_payment(
    request: PaymentRequest
):

    # --------------------------------------------------------
    # Check Square client
    # --------------------------------------------------------

    if client is None:

        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": (
                    "Square client is not initialized. "
                    "Check SQUARE_ACCESS_TOKEN."
                )
            }
        )


    # --------------------------------------------------------
    # Check Location ID
    # --------------------------------------------------------

    if not SQUARE_LOCATION_ID:

        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": (
                    "SQUARE_LOCATION_ID is not configured."
                )
            }
        )


    # --------------------------------------------------------
    # Validate amount
    # --------------------------------------------------------

    try:

        amount_value = float(request.amount)

        amount_cents = int(
            round(amount_value * 100)
        )

        if amount_cents <= 0:

            raise ValueError(
                "Amount must be greater than zero."
            )

    except (ValueError, TypeError):

        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": (
                    "Invalid amount."
                )
            }
        )


    # --------------------------------------------------------
    # Validate currency
    # --------------------------------------------------------

    currency = request.currency.upper().strip()

    if len(currency) != 3:

        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": (
                    "Currency must be a valid 3-letter "
                    "ISO currency code."
                )
            }
        )


    # --------------------------------------------------------
    # Idempotency Key
    # --------------------------------------------------------

    idempotency_key = str(
        uuid.uuid4()
    )


    # --------------------------------------------------------
    # Payment Data
    # --------------------------------------------------------

    payment_data = {

        "source_id": request.nonce,

        "idempotency_key": idempotency_key,

        "amount_money": {

            "amount": amount_cents,

            "currency": currency,
        },

        "location_id": SQUARE_LOCATION_ID,

        "autocomplete": True,
    }


    # --------------------------------------------------------
    # Optional Reference ID
    # --------------------------------------------------------

    if request.reference_id:

        payment_data[
            "reference_id"
        ] = request.reference_id


    # --------------------------------------------------------
    # Optional Note
    # --------------------------------------------------------

    if request.note:

        payment_data[
            "note"
        ] = request.note

    else:

        payment_data[
            "note"
        ] = (
            "Flutter Payment - "
            f"{idempotency_key[:8]}"
        )


    # --------------------------------------------------------
    # Logging
    # --------------------------------------------------------

    logger.info(
        "💳 Starting payment: "
        f"{idempotency_key[:8]} | "
        f"{amount_value:.2f} {currency}"
    )


    # --------------------------------------------------------
    # Create Payment
    # --------------------------------------------------------

    try:

        payments_api = client.payments

        result = payments_api.create_payment(
            payment_data
        )


        # ----------------------------------------------------
        # Successful Payment
        # ----------------------------------------------------

        if result.is_success():

            body = result.body or {}

            payment = body.get(
                "payment",
                {}
            )

            payment_id = payment.get(
                "id"
            )

            amount_money = payment.get(
                "amount_money",
                {}
            )

            logger.info(
                f"✅ Payment successful: {payment_id}"
            )


            return PaymentResponse(

                status="success",

                payment_id=payment_id,

                order_id=payment.get(
                    "order_id"
                ),

                amount=amount_money.get(
                    "amount"
                ),

                currency=amount_money.get(
                    "currency"
                ),

                payment_status=payment.get(
                    "status"
                ),

                created_at=payment.get(
                    "created_at"
                ),

                message="Payment completed successfully",
            )


        # ----------------------------------------------------
        # Square Error
        # ----------------------------------------------------

        errors = result.errors or []

        if errors:

            error = errors[0]

            error_detail = getattr(
                error,
                "detail",
                "Unknown Square error"
            )

            error_code = getattr(
                error,
                "code",
                "UNKNOWN"
            )

        else:

            error_detail = (
                "Unknown Square error"
            )

            error_code = "UNKNOWN"


        logger.error(
            f"❌ Square payment failed: "
            f"{error_detail} "
            f"({error_code})"
        )


        raise HTTPException(

            status_code=400,

            detail={

                "status": "error",

                "message": (
                    f"Payment failed: "
                    f"{error_detail}"
                ),

                "code": error_code,
            }
        )


    # --------------------------------------------------------
    # HTTPException
    # --------------------------------------------------------

    except HTTPException:

        raise


    # --------------------------------------------------------
    # Unexpected Error
    # --------------------------------------------------------

    except Exception as e:

        logger.exception(
            f"❌ Unexpected payment error: {e}"
        )

        raise HTTPException(

            status_code=500,

            detail={

                "status": "error",

                "message": (
                    "Internal server error."
                ),
            }
        )


# ============================================================
# Run Server
# ============================================================

if __name__ == "__main__":

    import uvicorn

    port = int(
        os.getenv(
            "PORT",
            "8000"
        )
    )

    uvicorn.run(

        "main:app",

        host="0.0.0.0",

        port=port,

        reload=False,

        log_level="info"
    )
