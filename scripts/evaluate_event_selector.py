#!/usr/bin/env python3
"""Explicit v1.4 Event Selector quality evaluator.

Dry-run is the default and never uses credentials or transport.  A real model
call requires ``--real-provider deepseek``.  Results are printed as JSON and
are not persisted automatically.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from canonical_domain import (  # noqa: E402
    Article,
    EventCandidate,
    StageStatus,
    datetime_in_report_window,
    normalize_canonical_datetime,
    validate_report_window,
)
from event_selector import SelectorGateway, select_events  # noqa: E402
from generation_2_runtime import (  # noqa: E402
    DEEPSEEK_API_KEY_ENV,
    DEEPSEEK_ENDPOINT,
    DEEPSEEK_MAX_ATTEMPTS,
    DEEPSEEK_MAX_TOKENS,
    DEEPSEEK_MODEL,
    DEEPSEEK_PROVIDER_ID,
    DEEPSEEK_TIMEOUT_SECONDS,
    DeepSeekGeneration2Gateway,
    build_deepseek_generation_2_gateway,
)
from llm_gateway import GatewayResponse  # noqa: E402


FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "event_selector_quality_v1_4.json"
DEFAULT_RUNS = 3
MAX_RUNS = 5
EXPECTATIONS = frozenset({"must_include", "judgment_call", "should_omit"})
_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class QualityFixture:
    fixture_id: str
    provenance: str
    window_start: datetime
    window_end: datetime
    event_candidates: tuple[EventCandidate, ...]
    articles: tuple[Article, ...]
    key_by_candidate_id: Mapping[str, str]
    expectation_by_key: Mapping[str, str]


class _CaptureGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[Sequence[Mapping[str, Any]], Mapping[str, Any] | None]] = []

    def complete_json(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> GatewayResponse:
        self.calls.append((messages, parameters))
        return GatewayResponse(
            payload={"selected": []},
            attempts=1,
            provider_id="dry-run",
            model="dry-run",
        )


_DeepSeekSelectorGateway = DeepSeekGeneration2Gateway


def _require_exact_keys(
    value: Mapping[str, Any], expected: set[str], context: str
) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} keys are invalid")


def _required_key(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not _KEY_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be a lowercase hyphenated key")
    return value


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text")
    return value


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be an ISO datetime")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError(f"{field_name} must be an ISO datetime") from error
    return normalize_canonical_datetime(parsed, field_name)


def load_quality_fixture(path: Path) -> QualityFixture:
    with Path(path).open("r", encoding="utf-8") as fixture_file:
        payload = json.load(fixture_file)
    if not isinstance(payload, Mapping):
        raise ValueError("fixture must be an object")
    _require_exact_keys(
        payload,
        {"fixture_id", "provenance", "window_start", "window_end", "events"},
        "fixture",
    )
    fixture_id = _required_key(payload["fixture_id"], "fixture_id")
    if payload["provenance"] != "synthetic":
        raise ValueError("fixture provenance must be synthetic")
    window_start, window_end = validate_report_window(
        _parse_datetime(payload["window_start"], "window_start"),
        _parse_datetime(payload["window_end"], "window_end"),
    )
    raw_events = payload["events"]
    if not isinstance(raw_events, list) or not raw_events:
        raise ValueError("fixture events must be a non-empty list")

    articles: list[Article] = []
    candidates: list[EventCandidate] = []
    key_by_candidate_id: dict[str, str] = {}
    expectation_by_key: dict[str, str] = {}
    for raw_event in raw_events:
        if not isinstance(raw_event, Mapping):
            raise ValueError("fixture event must be an object")
        _require_exact_keys(
            raw_event,
            {"event_key", "expectation", "articles"},
            "fixture event",
        )
        event_key = _required_key(raw_event["event_key"], "event_key")
        expectation = raw_event["expectation"]
        if event_key in expectation_by_key or expectation not in EXPECTATIONS:
            raise ValueError("fixture event key or expectation is invalid")
        raw_articles = raw_event["articles"]
        if not isinstance(raw_articles, list) or not raw_articles:
            raise ValueError("fixture event articles must be a non-empty list")

        event_articles: list[Article] = []
        for article_index, raw_article in enumerate(raw_articles, start=1):
            if not isinstance(raw_article, Mapping):
                raise ValueError("fixture article must be an object")
            _require_exact_keys(
                raw_article,
                {"source", "title", "summary", "published_at"},
                "fixture article",
            )
            summary = raw_article["summary"]
            if summary is not None and not isinstance(summary, str):
                raise ValueError("fixture article summary must be text or null")
            published_at = _parse_datetime(raw_article["published_at"], "published_at")
            if not datetime_in_report_window(published_at, window_start, window_end):
                raise ValueError("fixture article must fall inside the report window")
            item = Article.from_source(
                source=_required_text(raw_article["source"], "source"),
                url=(
                    f"https://fixture.example/v1-4/{fixture_id}/{event_key}/"
                    f"{article_index}"
                ),
                published_at=published_at,
                collected_at=window_end,
                language="und",
                title=_required_text(raw_article["title"], "title"),
                summary=summary,
            )
            event_articles.append(item)
            articles.append(item)

        candidate = EventCandidate.from_article_ids(
            item.article_id for item in event_articles
        )
        if candidate.event_candidate_id in key_by_candidate_id:
            raise ValueError("fixture event memberships must be unique")
        candidates.append(candidate)
        key_by_candidate_id[candidate.event_candidate_id] = event_key
        expectation_by_key[event_key] = expectation

    if not {"must_include", "should_omit"}.issubset(expectation_by_key.values()):
        raise ValueError("fixture requires must_include and should_omit references")
    return QualityFixture(
        fixture_id=fixture_id,
        provenance="synthetic",
        window_start=window_start,
        window_end=window_end,
        event_candidates=tuple(candidates),
        articles=tuple(articles),
        key_by_candidate_id=key_by_candidate_id,
        expectation_by_key=expectation_by_key,
    )


def _reference_expectations(fixture: QualityFixture) -> dict[str, list[str]]:
    return {
        expectation: sorted(
            key
            for key, value in fixture.expectation_by_key.items()
            if value == expectation
        )
        for expectation in sorted(EXPECTATIONS)
    }


def build_dry_run_report(fixture: QualityFixture) -> dict[str, Any]:
    gateway = _CaptureGateway()
    result = select_events(
        fixture.event_candidates,
        fixture.articles,
        fixture.window_start,
        fixture.window_end,
        gateway,
    )
    if result.status is not StageStatus.SUCCEEDED or result.outputs or result.failures:
        raise ValueError("dry-run selector request path failed")
    messages, parameters = gateway.calls[0]
    return {
        "mode": "dry-run",
        "fixture_id": fixture.fixture_id,
        "provenance": fixture.provenance,
        "event_count": len(fixture.event_candidates),
        "gateway_calls": len(gateway.calls),
        "transport_calls": 0,
        "stage_status": result.status.value,
        "reference_expectations": _reference_expectations(fixture),
        "request": {
            "messages": [dict(message) for message in messages],
            "parameters": parameters,
        },
    }


def summarize_observations(
    fixture: QualityFixture,
    observations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if isinstance(observations, (str, bytes)) or not observations:
        raise ValueError("observations must be a non-empty sequence")
    known_keys = set(fixture.expectation_by_key)
    must_include = sorted(
        key
        for key, expectation in fixture.expectation_by_key.items()
        if expectation == "must_include"
    )
    runs: list[dict[str, Any]] = []
    sequences: list[tuple[str, ...]] = []
    for observation in observations:
        if not isinstance(observation, Mapping):
            raise ValueError("observation must be an object")
        selected = observation.get("selected_event_keys")
        if (
            not isinstance(selected, list)
            or any(not isinstance(key, str) or key not in known_keys for key in selected)
            or len(selected) != len(set(selected))
        ):
            raise ValueError("selected_event_keys must contain unique known keys")
        selected_set = set(selected)
        sequences.append(tuple(selected))
        runs.append(
            {
                **dict(observation),
                "missing_must_include": [
                    key for key in must_include if key not in selected_set
                ],
                "selected_should_omit": [
                    key
                    for key in selected
                    if fixture.expectation_by_key[key] == "should_omit"
                ],
                "selected_judgment_calls": [
                    key
                    for key in selected
                    if fixture.expectation_by_key[key] == "judgment_call"
                ],
            }
        )
    selection_sets = {frozenset(sequence) for sequence in sequences}
    return {
        "all_runs_succeeded": all(run.get("status") == "succeeded" for run in runs),
        "selection_sets_stable": len(selection_sets) == 1,
        "selection_order_stable": len(set(sequences)) == 1,
        "must_include_consistent": all(not run["missing_must_include"] for run in runs),
        "no_padding_consistent": all(not run["selected_should_omit"] for run in runs),
        "runs": runs,
    }


def _deepseek_gateway() -> _DeepSeekSelectorGateway:
    return build_deepseek_generation_2_gateway()


def evaluate_quality_runs(
    fixture: QualityFixture,
    runs: int,
    gateway: SelectorGateway,
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for run_number in range(1, runs + 1):
        result = select_events(
            fixture.event_candidates,
            fixture.articles,
            fixture.window_start,
            fixture.window_end,
            gateway,
        )
        observation = {
            "run": run_number,
            "status": result.status.value,
            "selected_event_keys": [
                fixture.key_by_candidate_id[event.event_id]
                for event in result.outputs
            ],
            "failures": [failure.to_dict() for failure in result.failures],
        }
        if result.diagnostic_ref is not None:
            observation["diagnostic_ref"] = result.diagnostic_ref
        observations.append(observation)
    return observations


def _run_real_evaluation(fixture: QualityFixture, runs: int) -> dict[str, Any]:
    observations = evaluate_quality_runs(fixture, runs, _deepseek_gateway())
    return {
        "mode": "real-provider",
        "fixture_id": fixture.fixture_id,
        "provenance": fixture.provenance,
        "provider_id": DEEPSEEK_PROVIDER_ID,
        "model": DEEPSEEK_MODEL,
        "runs_requested": runs,
        "reference_expectations": _reference_expectations(fixture),
        "summary": summarize_observations(fixture, observations),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    parser.add_argument("--real-provider", choices=(DEEPSEEK_PROVIDER_ID,))
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        if type(args.runs) is not int or not 1 <= args.runs <= MAX_RUNS:
            raise ValueError(f"runs must be between 1 and {MAX_RUNS}")
        fixture = load_quality_fixture(args.fixture)
        report = (
            build_dry_run_report(fixture)
            if args.real_provider is None
            else _run_real_evaluation(fixture, args.runs)
        )
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
        if args.real_provider is not None and not report["summary"]["all_runs_succeeded"]:
            raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as error:
        raise SystemExit(
            f"event selector evaluation failed: {type(error).__name__}"
        ) from error


if __name__ == "__main__":
    main()
