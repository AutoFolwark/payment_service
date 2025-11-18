from typing import Any, TypeVar, Generic, Type, Sequence, Literal

from sqlalchemy import Select, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel

ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class BaseService(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType], db: AsyncSession) -> None:
        self.model = model
        self.session = db

    async def get(self, obj_id: int) -> ModelType | None:
        return await self.session.get(self.model, obj_id)

    async def get_all(
        self,
        get_stmt: bool = False,
        order_by: str | None = None,
        sort: Literal["desc", "asc"] | None = None,
    ) -> Sequence[ModelType] | Select[tuple[ModelType]]:
        stmt = select(self.model)

        if order_by:
            column = getattr(self.model, order_by, None)
            if column is None:
                raise ValueError(f"Invalid order_by field: {order_by}")
            if sort and sort.lower() == "desc":
                stmt = stmt.order_by(desc(column))
            else:
                stmt = stmt.order_by(asc(column))

        if get_stmt:
            return stmt
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, data: CreateSchemaType) -> ModelType:
        obj = self.model(**data.model_dump())
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def update(self, obj_id: int, data: UpdateSchemaType) -> ModelType | None:
        obj = await self.get(obj_id)
        if not obj:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, key, value)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def delete(self, obj_id: int) -> bool:
        obj = await self.get(obj_id)
        if not obj:
            return False
        await self.session.delete(obj)
        await self.session.commit()
        return True
