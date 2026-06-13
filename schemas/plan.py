from pydantic import BaseModel, HttpUrl

from core.utils import create_pagination_page
from database.schemas.plan import PlanRead


class PlanAssignPayload(BaseModel):
    user_uuid: str
    plan_id: int

class BuyPlanPayload(BaseModel):
    plan_id: int

class BuyPlanStripePayload(BaseModel):
    plan_id: int
    success_link: HttpUrl 
    cancel_link: HttpUrl

PlansPage = create_pagination_page(PlanRead)
