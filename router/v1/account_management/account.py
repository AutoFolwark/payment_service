from AuthTools import HeaderUser
from AuthTools.Permissions.dependencies import require_permissions
from fastapi import APIRouter, Depends
from fastapi_problem import error as problem
from sqlalchemy.ext.asyncio import AsyncSession

from config import Permissions
from core.logger import logger
from database.crud import TransactionService, UserAccountService
from database.db.session import get_db
from database.models.transaction import TransactionType
from database.schemas.transaction import TransactionCreate
from database.schemas.user_account import UserAccountUpdate
from schemas.account import AccountResetPayload, UserAccountDetailed

account_management_router = APIRouter(prefix="/account", tags=["Account Management"])


@account_management_router.get(
    "/me",
    response_model=UserAccountDetailed,
    description=f"Get current user account with plan details, required permissions:{Permissions.ACCOUNT_OWN_READ.value}",
)
async def get_my_account(
    current_user: HeaderUser = Depends(
        require_permissions(Permissions.ACCOUNT_OWN_READ)
    ),
    db: AsyncSession = Depends(get_db),
):
    account_service = UserAccountService(db)
    logger.info(f'Searching for account for user: {current_user.uuid}')
    return await account_service.get_by_user_uuid(current_user.uuid)


@account_management_router.post(
    "/reset",
    response_model=UserAccountDetailed,
    description=(
        f"Reset user account balance and plan, required permissions: "
        f"{Permissions.ACCOUNT_ALL_WRITE.value}"
    ),
    dependencies=[Depends(require_permissions(Permissions.ACCOUNT_ALL_WRITE))],
)
async def reset_user_account(
    payload: AccountResetPayload,
    db: AsyncSession = Depends(get_db),
):
    account_service = UserAccountService(db)
    account = await account_service.get_by_user_uuid(payload.user_uuid)

    transaction_service = TransactionService(db)
    adjustment_amount = -account.balance if account.balance else 0

    if adjustment_amount != 0:
        await transaction_service.create(
            TransactionCreate(
                user_account_id=account.id,
                plan_id=None,
                transaction_type=TransactionType.ADJUSTMENT,
                amount=adjustment_amount,
            )
        )

    updated_account = await account_service.update(
        account.id,
        UserAccountUpdate(plan_id=None, balance=0),
    )
    if not updated_account:
        raise problem.ServerProblem(detail="Unable to reset account")

    return await account_service.get_by_user_uuid(payload.user_uuid)
