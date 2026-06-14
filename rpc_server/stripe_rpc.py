import asyncio

import grpc

from core.logger import logger
from database.crud.payment import PaymentService
from database.db.session import get_db_context
from database.schemas.payment import Purposes, PaymentCreate
from rpc_server.gen.python.payment.v1 import stripe_pb2_grpc, stripe_pb2
from services.stripe_service.service import StripeService


class StripeRpc(stripe_pb2_grpc.StripeServiceServicer):


    async def GetCheckoutLink(self, request: stripe_pb2.GetCheckoutLinkRequest, context):
        logger.debug(f"Received get_checkout_link rpc request")
        try:
            purpose = request.purpose

            if purpose == Purposes.CARFAX:
                product = StripeService.CARFAX
            else:
                logger.warning(f"Wrong Purpose while rpc request: {purpose}")
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details('Wrong Purpose')
                return stripe_pb2.GetCheckoutLinkResponse()




            stripe_service = StripeService(success_url=str(request.success_link), cancel_url=str(request.cancel_link))
            session = await asyncio.to_thread(
                stripe_service.create_checkout_session,
                product,
            )
            async with get_db_context() as db:
                payment_service = PaymentService(db)
                await payment_service.create(PaymentCreate(user_external_id=request.user_external_id, source=request.source,
                                                           provider='STRIPE', amount=product.price_data.unit_amount,
                                                           purpose=product.price_data.product_data.name,
                                                           provider_payment_id=session.id,
                                                           purpose_external_id=request.purpose_external_id, ))

                return stripe_pb2.GetCheckoutLinkResponse(link=session.url)
        except Exception as e:
            logger.error(f"Error while rpc request: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details('Internal Error')
            return stripe_pb2.GetCheckoutLinkResponse()
