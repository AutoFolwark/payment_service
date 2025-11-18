from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from database.db.session import get_db
from database.schemas.payment import PaymentStatus, Purposes
from database.schemas.transaction import TransactionType
from router.paypal import private
from main import app


def _override_permission_dependencies():
    def _user_override():
        return SimpleNamespace(uuid="test-user")

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/private/paypal/"):
            continue
        for dependency in route.dependant.dependencies:
            qualname = getattr(dependency.call, "__qualname__", "")
            if "require_permissions.<locals>.dependency" in qualname:
                app.dependency_overrides[dependency.call] = _user_override


@pytest.fixture
def client(monkeypatch):
    app.dependency_overrides.clear()

    async def _override_db():
        yield None

    app.dependency_overrides[get_db] = _override_db
    _override_permission_dependencies()

    async def immediate_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(private.asyncio, "to_thread", immediate_to_thread)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _patch_service(monkeypatch, service_name: str, instance):
    monkeypatch.setattr(private, service_name, lambda *_args, **_kwargs: instance)


def _sample_plan(plan_id: int = 1):
    return SimpleNamespace(
        id=plan_id,
        name="Basic",
        description="Plan description",
        max_bid_one_time=5.0,
        bid_power=100,
        price=19.99,
    )


def test_paypal_create_order_success(monkeypatch, client):
    plan = _sample_plan()
    plan_service = MagicMock(get=AsyncMock(return_value=plan))
    payment_service = MagicMock(create=AsyncMock())
    paypal_service = MagicMock(create_order_for_plan=MagicMock(return_value="order-123"))

    _patch_service(monkeypatch, "PlanService", plan_service)
    _patch_service(monkeypatch, "PaymentService", payment_service)
    _patch_service(monkeypatch, "PaypalService", paypal_service)

    response = client.post("/private/paypal/create-order", json={"plan_id": plan.id})

    assert response.status_code == 201
    assert response.json() == {"order_id": "order-123"}
    plan_service.get.assert_awaited_once_with(plan.id)
    paypal_service.create_order_for_plan.assert_called_once_with(plan)
    payment_service.create.assert_awaited_once()
    payment_create = payment_service.create.call_args.args[0]
    assert payment_create.user_external_id == "test-user"
    assert payment_create.provider_payment_id == "order-123"
    assert payment_create.amount == plan.price
    assert payment_create.purpose_external_id == str(plan.id)
    assert payment_create.purpose == Purposes.PLAN_PURCHASE
    assert payment_create.status == PaymentStatus.PENDING


def test_paypal_create_order_plan_not_found(monkeypatch, client):
    plan_service = MagicMock(get=AsyncMock(return_value=None))
    _patch_service(monkeypatch, "PlanService", plan_service)

    response = client.post("/private/paypal/create-order", json={"plan_id": 99})

    assert response.status_code == 404
    assert response.json()["detail"] == "Plan not found"
    plan_service.get.assert_awaited_once_with(99)


def test_paypal_create_order_paypal_failure(monkeypatch, client):
    plan = _sample_plan()
    plan_service = MagicMock(get=AsyncMock(return_value=plan))
    payment_service = MagicMock(create=AsyncMock())
    paypal_service = MagicMock(
        create_order_for_plan=MagicMock(side_effect=RuntimeError("boom"))
    )

    _patch_service(monkeypatch, "PlanService", plan_service)
    _patch_service(monkeypatch, "PaymentService", payment_service)
    _patch_service(monkeypatch, "PaypalService", paypal_service)

    response = client.post("/private/paypal/create-order", json={"plan_id": plan.id})

    assert response.status_code == 500
    assert response.json()["detail"] == "Unable to create PayPal order"
    payment_service.create.assert_not_called()
    paypal_service.create_order_for_plan.assert_called_once_with(plan)


def test_paypal_capture_order_success(monkeypatch, client):
    plan = _sample_plan()
    payment = SimpleNamespace(
        id=11,
        user_external_id="test-user",
        purpose_external_id=str(plan.id),
    )
    account = SimpleNamespace(id=22)

    payment_service = MagicMock(
        get_by_provider_payment_id=AsyncMock(return_value=payment),
        update=AsyncMock(),
    )
    plan_service = MagicMock(get=AsyncMock(return_value=plan))
    account_service = MagicMock(
        get_by_user_uuid=AsyncMock(return_value=account),
        update=AsyncMock(),
    )
    transaction_service = MagicMock(create=AsyncMock())
    paypal_service = MagicMock(
        capture_order=MagicMock(return_value={"status": "COMPLETED"})
    )

    _patch_service(monkeypatch, "PaymentService", payment_service)
    _patch_service(monkeypatch, "PlanService", plan_service)
    _patch_service(monkeypatch, "UserAccountService", account_service)
    _patch_service(monkeypatch, "TransactionService", transaction_service)
    _patch_service(monkeypatch, "PaypalService", paypal_service)

    response = client.post("/private/paypal/capture-order", json={"order_id": "order-123"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == plan.id
    assert body["price"] == plan.price
    assert body["bid_power"] == plan.bid_power

    payment_service.get_by_provider_payment_id.assert_awaited_once_with("order-123")
    paypal_service.capture_order.assert_called_once_with("order-123")
    plan_service.get.assert_awaited_once_with(plan.id)
    account_service.get_by_user_uuid.assert_awaited_once_with("test-user")
    transaction_service.create.assert_awaited_once()
    payment_service.update.assert_awaited_once()

    payment_update = payment_service.update.call_args.args[1]
    assert payment_update.status == PaymentStatus.COMPLETED

    transaction_payload = transaction_service.create.call_args.args[0]
    assert transaction_payload.user_account_id == account.id
    assert transaction_payload.plan_id == plan.id
    assert transaction_payload.transaction_type == TransactionType.PLAN_PURCHASE
    assert transaction_payload.amount == plan.bid_power

    account_update = account_service.update.call_args.args[1]
    assert account_update.plan_id == plan.id
    assert account_update.balance == plan.bid_power


def test_paypal_capture_order_payment_missing(monkeypatch, client):
    payment_service = MagicMock(
        get_by_provider_payment_id=AsyncMock(return_value=None)
    )
    _patch_service(monkeypatch, "PaymentService", payment_service)

    response = client.post("/private/paypal/capture-order", json={"order_id": "missing"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Payment not found for this order or user mismatch"
    payment_service.get_by_provider_payment_id.assert_awaited_once_with("missing")


def test_paypal_capture_order_not_completed(monkeypatch, client):
    plan = _sample_plan()
    payment = SimpleNamespace(
        id=11,
        user_external_id="test-user",
        purpose_external_id=str(plan.id),
    )
    payment_service = MagicMock(
        get_by_provider_payment_id=AsyncMock(return_value=payment),
        update=AsyncMock(),
    )
    paypal_service = MagicMock(
        capture_order=MagicMock(return_value={"status": "PENDING"})
    )

    _patch_service(monkeypatch, "PaymentService", payment_service)
    _patch_service(monkeypatch, "PaypalService", paypal_service)

    response = client.post("/private/paypal/capture-order", json={"order_id": "order-123"})

    assert response.status_code == 400
    assert response.json()["detail"] == "PayPal order not completed"
    payment_service.update.assert_awaited_once()
    payment_update = payment_service.update.call_args.args[1]
    assert payment_update.status == PaymentStatus.FAILED


def test_paypal_capture_order_plan_not_found(monkeypatch, client):
    payment = SimpleNamespace(
        id=11,
        user_external_id="test-user",
        purpose_external_id="5",
    )
    payment_service = MagicMock(
        get_by_provider_payment_id=AsyncMock(return_value=payment),
        update=AsyncMock(),
    )
    plan_service = MagicMock(get=AsyncMock(return_value=None))
    paypal_service = MagicMock(
        capture_order=MagicMock(return_value={"status": "COMPLETED"})
    )

    _patch_service(monkeypatch, "PaymentService", payment_service)
    _patch_service(monkeypatch, "PlanService", plan_service)
    _patch_service(monkeypatch, "PaypalService", paypal_service)

    response = client.post("/private/paypal/capture-order", json={"order_id": "order-123"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Plan not found"
    plan_service.get.assert_awaited_once_with(int(payment.purpose_external_id))
    payment_service.update.assert_not_called()


def test_paypal_capture_order_user_account_not_found(monkeypatch, client):
    plan = _sample_plan()
    payment = SimpleNamespace(
        id=11,
        user_external_id="test-user",
        purpose_external_id=str(plan.id),
    )
    payment_service = MagicMock(
        get_by_provider_payment_id=AsyncMock(return_value=payment),
        update=AsyncMock(),
    )
    plan_service = MagicMock(get=AsyncMock(return_value=plan))
    account_service = MagicMock(get_by_user_uuid=AsyncMock(return_value=None))
    paypal_service = MagicMock(
        capture_order=MagicMock(return_value={"status": "COMPLETED"})
    )

    _patch_service(monkeypatch, "PaymentService", payment_service)
    _patch_service(monkeypatch, "PlanService", plan_service)
    _patch_service(monkeypatch, "UserAccountService", account_service)
    _patch_service(monkeypatch, "PaypalService", paypal_service)

    response = client.post("/private/paypal/capture-order", json={"order_id": "order-123"})

    assert response.status_code == 404
    assert response.json()["detail"] == "User account not found"
    account_service.get_by_user_uuid.assert_awaited_once_with("test-user")
    payment_service.update.assert_not_called()
    plan_service.get.assert_awaited_once_with(plan.id)
