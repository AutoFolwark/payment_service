from enum import Enum

from pydantic_settings import BaseSettings

from dotenv import load_dotenv

load_dotenv()

class Permissions(str, Enum):
    PLAN_ALL_READ = 'payments.plan.all:read'
    PLAN_ALL_WRITE = 'payments.plan.all:write'
    PLAN_ALL_DELETE = 'payments.plan.all:delete'

    ACCOUNT_ALL_READ = 'payments.account.all:read'
    ACCOUNT_ALL_WRITE = 'payments.account.all:write'

    ACCOUNT_OWN_READ = 'payments.plan.own:read'
    ACCOUNT_OWN_WRITE = 'payments.plan.own:write'


class Environment(str, Enum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "payments-service"
    DEBUG: bool = True
    ROOT_PATH: str = ''
    ENVIRONMENT: Environment = Environment.DEVELOPMENT

    @property
    def enable_docs(self) -> bool:
        return self.ENVIRONMENT in [Environment.DEVELOPMENT]

    # database
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str = "test_db"
    DB_USER: str = "postgres"
    DB_PASS: str = "testpass"

    # rabbitmq
    RABBITMQ_URL: str = 'amqp://guest:guest@localhost:5672/'
    RABBITMQ_EXCHANGE_NAME: str = 'events'

    #rpc
    GRPC_SERVER_PORT: int = 50053

    # stripe
    STRIPE_SECRET_KEY: str = ''
    STRIPE_WEBHOOK_SECRET: str = ''

    #paypal
    PAYPAL_CLIENT_ID: str = ''
    PAYPAL_CLIENT_SECRET: str = ''


settings = Settings()
