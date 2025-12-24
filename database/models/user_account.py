from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.models import Base

if TYPE_CHECKING:
    from database.models.plan import Plan
    from database.models.transaction import Transaction


class UserAccount(Base):
    __tablename__ = "user_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_uuid: Mapped[str] = mapped_column(nullable=False, index=True)

    balance: Mapped[int] = mapped_column(default=0)

    plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("plan.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    plan: Mapped["Plan | None"] = relationship(back_populates="accounts", lazy="selectin")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="user_account",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_user_account_user_plan", "user_uuid", "plan_id"),
        UniqueConstraint("user_uuid", name="uq_user_account_user_uuid"),
    )
