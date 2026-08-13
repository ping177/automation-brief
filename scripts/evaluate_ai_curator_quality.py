from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any


REFERENCE_TIERS = frozenset({"must_include_at_10", "strong_candidate"})
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CHINESE_ATTRIBUTION_CLAUSE_PATTERN = re.compile(
    r"[\u4e00-\u9fff·]{2,12}称(?:已|将|正|未|没有|不会|可以|可能|美|中|其|该)"
)
_ATTRIBUTION_MARKERS = (
    "according to",
    "alleges",
    "alleged",
    "claims",
    "claimed",
    "officials said",
    "reports",
    "reported",
    "reportedly",
    "said",
    "says",
    "声称",
    "声明",
    "据报道",
    "据外媒",
    "据消息",
    "报道称",
    "消息称",
    "官员称",
    "政府称",
    "军方称",
    "警方称",
    "公司称",
    "机构称",
    "发言人称",
    "援引",
    "表示",
)


def load_gold_reference(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("gold reference must be a JSON object")
    if not isinstance(payload.get("snapshot_id"), str) or not payload["snapshot_id"].strip():
        raise ValueError("gold reference snapshot_id must be non-empty")
    if not _SHA256_PATTERN.fullmatch(str(payload.get("snapshot_sha256", ""))):
        raise ValueError("gold reference snapshot_sha256 must be lowercase SHA-256")
    if not isinstance(payload.get("reference_max_events"), int) or payload["reference_max_events"] <= 0:
        raise ValueError("gold reference reference_max_events must be positive")

    raw_events = payload.get("events")
    if not isinstance(raw_events, list) or not raw_events:
        raise ValueError("gold reference events must be a non-empty list")
    seen_reference_ids: set[str] = set()
    for event in raw_events:
        if not isinstance(event, dict):
            raise ValueError("gold reference event must be an object")
        reference_id = _required_text(event, "reference_id")
        if reference_id in seen_reference_ids:
            raise ValueError("gold reference_id values must be unique")
        seen_reference_ids.add(reference_id)
        if event.get("tier") not in REFERENCE_TIERS:
            raise ValueError("gold reference event has unsupported tier")
        supporting_ids = _required_id_list(event, "supporting_article_ids", allow_empty=False)
        forbidden_ids = _required_id_list(event, "forbidden_article_ids", allow_empty=True)
        if set(supporting_ids).intersection(forbidden_ids):
            raise ValueError("supporting and forbidden article ids must be disjoint")
        for field_name in ("attribution_required", "uncertainty_expected"):
            if not isinstance(event.get(field_name), bool):
                raise ValueError(f"gold reference {field_name} must be boolean")

    _required_id_list(payload, "representative_omit_article_ids", allow_empty=True)
    return payload


def evaluate_snapshot_response(
    response: dict[str, Any],
    gold: dict[str, Any],
) -> dict[str, object]:
    raw_events = response.get("events")
    if not isinstance(raw_events, list):
        raise ValueError("response events must be a list")
    events = [_response_event(event) for event in raw_events]

    references = gold["events"]
    matched_events = {
        reference["reference_id"]: [
            event
            for event in events
            if set(reference["supporting_article_ids"]).intersection(
                event["evidence_article_ids"]
            )
        ]
        for reference in references
    }

    must_include_missing = [
        reference["reference_id"]
        for reference in references
        if reference["tier"] == "must_include_at_10"
        and not matched_events[reference["reference_id"]]
    ]
    priority_missing = any(
        not matched_events[reference["reference_id"]] for reference in references
    )
    background_over_priority = (
        [event["event_id"] for event in events if event["importance"] == "background"]
        if priority_missing
        else []
    )

    forbidden_evidence_binding: dict[str, list[str]] = {}
    attribution_required_missing: list[str] = []
    uncertainty_expected_missing: list[str] = []
    for reference in references:
        reference_id = reference["reference_id"]
        reference_matches = matched_events[reference_id]
        if not reference_matches:
            continue

        bound_forbidden = [
            article_id
            for article_id in reference["forbidden_article_ids"]
            if any(article_id in event["evidence_article_ids"] for event in reference_matches)
        ]
        if bound_forbidden:
            forbidden_evidence_binding[reference_id] = bound_forbidden

        if reference["attribution_required"] and any(
            not _has_attribution(event["canonical_title"])
            or not _has_attribution(event["summary"])
            for event in reference_matches
        ):
            attribution_required_missing.append(reference_id)

        if reference["uncertainty_expected"] and any(
            event["confidence"] == "high" and not event["uncertainties"]
            for event in reference_matches
        ):
            uncertainty_expected_missing.append(reference_id)

    return {
        "must_include_missing": must_include_missing,
        "background_over_priority": background_over_priority,
        "forbidden_evidence_binding": forbidden_evidence_binding,
        "attribution_required_missing": attribution_required_missing,
        "uncertainty_expected_missing": uncertainty_expected_missing,
    }


def _response_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("response event must be an object")
    return {
        "event_id": _required_text(value, "event_id"),
        "canonical_title": _required_text(value, "canonical_title"),
        "summary": _required_text(value, "summary"),
        "importance": _required_text(value, "importance"),
        "evidence_article_ids": _required_id_list(
            value, "evidence_article_ids", allow_empty=False
        ),
        "confidence": _required_text(value, "confidence"),
        "uncertainties": _required_text_list(value, "uncertainties"),
    }


def _required_text(value: dict[str, Any], field_name: str) -> str:
    text = str(value.get(field_name, "")).strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    return text


def _required_id_list(
    value: dict[str, Any], field_name: str, *, allow_empty: bool
) -> list[str]:
    raw_items = value.get(field_name)
    if not isinstance(raw_items, list) or (not raw_items and not allow_empty):
        raise ValueError(f"{field_name} must be a list")
    items = [str(item).strip() for item in raw_items]
    if any(not item for item in items) or len(items) != len(set(items)):
        raise ValueError(f"{field_name} must contain unique non-empty ids")
    return items


def _required_text_list(value: dict[str, Any], field_name: str) -> list[str]:
    raw_items = value.get(field_name)
    if not isinstance(raw_items, list):
        raise ValueError(f"{field_name} must be a list")
    return [str(item).strip() for item in raw_items if str(item).strip()]


def _has_attribution(text: str) -> bool:
    normalized = text.casefold()
    return any(marker in normalized for marker in _ATTRIBUTION_MARKERS) or bool(
        _CHINESE_ATTRIBUTION_CLAUSE_PATTERN.search(normalized)
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate a CuratorResponse against a narrow snapshot gold reference."
    )
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gold = load_gold_reference(args.gold)
    response = json.loads(args.response.read_text(encoding="utf-8"))
    if not isinstance(response, dict):
        raise ValueError("response must be a JSON object")
    result = evaluate_snapshot_response(response, gold)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
