import uvicorn
from fastapi import FastAPI, APIRouter
from fastapi_problem.handler import new_exception_handler, add_exception_handler

from config import settings
from router.health import health_router
from router.paypal.private import paypal_private_router
from router.stripe.private import stripe_private_router
from router.stripe.public import stripe_public_router
from router.v1.private import private_router
from router.v1.public import public_router

docs_url = "/docs" if settings.enable_docs else None
redoc_url = "/redoc"  if settings.enable_docs else None
openapi_url = "/openapi.json" if settings.enable_docs else None

app = FastAPI(title='Payment Service',
              description='Process payments via Stripe, Paypal',
              version='0.0.1',
              root_path=settings.ROOT_PATH,
              docs_url=docs_url,
              redoc_url=redoc_url,
              openapi_url=openapi_url)

eh = new_exception_handler()
add_exception_handler(app, eh)


public_endpoints = APIRouter(prefix="/public", tags=["Public"])
private_endpoints = APIRouter(prefix="/private")

# stripe
public_endpoints.include_router(stripe_public_router, prefix="/stripe", tags=["Stripe"])
private_endpoints.include_router(stripe_private_router, prefix="/stripe", tags=["Stripe"])

# paypal
private_endpoints.include_router(paypal_private_router, prefix="/paypal", tags=["Paypal"])

private_endpoints.include_router(private_router)
public_endpoints.include_router(public_router)

app.include_router(public_endpoints)
app.include_router(private_endpoints)

app.include_router(health_router)


if __name__ == '__main__':
    uvicorn.run(app, host="localhost", port=8002)
