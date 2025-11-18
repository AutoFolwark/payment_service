from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_pagination import Params
from fastapi_pagination.ext.sqlalchemy import apaginate
from database.crud import PlanService
from database.db.session import get_db
from schemas.plan import PlansPage

plan_public_router = APIRouter(prefix='/plan')


class PlanParams(Params):
    size: int = 10

@plan_public_router.get(
    "",
    response_model=PlansPage,
    description=f"List plans available for users",
)
async def list_plans(
    params: PlanParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    service = PlanService(db)
    plans_query = await service.get_all(get_stmt=True, order_by='price', sort='asc')
    return await apaginate(db, plans_query, params)