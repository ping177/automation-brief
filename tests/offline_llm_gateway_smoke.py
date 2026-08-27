from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.request import HTTPRedirectHandler, Request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import llm_gateway as llm_gateway_module  # noqa: E402
from llm_gateway import (  # noqa: E402
    GatewayConfigurationError,
    GatewayError,
    OpenAICompatibleJSONGateway,
    OpenAICompatibleGatewayConfig,
)


class FakeTransport:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[object, float]] = []

    def __call__(self, request: object, timeout: float) -> tuple[int, bytes]:
        self.calls.append((request, timeout))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response  # type: ignore[return-value]


class RedirectFixtureState:
    def __init__(self) -> None:
        self.source_requests: list[dict[str, str | None]] = []
        self.target_requests: list[dict[str, str | None]] = []


@contextmanager
def redirect_fixture_opener(state: RedirectFixtureState) -> Iterator[None]:
    # Exercise the production opener's redirect handler without opening a socket.
    opener = llm_gateway_module._NO_REDIRECT_OPENER
    original_open = opener.open

    def open_redirect(request: Request, timeout: float) -> object:
        state.source_requests.append(
            {
                "path": request.full_url,
                "authorization": request.get_header("Authorization"),
            }
        )
        location = "http://redirect-target.test/chat/completions"
        redirect_handler = next(
            handler
            for handler in opener.handlers
            if isinstance(handler, HTTPRedirectHandler)
        )
        redirected_request = redirect_handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {"Location": location},
            location,
        )
        if redirected_request is None:
            raise AssertionError("redirect handler must either reject or return a request")
        state.target_requests.append(
            {
                "path": redirected_request.full_url,
                "authorization": redirected_request.get_header("Authorization"),
            }
        )
        return _FixtureResponse(provider_envelope({"unexpected": "redirect"}))

    opener.open = open_redirect  # type: ignore[method-assign]
    previous_urlopen = getattr(llm_gateway_module, "urlopen", None)

    def forbidden_urlopen(*args: object, **kwargs: object) -> object:
        raise AssertionError("default transport must use the no-redirect opener")

    llm_gateway_module.urlopen = forbidden_urlopen  # type: ignore[attr-defined]
    try:
        yield
    finally:
        opener.open = original_open  # type: ignore[method-assign]
        if previous_urlopen is None:
            try:
                del llm_gateway_module.urlopen
            except AttributeError:
                pass
        else:
            llm_gateway_module.urlopen = previous_urlopen  # type: ignore[attr-defined]


class _FixtureResponse:
    def __init__(self, body: bytes) -> None:
        self.status = 200
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FixtureResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


@contextmanager
def env_value(name: str, value: str | None) -> Iterator[None]:
    previous = os.environ.get(name)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


def provider_envelope(payload: dict[str, object]) -> bytes:
    return json.dumps(
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": json.dumps(payload, ensure_ascii=False)},
                }
            ]
        },
        ensure_ascii=False,
    ).encode("utf-8")


def gateway(
    transport: FakeTransport,
    *,
    max_attempts: int = 2,
) -> OpenAICompatibleJSONGateway:
    return OpenAICompatibleJSONGateway(
        OpenAICompatibleGatewayConfig(
            provider_id="fixture",
            model="fixture-model",
            endpoint="https://example.test/v1/chat/completions",
            api_key_env="AUTOMATION_BRIEF_TEST_API_KEY",
            timeout=7.5,
            max_attempts=max_attempts,
        ),
        transport=transport,
    )


def test_default_transport_rejects_redirect_without_following() -> None:
    secret = "redirect-secret-test-token-do-not-leak"
    state = RedirectFixtureState()
    gateway_instance = OpenAICompatibleJSONGateway(
        OpenAICompatibleGatewayConfig(
            provider_id="fixture",
            model="fixture-model",
            endpoint="https://provider.test/v1/chat/completions",
            api_key_env="AUTOMATION_BRIEF_TEST_API_KEY",
            timeout=7.5,
            max_attempts=2,
        )
    )
    with env_value("AUTOMATION_BRIEF_TEST_API_KEY", secret), redirect_fixture_opener(
        state
    ):
        try:
            gateway_instance.complete_json(
                [{"role": "user", "content": "redirect case"}]
            )
        except GatewayError as error:
            assert error.kind == "provider_failed"
            assert error.attempts == 1
            assert error.status == 302
            assert secret not in str(error)
            assert secret not in repr(error)
        else:
            raise AssertionError("redirect must fail without following")

    assert len(state.source_requests) == 1
    assert state.source_requests[0]["authorization"] == f"Bearer {secret}"
    assert state.target_requests == []


def test_success_parses_json_content_and_attempts() -> None:
    transport = FakeTransport([(200, provider_envelope({"selected": []}))])
    with env_value("AUTOMATION_BRIEF_TEST_API_KEY", "offline-only-secret"):
        response = gateway(transport).complete_json(
            [{"role": "user", "content": "hello"}]
        )
    assert response.payload == {"selected": []}
    assert response.attempts == 1
    assert len(transport.calls) == 1


def test_success_accepts_provider_json_object_content() -> None:
    body = json.dumps(
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": {"ok": True}},
                }
            ]
        }
    ).encode("utf-8")
    transport = FakeTransport([(200, body)])
    with env_value("AUTOMATION_BRIEF_TEST_API_KEY", "offline-only-secret"):
        response = gateway(transport).complete_json(
            [{"role": "user", "content": "object content"}]
        )
    assert response.payload == {"ok": True}
    assert response.attempts == 1


def test_timeout_retries_once_with_exact_same_body() -> None:
    transport = FakeTransport(
        [TimeoutError(), (200, provider_envelope({"ok": True}))]
    )
    with env_value("AUTOMATION_BRIEF_TEST_API_KEY", "offline-only-secret"):
        response = gateway(transport).complete_json(
            [{"role": "system", "content": "fixed prompt"}]
        )
    assert response.payload == {"ok": True}
    assert response.attempts == 2
    first_request = transport.calls[0][0]
    second_request = transport.calls[1][0]
    assert first_request.data == second_request.data  # type: ignore[attr-defined]


def test_missing_api_key_fails_before_transport_without_secret() -> None:
    transport = FakeTransport([(200, provider_envelope({"ok": True}))])
    with env_value("AUTOMATION_BRIEF_TEST_API_KEY", None):
        try:
            gateway(transport).complete_json(
                [{"role": "user", "content": "no key"}]
            )
        except GatewayError as error:
            assert error.kind == "invalid_input"
            assert error.attempts == 0
            assert "offline-only-secret" not in str(error)
        else:
            raise AssertionError("missing API key must fail closed")
    assert transport.calls == []


def expect_gateway_error(
    transport: FakeTransport,
    *,
    kind: str,
    expected_attempts: int,
    expected_status: int | None = None,
    max_attempts: int = 2,
) -> GatewayError:
    with env_value("AUTOMATION_BRIEF_TEST_API_KEY", "offline-only-secret"):
        try:
            gateway(transport, max_attempts=max_attempts).complete_json(
                [{"role": "user", "content": "failure case"}]
            )
        except GatewayError as error:
            assert error.kind == kind
            assert error.attempts == expected_attempts
            assert error.status == expected_status
            return error
    raise AssertionError("gateway call must fail")


def test_max_attempts_one_does_not_retry() -> None:
    transport = FakeTransport(
        [TimeoutError(), (200, provider_envelope({"unexpected": "retry"}))]
    )
    expect_gateway_error(
        transport,
        kind="timeout",
        expected_attempts=1,
        max_attempts=1,
    )
    assert len(transport.calls) == 1


def test_max_attempts_two_is_valid() -> None:
    transport = FakeTransport([(200, provider_envelope({"ok": True}))])
    with env_value("AUTOMATION_BRIEF_TEST_API_KEY", "offline-only-secret"):
        response = gateway(transport, max_attempts=2).complete_json(
            [{"role": "user", "content": "two attempts is valid"}]
        )
    assert response.attempts == 1
    assert len(transport.calls) == 1


def test_transport_failure_classes_retry_once() -> None:
    retryable_cases = (
        TimeoutError(),
        OSError("offline transport"),
        (429, b"provider unavailable"),
        (503, b"provider unavailable"),
    )
    for first_failure in retryable_cases:
        transport = FakeTransport([first_failure, (200, provider_envelope({"ok": True}))])
        with env_value("AUTOMATION_BRIEF_TEST_API_KEY", "offline-only-secret"):
            response = gateway(transport).complete_json(
                [{"role": "user", "content": "retry"}],
                parameters={"max_tokens": 128},
            )
        assert response.attempts == 2
        assert len(transport.calls) == 2
        assert transport.calls[0][0].data == transport.calls[1][0].data  # type: ignore[attr-defined]


def test_retryable_failures_exhaust_at_two_attempts() -> None:
    exhausted_cases = (
        ([TimeoutError(), TimeoutError()], "timeout", None),
        ([OSError("offline transport"), OSError("offline transport")], "transport_failed", None),
        ([(429, b"provider unavailable"), (429, b"provider unavailable")], "provider_failed", 429),
        ([(502, b"provider unavailable"), (502, b"provider unavailable")], "provider_failed", 502),
    )
    for responses, kind, status in exhausted_cases:
        transport = FakeTransport(responses)
        expect_gateway_error(
            transport,
            kind=kind,
            expected_attempts=2,
            expected_status=status,
        )
        assert len(transport.calls) == 2
        assert transport.calls[0][0].data == transport.calls[1][0].data  # type: ignore[attr-defined]


def test_non_retryable_http_statuses_call_transport_once() -> None:
    for status in (400, 401, 403, 404):
        transport = FakeTransport([(status, b"provider error")])
        expect_gateway_error(
            transport,
            kind="provider_failed",
            expected_attempts=1,
            expected_status=status,
        )
        assert len(transport.calls) == 1


def test_invalid_provider_responses_do_not_retry() -> None:
    invalid_bodies = (
        b"not-json",
        json.dumps({"choices": []}).encode("utf-8"),
        json.dumps(
            {
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"content": "{}"},
                    }
                ]
            }
        ).encode("utf-8"),
        json.dumps(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "not-json"},
                    }
                ]
            }
        ).encode("utf-8"),
    )
    for body in invalid_bodies:
        transport = FakeTransport([(200, body)])
        expect_gateway_error(
            transport,
            kind="response_parse_failed",
            expected_attempts=1,
        )
        assert len(transport.calls) == 1


def test_invalid_configuration_and_request_fail_before_transport() -> None:
    invalid_configs = (
        {"endpoint": "http://example.test/chat"},
        {"endpoint": "https://[invalid"},
        {"timeout": 0.0},
        {"max_attempts": 3},
        {"api_key_env": "not-an-environment-variable"},
    )
    for overrides in invalid_configs:
        values: dict[str, object] = {
            "provider_id": "fixture",
            "model": "fixture-model",
            "endpoint": "https://example.test/v1/chat/completions",
            "api_key_env": "AUTOMATION_BRIEF_TEST_API_KEY",
        }
        values.update(overrides)
        try:
            OpenAICompatibleGatewayConfig(**values)  # type: ignore[arg-type]
        except GatewayError as error:
            assert error.kind == "invalid_input"
            assert error.attempts == 0
        else:
            raise AssertionError("invalid configuration must fail closed")

    transport = FakeTransport([(200, provider_envelope({"ok": True}))])
    with env_value("AUTOMATION_BRIEF_TEST_API_KEY", "offline-only-secret"):
        for messages, parameters in (
            ([], None),
            ([{"role": "user"}], None),
            ([{"role": "user", "content": "ok"}], {"model": "override"}),
        ):
            try:
                gateway(transport).complete_json(messages, parameters=parameters)  # type: ignore[arg-type]
            except GatewayError as error:
                assert error.kind == "invalid_input"
                assert error.attempts == 0
            else:
                raise AssertionError("invalid request must fail closed")
    assert transport.calls == []


def test_max_attempts_values_fail_closed_before_transport() -> None:
    invalid_values = (-1, 0, 3, 1.0, 2.0, "1", "2", True, False, None)
    for invalid_value in invalid_values:
        transport = FakeTransport([(200, provider_envelope({"ok": True}))])
        try:
            config = OpenAICompatibleGatewayConfig(
                provider_id="fixture",
                model="fixture-model",
                endpoint="https://example.test/v1/chat/completions",
                api_key_env="AUTOMATION_BRIEF_TEST_API_KEY",
                max_attempts=invalid_value,  # type: ignore[arg-type]
            )
            OpenAICompatibleJSONGateway(config, transport=transport).complete_json(
                [{"role": "user", "content": "invalid attempts"}]
            )
        except GatewayError as error:
            assert isinstance(error, GatewayConfigurationError)
            assert error.kind == "invalid_input"
            assert error.attempts == 0
        else:
            raise AssertionError("invalid max_attempts must fail closed")
        assert transport.calls == []


def test_gateway_response_and_errors_do_not_expose_api_key() -> None:
    secret = "offline-secret-must-not-escape"
    transport = FakeTransport([(200, provider_envelope({"ok": True}))])
    with env_value("AUTOMATION_BRIEF_TEST_API_KEY", secret):
        response = gateway(transport).complete_json(
            [{"role": "user", "content": "safe"}]
        )
    request = transport.calls[0][0]
    assert request.get_header("Authorization") == f"Bearer {secret}"  # type: ignore[attr-defined]
    assert secret not in request.data.decode("utf-8")  # type: ignore[attr-defined]
    assert secret not in repr(response)
    assert secret not in repr(response.payload)
    assert secret not in repr(response.__dict__)

    failing_transport = FakeTransport([OSError("transport details are not retained")])
    with env_value("AUTOMATION_BRIEF_TEST_API_KEY", secret):
        try:
            gateway(failing_transport).complete_json(
                [{"role": "user", "content": "safe"}]
            )
        except GatewayError as error:
            assert secret not in str(error)
            assert secret not in repr(error)
        else:
            raise AssertionError("transport failure must fail")


def test_gateway_has_no_generation_one_domain_dependencies() -> None:
    source = (PROJECT_ROOT / "llm_gateway.py").read_text(encoding="utf-8")
    for forbidden_name in (
        "EventCandidate",
        "CandidateArticle",
        "CuratorRequest",
        "CuratedEvent",
        "selection_order",
        "importance",
        "category",
        "ranking",
    ):
        assert forbidden_name not in source


def main() -> None:
    test_default_transport_rejects_redirect_without_following()
    test_success_parses_json_content_and_attempts()
    test_success_accepts_provider_json_object_content()
    test_timeout_retries_once_with_exact_same_body()
    test_missing_api_key_fails_before_transport_without_secret()
    test_max_attempts_one_does_not_retry()
    test_max_attempts_two_is_valid()
    test_transport_failure_classes_retry_once()
    test_retryable_failures_exhaust_at_two_attempts()
    test_non_retryable_http_statuses_call_transport_once()
    test_invalid_provider_responses_do_not_retry()
    test_invalid_configuration_and_request_fail_before_transport()
    test_max_attempts_values_fail_closed_before_transport()
    test_gateway_response_and_errors_do_not_expose_api_key()
    test_gateway_has_no_generation_one_domain_dependencies()
    print("offline llm gateway smoke passed")


if __name__ == "__main__":
    main()
