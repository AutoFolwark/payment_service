from AuthTools import HeaderUser
from AuthTools.Permissions.dependencies import require_permissions
from fastapi import APIRouter, Depends
from rfc9457 import NotFoundProblem, ServerProblem

from config import Permissions
from database.crud import PaymentService, PlanService
from database.db.session import get_db
from database.schemas.payment import PaymentCreate, PaymentStatus, Purposes
from schemas.plan import BuyPlanPayload, BuyPlanStripePayload
from schemas.stripe import StripeCheckOutOut
from sqlalchemy.ext.asyncio import AsyncSession

from services.stripe_service.service import StripeService
from services.stripe_service.types import ProductData, Product, Price

stripe_private_router = APIRouter()


@stripe_private_router.post("/buy-plan", response_model=StripeCheckOutOut, description="Buy a plan with Stripe")
async def buy_plan(
    payload: BuyPlanStripePayload, 
    db: AsyncSession = Depends(get_db),
    user: HeaderUser = Depends(require_permissions(Permissions.ACCOUNT_ALL_WRITE))
):
    plan_service = PlanService(db)
    plan = await plan_service.get(payload.plan_id)
    if not plan:
        raise NotFoundProblem(title="Plan not found", detail="Plan not found")

    
    stripe_service = StripeService(success_url=payload.success_link, cancel_url=payload.cancel_link)
    product = Product(
        price_data=Price(
            unit_amount=plan.price, 
            product_data=ProductData(
                name=plan.name, 
                description=plan.description
            )
        ),
        quantity=1
    )
    try:
        stripe_session = await stripe_service.create_checkout_session(product)
    except Exception:
        raise ServerProblem(title='Failed to connect to Stripe', detail="Unable to create Stripe checkout session")

    try:
        payment_service = PaymentService(db)

        await payment_service.create(
            PaymentCreate(
                user_external_id=user.uuid,
                source="web",
                provider="STRIPE",
                amount=plan.price,
                purpose=Purposes.PLAN_PURCHASE,
                provider_payment_id=stripe_session.id,
                purpose_external_id=str(plan.id),
                status=PaymentStatus.PENDING,
            )
        )
    except Exception:
        raise ServerProblem(title='Failed to create payment', detail="Unable to create payment")
    
    return StripeCheckOutOut(link=stripe_session.url, checkout_id=stripe_session.id)






