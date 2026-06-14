from pydantic import BaseModel, HttpUrl


class StripeCheckOutIn(BaseModel):
    purpose: str
    purpose_external_id: str
    success_link: HttpUrl
    cancel_link: HttpUrl


class StripeCheckOutOut(BaseModel):
    link: HttpUrl
    checkout_id: str


