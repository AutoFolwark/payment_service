import asyncio
import json
import logging

from apimatic_core.utilities.api_helper import ApiHelper
from paypalserversdk.controllers.orders_controller import OrdersController
from paypalserversdk.controllers.payments_controller import PaymentsController
from paypalserversdk.configuration import Environment as PaypalEnvironment
from paypalserversdk.http.auth.o_auth_2 import ClientCredentialsAuthCredentials
from paypalserversdk.logging.configuration.api_logging_configuration import LoggingConfiguration, \
    RequestLoggingConfiguration, ResponseLoggingConfiguration
from paypalserversdk.models.amount_breakdown import AmountBreakdown
from paypalserversdk.models.amount_with_breakdown import AmountWithBreakdown
from paypalserversdk.models.checkout_payment_intent import CheckoutPaymentIntent
from paypalserversdk.models.item import Item
from paypalserversdk.models.item_category import ItemCategory
from paypalserversdk.models.money import Money
from paypalserversdk.models.order_request import OrderRequest
from paypalserversdk.models.purchase_unit_request import PurchaseUnitRequest
from paypalserversdk.paypal_serversdk_client import PaypalServersdkClient

from config import settings, Environment
from database.crud import PlanService
from database.db.session import get_db_context
from database.models.plan import Plan


class PaypalService:
    def __init__(self):
        if settings.ENVIRONMENT == Environment.PRODUCTION.value:
            environment = PaypalEnvironment.PRODUCTION
        else:
            environment = PaypalEnvironment.SANDBOX

        self.paypal_client: PaypalServersdkClient = PaypalServersdkClient(
            environment=environment,
            client_credentials_auth_credentials=ClientCredentialsAuthCredentials(
                o_auth_client_id=settings.PAYPAL_CLIENT_ID,
                o_auth_client_secret=settings.PAYPAL_CLIENT_SECRET,
            ),
            logging_configuration=LoggingConfiguration(
                log_level=logging.INFO,
                mask_sensitive_headers=False,
                request_logging_config=RequestLoggingConfiguration(
                    log_headers=True,
                    log_body=True,
                ),
                response_logging_config=ResponseLoggingConfiguration(
                    log_headers=True,
                    log_body=True,
                ),
            ),
        )

        self.orders_controller: OrdersController = self.paypal_client.orders
        self.payments_controller: PaymentsController = self.paypal_client.payments

    def create_order_for_plan(self, plan: Plan) -> str:
        item: Item = Item(
            name=plan.name,
            unit_amount=Money(currency_code="USD", value=plan.price),
            quantity="1",
            category=ItemCategory.DIGITAL_GOODS,
        )

        order = self.orders_controller.create_order(
            {
                "body": OrderRequest(
                    intent=CheckoutPaymentIntent.CAPTURE,
                    purchase_units=[
                        PurchaseUnitRequest(
                            amount=AmountWithBreakdown(
                                currency_code="USD",
                                value=plan.price,
                                breakdown=AmountBreakdown(
                                    item_total=Money(
                                        currency_code="USD",
                                        value=plan.price,
                                    )
                                ),
                            ),
                            items=[item],
                        )
                    ],
                )
            }
        )
        serialized = json.loads(ApiHelper.json_serialize(order.body))
        print(serialized)
        return serialized['id']

    def capture_order(self, order_id: str):
        order = self.orders_controller.capture_order(
            {
                "id": order_id,
                "prefer": "return=representation",
            }
        )

        order_body = json.loads(ApiHelper.json_serialize(order.body))
        return order_body





if __name__ == "__main__":
    paypal_service = PaypalService()

    async def main():
        async with get_db_context() as db:
            plan_service = PlanService(db)
            plan = await plan_service.get_by_name("Basic Plan")

        order_id = paypal_service.create_order_for_plan(plan)
        timeout = input('wait')
        print(paypal_service.capture_order(order_id))

    asyncio.run(main())
