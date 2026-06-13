import stripe
from stripe.checkout import Session

from config import settings
from services.stripe_service.types import Product, Price, ProductData, WebhookData


class StripeService:
    CARFAX = Product(
        price_data=Price(
            product_data=ProductData(name="CARFAX", description="Išsamus „Carfax“ ataskaitos pirkimas — sužinokite visą transporto priemonės istoriją: avarijos, rida, techninė priežiūra, savininkų skaičius ir kita svarbi informacija."),
            unit_amount=100*2
            ),
        quantity=1,
    )

    def __init__(self, success_url: str = 'https://google.com',
                 cancel_url: str = 'https://google.com'):
        self.success_url = success_url

        self.cancel_url = cancel_url
        stripe.api_key = settings.STRIPE_SECRET_KEY

    async def create_checkout_session(self, product: Product) -> Session:
        try:
            session = await stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="payment",
                line_items=[product.model_dump()],
                success_url=self.success_url,
                cancel_url=self.cancel_url,
            )
            return session
        except stripe.error.StripeError as e:
            raise RuntimeError(f"Stripe error: {str(e)}")

    @classmethod
    def decode_webhook(cls, event: dict) -> WebhookData:
        webhook_object = event["data"]["object"]
        payment_intent = webhook_object.get("payment_intent", "")
        amount_total = webhook_object.get("amount_total", 0)
        currency = webhook_object.get("currency", "")
        checkout_id = webhook_object.get("id", "")
        status = webhook_object.get("status", "")
        payment_status = webhook_object.get("payment_status", "")

        return WebhookData(payment_intent=payment_intent, amount_total=amount_total,
                           currency=currency, checkout_id=checkout_id, status=status, payment_status=payment_status)




if __name__ == "__main__":
    stripe_service = StripeService()
    print(stripe_service.create_checkout_session(StripeService.CARFAX))