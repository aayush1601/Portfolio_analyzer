"""Phase 17: who a request belongs to. API Gateway verifies the Cognito JWT; the app only reads its claims."""

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.portfolio import current_user
from app.config import get_settings


def request(claims: dict | None = None) -> Request:
    scope = {"type": "http", "headers": []}
    if claims is not None:  # what Mangum puts in the scope for an HTTP API event with a JWT authorizer
        scope["aws.event"] = {"requestContext": {"authorizer": {"jwt": {"claims": claims}}}}
    return Request(scope)


@pytest.fixture
def settings(monkeypatch):
    def use(**env):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        get_settings.cache_clear()

    yield use
    get_settings.cache_clear()


def test_signed_in_user_is_the_token_subject(settings):
    settings(AUTH_REQUIRED="true")
    assert current_user(request({"sub": "a1b2-c3", "email": "x@y.in"})) == "a1b2-c3"


def test_missing_identity_is_refused_when_auth_is_required(settings):
    settings(AUTH_REQUIRED="true")
    with pytest.raises(HTTPException) as e:
        current_user(request())
    assert e.value.status_code == 401


def test_local_development_has_one_local_user(settings):
    settings(AUTH_REQUIRED="false")
    assert current_user(request()) == "local"
