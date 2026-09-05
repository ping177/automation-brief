"""Offline smoke tests for the explicit v1.4 Selector quality evaluator."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from evaluate_event_selector import (  # noqa: E402
    _DeepSeekSelectorGateway,
    FIXTURE_PATH,
    DEEPSEEK_API_KEY_ENV,
    DEEPSEEK_ENDPOINT,
    DEEPSEEK_MAX_ATTEMPTS,
    DEEPSEEK_MODEL,
    DEEPSEEK_PROVIDER_ID,
    DEEPSEEK_TIMEOUT_SECONDS,
    build_dry_run_report,
    evaluate_quality_runs,
    load_quality_fixture,
    parse_args,
    summarize_observations,
)
from llm_gateway import (  # noqa: E402
    GatewayError,
    GatewayResponse,
    OpenAICompatibleGatewayConfig,
    OpenAICompatibleJSONGateway,
)


class CapturingDelegate:
    def __init__(self) -> None:
        self.parameters: object = None

    def complete_json(self, messages, *, parameters=None):
        self.parameters = parameters
        return GatewayResponse(
            payload={"selected": []},
            attempts=1,
            provider_id="fixture-provider",
            model="fixture-model",
        )


class ParseFailureGateway:
    def complete_json(self, messages, *, parameters=None):
        raise GatewayError(
            "response_parse_failed",
            1,
            parse_reason="finish_reason_length",
        )


class SuccessfulSelectionGateway:
    def __init__(self, event_candidate_id: str) -> None:
        self.event_candidate_id = event_candidate_id

    def complete_json(self, messages, *, parameters=None):
        return GatewayResponse(
            payload={
                "selected": [
                    {
                        "event_candidate_id": self.event_candidate_id,
                        "order": 1,
                    }
                ]
            },
            attempts=1,
            provider_id="fixture-provider",
            model="fixture-model",
        )


class OuterContractFailureGateway:
    def complete_json(self, messages, *, parameters=None):
        return GatewayResponse(
            payload={"selected": {"private-id": "private-news-text"}},
            attempts=1,
            provider_id="fixture-provider",
            model="fixture-model",
        )


class RequestCaptureTransport:
    def __init__(self) -> None:
        self.body = None

    def __call__(self, request, timeout):
        self.body = json.loads(request.data)
        return (
            200,
            json.dumps(
                {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"content": '{"selected": []}'},
                        }
                    ]
                }
            ).encode("utf-8"),
        )


def _assert_no_reference_keys(value: object) -> None:
    forbidden = {"event_key", "expectation", "provenance", "must_include", "should_omit"}
    if isinstance(value, dict):
        assert forbidden.isdisjoint(value)
        for child in value.values():
            _assert_no_reference_keys(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_reference_keys(child)


def test_fixture_builds_a_canonical_pool_with_minimal_reference_labels() -> None:
    fixture = load_quality_fixture(FIXTURE_PATH)

    assert fixture.fixture_id == "v1-4-minimal-editorial-mix"
    assert fixture.provenance == "synthetic"
    assert len(fixture.event_candidates) == len(fixture.expectation_by_key) == 8
    assert set(fixture.expectation_by_key.values()) == {
        "must_include",
        "judgment_call",
        "should_omit",
    }
    article_ids = {item.article_id for item in fixture.articles}
    assert all(
        set(item.article_ids).issubset(article_ids) for item in fixture.event_candidates
    )
    assert len(fixture.key_by_candidate_id) == len(fixture.event_candidates)


def test_dry_run_uses_the_real_selector_request_path_without_network_or_label_leakage() -> None:
    fixture = load_quality_fixture(FIXTURE_PATH)

    report = build_dry_run_report(fixture)

    assert report["mode"] == "dry-run"
    assert report["gateway_calls"] == 1
    assert report["transport_calls"] == 0
    assert report["stage_status"] == "succeeded"
    assert report["event_count"] == len(fixture.event_candidates)
    messages = report["request"]["messages"]
    assert messages[0]["role"] == "system"
    assert "about 10 minutes" in messages[0]["content"]
    assert "target number" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    _, separator, projection_json = messages[1]["content"].partition("\n")
    assert separator
    projection = json.loads(projection_json)
    assert len(projection["event_candidates"]) == len(fixture.event_candidates)
    _assert_no_reference_keys(projection)


def test_summary_exposes_stability_omission_and_padding_facts_without_a_score() -> None:
    fixture = load_quality_fixture(FIXTURE_PATH)
    must_include = sorted(
        key
        for key, expectation in fixture.expectation_by_key.items()
        if expectation == "must_include"
    )
    judgment_call = next(
        key
        for key, expectation in fixture.expectation_by_key.items()
        if expectation == "judgment_call"
    )
    should_omit = next(
        key
        for key, expectation in fixture.expectation_by_key.items()
        if expectation == "should_omit"
    )
    observations = [
        {
            "run": 1,
            "status": "succeeded",
            "selected_event_keys": [*must_include, judgment_call],
            "failures": [],
        },
        {
            "run": 2,
            "status": "succeeded",
            "selected_event_keys": [*must_include[:-1], should_omit],
            "failures": [],
        },
    ]

    summary = summarize_observations(fixture, observations)

    assert summary["all_runs_succeeded"] is True
    assert summary["selection_sets_stable"] is False
    assert summary["selection_order_stable"] is False
    assert summary["must_include_consistent"] is False
    assert summary["no_padding_consistent"] is False
    assert summary["runs"][0]["missing_must_include"] == []
    assert summary["runs"][0]["selected_should_omit"] == []
    assert summary["runs"][1]["missing_must_include"] == [must_include[-1]]
    assert summary["runs"][1]["selected_should_omit"] == [should_omit]
    assert "score" not in json.dumps(summary, ensure_ascii=False).casefold()


def test_cli_defaults_to_dry_run_and_keeps_real_provider_explicit() -> None:
    args = parse_args(["--fixture", str(FIXTURE_PATH)])

    assert args.real_provider is None
    assert args.runs == 3
    source = (PROJECT_ROOT / "scripts" / "evaluate_event_selector.py").read_text(
        encoding="utf-8"
    )
    for forbidden_dependency in (
        "from ai_curator",
        "import ai_curator",
        "from main",
        "import main",
    ):
        assert forbidden_dependency not in source


def test_real_provider_adapter_uses_the_frozen_deepseek_request_parameters() -> None:
    delegate = CapturingDelegate()
    gateway = _DeepSeekSelectorGateway(delegate)

    gateway.complete_json([{"role": "user", "content": "fixture"}])

    assert delegate.parameters == {
        "max_tokens": 8192,
        "thinking": {"type": "disabled"},
    }


def test_quality_runs_surface_safe_parse_diagnostics_without_provider_content() -> None:
    fixture = load_quality_fixture(FIXTURE_PATH)

    observations = evaluate_quality_runs(fixture, 1, ParseFailureGateway())

    assert observations == [
        {
            "run": 1,
            "status": "failed",
            "selected_event_keys": [],
            "failures": [
                {"item_id": None, "code": "response_parse_failed"},
            ],
            "diagnostic_ref": "llm_gateway:finish_reason_length",
        }
    ]
    assert "content" not in json.dumps(observations, ensure_ascii=False).casefold()


def test_quality_runs_leave_successful_selection_observations_unchanged() -> None:
    fixture = load_quality_fixture(FIXTURE_PATH)
    selected_candidate = fixture.event_candidates[0]

    observations = evaluate_quality_runs(
        fixture,
        1,
        SuccessfulSelectionGateway(selected_candidate.event_candidate_id),
    )

    assert observations == [
        {
            "run": 1,
            "status": "succeeded",
            "selected_event_keys": [
                fixture.key_by_candidate_id[selected_candidate.event_candidate_id]
            ],
            "failures": [],
        }
    ]


def test_quality_runs_surface_only_safe_outer_contract_structure() -> None:
    fixture = load_quality_fixture(FIXTURE_PATH)

    observations = evaluate_quality_runs(fixture, 1, OuterContractFailureGateway())

    assert observations[0]["diagnostic_ref"] == (
        "event_selector:selected_wrong_type_object"
    )
    serialized = json.dumps(observations, ensure_ascii=False)
    assert "private-id" not in serialized
    assert "private-news-text" not in serialized


def test_real_gateway_request_contains_json_format_and_selector_example() -> None:
    fixture = load_quality_fixture(FIXTURE_PATH)
    transport = RequestCaptureTransport()
    gateway = _DeepSeekSelectorGateway(
        OpenAICompatibleJSONGateway(
            OpenAICompatibleGatewayConfig(
                provider_id=DEEPSEEK_PROVIDER_ID,
                model=DEEPSEEK_MODEL,
                endpoint=DEEPSEEK_ENDPOINT,
                api_key_env=DEEPSEEK_API_KEY_ENV,
                timeout=DEEPSEEK_TIMEOUT_SECONDS,
                max_attempts=DEEPSEEK_MAX_ATTEMPTS,
            ),
            transport=transport,
        )
    )
    previous_key = os.environ.get(DEEPSEEK_API_KEY_ENV)
    os.environ[DEEPSEEK_API_KEY_ENV] = "offline-only-selector-key"
    try:
        observations = evaluate_quality_runs(fixture, 1, gateway)
    finally:
        if previous_key is None:
            os.environ.pop(DEEPSEEK_API_KEY_ENV, None)
        else:
            os.environ[DEEPSEEK_API_KEY_ENV] = previous_key

    assert observations[0]["status"] == "succeeded"
    assert transport.body["response_format"] == {"type": "json_object"}
    assert transport.body["max_tokens"] == 8192
    assert transport.body["thinking"] == {"type": "disabled"}
    system_prompt = transport.body["messages"][0]["content"]
    assert '"event_candidate_id": "example_event_id"' in system_prompt
    assert (
        "Return an empty selected array only when no candidate naturally satisfies this "
        "major-event standard."
    ) in system_prompt
    assert "selected array may be empty" not in system_prompt.casefold()


def main() -> None:
    test_fixture_builds_a_canonical_pool_with_minimal_reference_labels()
    test_dry_run_uses_the_real_selector_request_path_without_network_or_label_leakage()
    test_summary_exposes_stability_omission_and_padding_facts_without_a_score()
    test_cli_defaults_to_dry_run_and_keeps_real_provider_explicit()
    test_real_provider_adapter_uses_the_frozen_deepseek_request_parameters()
    test_quality_runs_surface_safe_parse_diagnostics_without_provider_content()
    test_quality_runs_leave_successful_selection_observations_unchanged()
    test_quality_runs_surface_only_safe_outer_contract_structure()
    test_real_gateway_request_contains_json_format_and_selector_example()
    print("offline event selector quality smoke passed")


if __name__ == "__main__":
    main()
