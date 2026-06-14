from fastapi import APIRouter, Depends
import json
import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from fastapi import Request, Header
from fastapi.responses import JSONResponse

from core.logger import logger
from database.crud import PaymentService, PlanService, TransactionService, UserAccountService
from database.db.session import get_db
from database.models.payment import Payment
from database.models.transaction import TransactionType
from database.schemas.payment import Purposes, PaymentUpdate, PaymentStatus
from database.schemas.transaction import TransactionCreate
from database.schemas.user_account import UserAccountUpdate
from services.rabbit_service import RabbitMQPublisher
from services.stripe_service.service import StripeService


stripe_public_router = APIRouter()

@stripe_public_router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db)
):
    payload = await request.body()
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        return JSONResponse({"success": False})

    if settings.STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=stripe_signature,
                secret=settings.STRIPE_WEBHOOK_SECRET,
            )
        except stripe.error.SignatureVerificationError:
            return JSONResponse({"success": False})

    event_type = event["type"]

    payment_service = PaymentService(db)

    data = StripeService.decode_webhook(event)
    session: Payment | None = await payment_service.get_by_provider_payment_id(data.checkout_id)
    if event_type == "checkout.session.completed":
        if not session:
            logger.warning(f"Payment not found for checkout_id: {data.checkout_id}")
            return JSONResponse({"success": False})

        logger.info(f"Checkout session completed event received")
        if session.status != PaymentStatus.COMPLETED:
            if session.purpose == Purposes.PLAN_PURCHASE:
                if not session.purpose_external_id:
                    logger.warning(
                        f"Missing purpose_external_id for PLAN_PURCHASE payment id={session.id}"
                    )
                    return JSONResponse({"success": False})

                plan_service = PlanService(db)
                plan = await plan_service.get(int(session.purpose_external_id))
                if not plan:
                    logger.warning(f"Plan not found for plan_id: {session.purpose_external_id}")
                    return JSONResponse({"success": False})

                account_service = UserAccountService(db)
                account = await account_service.get_by_user_uuid(session.user_external_id)
                if not account:
                    logger.warning(
                        f"User account not found for user: {session.user_external_id}"
                    )
                    return JSONResponse({"success": False})

                transaction_service = TransactionService(db)
                await transaction_service.create(
                    TransactionCreate(
                        user_account_id=account.id,
                        plan_id=plan.id,
                        transaction_type=TransactionType.PLAN_PURCHASE,
                        amount=plan.bid_power,
                    )
                )

                await account_service.update(
                    account.id,
                    UserAccountUpdate(
                        plan_id=plan.id,
                        balance=plan.bid_power,
                    ),
                )

            await payment_service.update(
                session.id, PaymentUpdate(status=PaymentStatus.COMPLETED)
            )

            if session.purpose in (Purposes.CARFAX, Purposes.PLAN_PURCHASE):
                rabbit_service = RabbitMQPublisher()
                routing_key = f'payment.success.{session.purpose}'.lower()
                logger.info(f"Routing key: {routing_key}")

                rabbit_payload = {
                    "session_id": session.id,
                    "user_uuid": session.user_external_id,
                    "amount": session.amount,
                    "purpose": session.purpose,
                    "purpose_external_id": session.purpose_external_id,
                }
                logger.info(f"Payload: {rabbit_payload}")
                await rabbit_service.publish(routing_key=routing_key, payload=rabbit_payload)


    elif event_type == "checkout.session.expired":
        if not session:
            logger.warning(f"Payment not found for checkout_id: {data.checkout_id}")
            return JSONResponse({"success": False})

        await payment_service.update(session.id, PaymentUpdate(status=PaymentStatus.FAILED))
    return JSONResponse({"success": True})
