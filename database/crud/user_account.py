from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud.base import BaseService
from database.models.user_account import UserAccount
from database.schemas.user_account import UserAccountCreate, UserAccountUpdate


class UserAccountService(
    BaseService[UserAccount, UserAccountCreate, UserAccountUpdate]
):
    def __init__(self, db: AsyncSession):
        super().__init__(UserAccount, db)

    async def get_by_user_uuid(self, user_uuid: str) -> UserAccount:
        stmt = (
            select(UserAccount)
            .options(selectinload(UserAccount.plan))
            .where(UserAccount.user_uuid == user_uuid)
            .order_by(UserAccount.id.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        account = result.scalar_one_or_none()
        if account:
            return account

        try:
            new_account = await self.create(
                UserAccountCreate(user_uuid=user_uuid, plan_id=None)
            )
            return new_account
        except IntegrityError:
            await self.session.rollback()
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
