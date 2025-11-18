from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Purposes(str, Enum):
    PLAN_PURCHASE = "PLAN_PURCHASE"
    CARFAX = "CARFAX"

class PaymentBase(BaseModel):
    user_external_id: str
    source: str
    provider: str
    amount: float
    status: PaymentStatus = PaymentStatus.PENDING
    purpose: Purposes
    purpose_external_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    provider_payment_id: str | None = None

class PaymentCreate(PaymentBase):
    pass

class PaymentUpdate(BaseModel):
    user_external_id: str | None = None
    source: str | None = None
    provider: str | None = None
    purpose: Purposes | None = None
    purpose_external_id: str | None = None
    amount: float | None = None
    status: PaymentStatus | None = None
    provider_payment_id: str | None = None
    updated_at: datetime | None = None

class PaymentRead(PaymentBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
