import asyncio

from AuthTools import HeaderUser
from AuthTools.Permissions.dependencies import require_permissions
from fastapi import APIRouter, Depends, status
from fastapi_problem import error as problem
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config import Permissions
from database.crud import PaymentService, PlanService, TransactionService, UserAccountService
from database.db.session import get_db
from database.models.transaction import TransactionType
from database.schemas.payment import PaymentCreate, PaymentUpdate, PaymentStatus, Purposes
from database.schemas.plan import PlanRead
from database.schemas.transaction import TransactionCreate
from database.schemas.user_account import UserAccountUpdate
from services.paypal_service.service import PaypalService
from schemas.plan import BuyPlanPayload

paypal_private_router = APIRouter()


class PaypalCapturePayload(BaseModel):
    order_id: str


@paypal_private_router.post(
    "/create-order",
    status_code=status.HTTP_201_CREATED,
    response_model=PaypalCapturePayload,
    description=f"Create PayPal order for plan, required permissions: {Permissions.ACCOUNT_ALL_WRITE.value}",
)
async def paypal_create_order(
    payload: BuyPlanPayload,
    db: AsyncSession = Depends(get_db),
    user: HeaderUser = Depends(require_permissions(Permissions.ACCOUNT_ALL_WRITE))
):
    plan_service = PlanService(db)
    plan = await plan_service.get(payload.plan_id)
    if not plan:
        raise problem.NotFoundProblem(detail="Plan not found")

    paypal_service = PaypalService()
    try:
        order_id = await asyncio.to_thread(
            paypal_service.create_order_for_plan,
            plan,
        )
    except Exception:
        raise problem.ServerProblem(detail="Unable to create PayPal order")

    payment_service = PaymentService(db)
    await payment_service.create(
        PaymentCreate(
            user_external_id=user.uuid,
            source="web",
            provider="PAYPAL",
            amount=plan.price,
            purpose=Purposes.PLAN_PURCHASE,
            purpose_external_id=str(plan.id),
            provider_payment_id=order_id,
            status=PaymentStatus.PENDING,
        )
    )

    return PaypalCapturePayload(order_id=order_id)


@paypal_private_router.post(
    "/capture-order",
    response_model=PlanRead,
    description=f"Capture PayPal order and apply plan, required permissions: {Permissions.ACCOUNT_ALL_WRITE.value}",
)
async def paypal_capture_order(
    payload: PaypalCapturePayload,
    db: AsyncSession = Depends(get_db),
    user: HeaderUser = Depends(require_permissions(Permissions.ACCOUNT_ALL_WRITE))
):
    payment_service = PaymentService(db)
    payment = await payment_service.get_by_provider_payment_id(payload.order_id)
    if not payment or payment.user_external_id != user.uuid:
        raise problem.NotFoundProblem(detail="Payment not found for this order or user mismatch")

    paypal_service = PaypalService()
    try:
        order_body = await asyncio.to_thread(
            paypal_service.capture_order,
            payload.order_id,
        )
    except Exception:
        raise problem.ServerProblem(detail="Failed to capture PayPal order")

    order_status = order_body.get("status")

    if order_status != "COMPLETED":
        await payment_service.update(
            payment.id, PaymentUpdate(status=PaymentStatus.FAILED)
        )
        raise problem.BadRequestProblem(detail="PayPal order not completed")
    plan_service = PlanService(db)
    plan_id = payment.purpose_external_id
    plan = await plan_service.get(int(plan_id))
    if not plan:
        raise problem.NotFoundProblem(detail="Plan not found")

    account_service = UserAccountService(db)
    account = await account_service.get_by_user_uuid(payment.user_external_id)
    if not account:
        raise problem.NotFoundProblem(detail="User account not found")

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
        payment.id,
        PaymentUpdate(status=PaymentStatus.COMPLETED),
    )

    return plan
