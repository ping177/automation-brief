"""Domain-neutral OpenAI-compatible JSON LLM transport.

This module owns only provider configuration, HTTP transport, bounded retry,
and parsing of the provider's generic response envelope. Business stages own
their logical request projection and semantic response validation.
"""

from __future__ import annotations

import json
import math
import os
import re
import socket
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_ATTEMPTS = 2
JSON_RESPONSE_FORMAT = {"type": "json_object"}
_ENVIRONMENT_VARIABLE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FAILURE_KINDS = frozenset(
    {
        "invalid_input",
        "timeout",
        "transport_failed",
        "provider_failed",
        "response_parse_failed",
    }
)


class GatewayError(RuntimeError):
    """Secret-safe typed failure for a single logical gateway invocation."""

    def __init__(
        self,
        kind: str,
        attempts: int,
        *,
        status: int | None = None,
    ) -> None:
        if kind not in _FAILURE_KINDS:
            raise ValueError("unsupported gateway failure kind")
        self.kind = kind
        self.attempts = attempts
        self.status = status
        super().__init__(kind)


class GatewayConfigurationError(GatewayError):
    """Configuration or request preflight failed before transport."""

    def __init__(self) -> None:
        super().__init__("invalid_input", 0)


@dataclass(frozen=True)
class OpenAICompatibleGatewayConfig:
    """Provider-neutral settings required for one OpenAI-compatible endpoint."""

    provider_id: str
    model: str
    endpoint: str
    api_key_env: str
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    max_attempts: int = DEFAULT_MAX_ATTEMPTS

    def __post_init__(self) -> None:
        for field_name in ("provider_id", "model", "endpoint", "api_key_env"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise GatewayConfigurationError()

        try:
            parsed_endpoint = urlsplit(self.endpoint)
            endpoint_hostname = parsed_endpoint.hostname
            endpoint_username = parsed_endpoint.username
            endpoint_password = parsed_endpoint.password
        except ValueError:
            raise GatewayConfigurationError() from None
        if (
            parsed_endpoint.scheme.lower() != "https"
            or not parsed_endpoint.netloc
            or endpoint_hostname is None
            or endpoint_username is not None
            or endpoint_password is not None
        ):
            raise GatewayConfigurationError()
        if isinstance(self.timeout, bool) or not isinstance(self.timeout, (int, float)):
            raise GatewayConfigurationError()
        if not math.isfinite(float(self.timeout)) or self.timeout <= 0:
            raise GatewayConfigurationError()
        if type(self.max_attempts) is not int or self.max_attempts not in (1, 2):
            raise GatewayConfigurationError()
        if not _ENVIRONMENT_VARIABLE_PATTERN.fullmatch(self.api_key_env):
            raise GatewayConfigurationError()


@dataclass(frozen=True)
class GatewayResponse:
    """Parsed provider JSON content plus non-secret invocation metadata."""

    payload: dict[str, Any]
    attempts: int
    provider_id: str
    model: str


class HTTPTransport(Protocol):
    """Callable transport seam used by the real adapter and offline tests."""

    def __call__(self, request: Request, timeout: float) -> tuple[int, bytes]:
        ...


class _HTTPStatusFailure(Exception):
    def __init__(self, status: int) -> None:
        self.status = status


class _NoRedirectHandler(HTTPRedirectHandler):
    """Turn every urllib redirect into a status failure instead of following it."""

    def redirect_request(
        self,
        request: Request,
        response: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        raise HTTPError(request.full_url, code, message, headers, response)


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler)


class _TransportFailure(Exception):
    def __init__(self, kind: str) -> None:
        self.kind = kind


def _urllib_transport(request: Request, timeout: float) -> tuple[int, bytes]:
    try:
        with _NO_REDIRECT_OPENER.open(request, timeout=timeout) as response:
            return int(response.status), response.read()
    except HTTPError as exc:
        # Never read or retain an untrusted provider error body.
        raise _HTTPStatusFailure(exc.code) from None
    except (socket.timeout, TimeoutError):
        raise _TransportFailure("timeout") from None
    except (URLError, OSError):
        raise _TransportFailure("transport") from None
    except Exception:
        raise _TransportFailure("transport") from None


def _serialize_request(
    messages: Sequence[Mapping[str, Any]],
    parameters: Mapping[str, Any] | None,
    model: str,
) -> bytes:
    if isinstance(messages, (str, bytes)):
        raise GatewayConfigurationError()
    try:
        message_values = tuple(messages)
    except (TypeError, ValueError):
        raise GatewayConfigurationError() from None
    if not message_values:
        raise GatewayConfigurationError()

    serialized_messages: list[dict[str, Any]] = []
    for message in message_values:
        if not isinstance(message, Mapping):
            raise GatewayConfigurationError()
        if any(not isinstance(key, str) for key in message):
            raise GatewayConfigurationError()
        role = message.get("role")
        content = message.get("content")
        if (
            not isinstance(role, str)
            or not role.strip()
            or not isinstance(content, str)
            or not content.strip()
        ):
            raise GatewayConfigurationError()
        serialized_messages.append(dict(message))

    if parameters is None:
        serialized_parameters: dict[str, Any] = {}
    elif isinstance(parameters, Mapping):
        serialized_parameters = dict(parameters)
    else:
        raise GatewayConfigurationError()

    if any(not isinstance(key, str) for key in serialized_parameters):
        raise GatewayConfigurationError()
    if any(key in serialized_parameters for key in ("model", "messages", "response_format")):
        raise GatewayConfigurationError()

    payload: dict[str, Any] = {
        "model": model,
        "messages": serialized_messages,
        "response_format": dict(JSON_RESPONSE_FORMAT),
    }
    payload.update(serialized_parameters)
    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise GatewayConfigurationError() from None


def _parse_provider_response(response_body: bytes, attempts: int) -> dict[str, Any]:
    try:
        envelope = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise GatewayError("response_parse_failed", attempts) from None

    if not isinstance(envelope, dict):
        raise GatewayError("response_parse_failed", attempts)
    choices = envelope.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise GatewayError("response_parse_failed", attempts)
    if choices[0].get("finish_reason") != "stop":
        raise GatewayError("response_parse_failed", attempts)
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise GatewayError("response_parse_failed", attempts)
    content = message.get("content")
    if isinstance(content, dict):
        payload = content
    elif isinstance(content, str):
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            raise GatewayError("response_parse_failed", attempts) from None
    else:
        raise GatewayError("response_parse_failed", attempts)
    if not isinstance(payload, dict):
        raise GatewayError("response_parse_failed", attempts)
    return payload


class OpenAICompatibleJSONGateway:
    """Synchronous, bounded-retry gateway for generic JSON model responses."""

    def __init__(
        self,
        config: OpenAICompatibleGatewayConfig,
        *,
        transport: HTTPTransport | None = None,
    ) -> None:
        if not isinstance(config, OpenAICompatibleGatewayConfig):
            raise GatewayConfigurationError()
        if transport is not None and not callable(transport):
            raise GatewayConfigurationError()
        self.config = config
        self._transport = transport or _urllib_transport

    def complete_json(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> GatewayResponse:
        """Send one immutable request and parse only generic JSON content."""

        body = _serialize_request(messages, parameters, self.config.model)
        api_key = os.environ.get(self.config.api_key_env, "").strip()
        if not api_key:
            raise GatewayError("invalid_input", 0)

        request = Request(
            self.config.endpoint,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                status, response_body = self._transport(request, self.config.timeout)
            except _HTTPStatusFailure as exc:
                if self._retryable_status(exc.status, attempt):
                    continue
                raise GatewayError("provider_failed", attempt, status=exc.status) from None
            except _TransportFailure as exc:
                if self._retryable_transport(exc.kind, attempt):
                    continue
                kind = "timeout" if exc.kind == "timeout" else "transport_failed"
                raise GatewayError(kind, attempt) from None
            except (socket.timeout, TimeoutError):
                if self._retryable_transport("timeout", attempt):
                    continue
                raise GatewayError("timeout", attempt) from None
            except OSError:
                if self._retryable_transport("transport", attempt):
                    continue
                raise GatewayError("transport_failed", attempt) from None
            except Exception:
                raise GatewayError("transport_failed", attempt) from None

            if isinstance(status, bool) or not isinstance(status, int):
                raise GatewayError("transport_failed", attempt) from None
            if not isinstance(response_body, (bytes, bytearray)):
                raise GatewayError("transport_failed", attempt) from None
            if status < 200 or status >= 300:
                if self._retryable_status(status, attempt):
                    continue
                raise GatewayError("provider_failed", attempt, status=status) from None

            payload = _parse_provider_response(bytes(response_body), attempt)
            return GatewayResponse(
                payload=payload,
                attempts=attempt,
                provider_id=self.config.provider_id,
                model=self.config.model,
            )

        # The loop always returns or raises; this protects type checkers.
        raise GatewayError("transport_failed", self.config.max_attempts)

    def _retryable_status(self, status: int, attempt: int) -> bool:
        return attempt < self.config.max_attempts and (
            status == 429 or 500 <= status <= 599
        )

    def _retryable_transport(self, kind: str, attempt: int) -> bool:
        return attempt < self.config.max_attempts and kind in {"timeout", "transport"}


__all__ = [
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_TIMEOUT_SECONDS",
    "GatewayConfigurationError",
    "GatewayError",
    "GatewayResponse",
    "HTTPTransport",
    "JSON_RESPONSE_FORMAT",
    "OpenAICompatibleGatewayConfig",
    "OpenAICompatibleJSONGateway",
]
