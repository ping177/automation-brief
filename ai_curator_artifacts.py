"""Filesystem artifacts for offline AI Curator shadow evaluations.

The artifact layer owns run metadata and review material. It deliberately
serializes the existing domain objects through small allowlists so provider
envelopes, headers, credentials, and arbitrary exception text cannot leak into
the shadow run directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import html
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any, Mapping, Sequence
import uuid

from ai_curator import CuratorContractError, CuratorRequest, CuratorResponse, validate_curator_response
from ai_curator_provider import (
    CuratorContentPolicyError,
    serialize_curator_request,
    validate_curator_content_policy,
)


_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]*$")


@dataclass(frozen=True)
class ShadowRunInfo:
    status: str
    provider_id: str
    model: str
    api_key_env: str
    attempts: int
    validation_status: str
    failure_stage: str = ""
    failure_code: str = ""
    failure_diagnostic_code: str = ""
    failure_diagnostic_path: str = ""
    failure_diagnostic_article_id: str = ""
    curator_request_bytes: int | None = None
    provider_request_body_bytes: int | None = None
    input_mode: str = ""
    original_candidate_count: int | None = None
    summary_max_chars: int | None = None
    summaries_capped_count: int | None = None
    summaries_unchanged_count: int | None = None
    max_candidate_count: int | None = None
    max_provider_request_body_bytes: int | None = None
    legacy_evaluation: str = "not_evaluated"
    candidate_window_start: datetime | None = None
    candidate_window_end: datetime | None = None


@dataclass(frozen=True)
class ShadowArtifactPaths:
    run_dir: Path
    run_json: Path
    request_json: Path | None
    response_json: Path | None
    trace_json: Path
    review_md: Path


def create_run_id(now: datetime | None = None) -> str:
    """Create a sortable, filesystem-safe run id with collision protection."""

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    timestamp = current.strftime("%Y%m%dT%H%M%S.%fZ")
    return f"{timestamp}-{uuid.uuid4().hex[:12]}"


def write_shadow_run(
    output_root: Path,
    *,
    report_date: date,
    request: CuratorRequest | None,
    response: CuratorResponse | None,
    trace_records: Sequence[Mapping[str, Any]],
    run_info: ShadowRunInfo,
    run_id: str | None = None,
    now: datetime | None = None,
) -> ShadowArtifactPaths:
    """Write one complete shadow run directory without overwriting another run."""

    validated_response = _validate_run_info(
        report_date=report_date,
        request=request,
        response=response,
        run_info=run_info,
    )
    resolved_run_id = run_id or create_run_id(now)
    if not _RUN_ID_PATTERN.fullmatch(resolved_run_id):
        raise ValueError("run_id must be filesystem-safe")

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    run_dir = output_root / resolved_run_id
    staging_dir = output_root / f".{resolved_run_id}.tmp-{uuid.uuid4().hex[:12]}"
    serialized_request = serialize_curator_request(request) if request is not None else None
    curator_request_bytes = len(serialized_request) if serialized_request is not None else None
    if run_info.curator_request_bytes is not None and run_info.curator_request_bytes != curator_request_bytes:
        raise ValueError("curator_request_bytes does not match request.json")
    if run_info.provider_request_body_bytes is not None and run_info.provider_request_body_bytes < 0:
        raise ValueError("provider_request_body_bytes must be non-negative")
    safe_trace_records = _safe_trace_records(trace_records)
    candidate_count = len(request.articles) if request is not None else 0
    legacy_selected_count = sum(
        1
        for record in safe_trace_records
        if record.get("trace_type") == "candidate" and bool(record.get("legacy_selected"))
    )
    succeeded = run_info.status == "succeeded"

    run_payload = {
        "status": run_info.status,
        "run_id": resolved_run_id,
        "report_date": report_date.isoformat(),
        "candidate_count": candidate_count,
        "legacy_selected_count": legacy_selected_count,
        "ai_event_count": len(response.events) if succeeded and response is not None else 0,
        "provider_id": _metadata_text(run_info.provider_id),
        "model": _metadata_text(run_info.model),
        "api_key_env": _safe_token(run_info.api_key_env),
        "attempts": run_info.attempts,
        "validation_status": "passed" if succeeded else _safe_token(run_info.validation_status),
        "curator_request_bytes": curator_request_bytes,
        "provider_request_body_bytes": run_info.provider_request_body_bytes,
        "failure_stage": _safe_token(run_info.failure_stage),
        "failure_code": _safe_token(run_info.failure_code),
        "legacy_evaluation": _legacy_evaluation_token(run_info.legacy_evaluation),
        "candidate_window_start": _datetime_text(run_info.candidate_window_start),
        "candidate_window_end": _datetime_text(run_info.candidate_window_end),
    }
    if run_info.input_mode:
        run_payload.update(
            {
                "input_mode": _input_mode_token(run_info.input_mode),
                "original_candidate_count": run_info.original_candidate_count,
                "summary_max_chars": run_info.summary_max_chars,
                "summaries_capped_count": run_info.summaries_capped_count,
                "summaries_unchanged_count": run_info.summaries_unchanged_count,
                "max_candidate_count": run_info.max_candidate_count,
                "max_provider_request_body_bytes": run_info.max_provider_request_body_bytes,
            }
        )
    if not succeeded:
        failure_diagnostic = _safe_failure_diagnostic(run_info, request)
        if failure_diagnostic:
            run_payload["failure_diagnostic"] = failure_diagnostic

    staging_dir.mkdir()
    try:
        _write_json(staging_dir / "run.json", run_payload)

        request_path: Path | None = None
        if serialized_request is not None:
            request_path = staging_dir / "request.json"
            request_path.write_bytes(serialized_request)

        trace_path = staging_dir / "trace.json"
        _write_json(trace_path, safe_trace_records)

        response_path: Path | None = None
        if succeeded and validated_response is not None:
            response_path = staging_dir / "response.json"
            _write_json(response_path, _serialize_response(validated_response))

        review_path = staging_dir / "review.md"
        review_path.write_text(
            _render_review(
                report_date=report_date,
                run_id=resolved_run_id,
                request=request,
                response=validated_response if succeeded else None,
                trace_records=safe_trace_records,
                run_info=run_info,
            ),
            encoding="utf-8",
        )

        _verify_staged_artifacts(
            staging_dir,
            run_payload=run_payload,
            succeeded=succeeded,
            request_present=request is not None,
        )
        os.replace(staging_dir, run_dir)
    except Exception:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        raise

    return ShadowArtifactPaths(
        run_dir=run_dir,
        run_json=run_dir / "run.json",
        request_json=run_dir / "request.json" if request is not None else None,
        response_json=run_dir / "response.json" if succeeded else None,
        trace_json=run_dir / "trace.json",
        review_md=run_dir / "review.md",
    )


def _validate_run_info(
    *,
    report_date: date,
    request: CuratorRequest | None,
    response: CuratorResponse | None,
    run_info: ShadowRunInfo,
) -> CuratorResponse | None:
    if run_info.status not in {"succeeded", "failed"}:
        raise ValueError("status must be succeeded or failed")
    if run_info.attempts < 0:
        raise ValueError("attempts must be non-negative")
    _input_mode_token(run_info.input_mode)
    for field_name in (
        "original_candidate_count",
        "summary_max_chars",
        "summaries_capped_count",
        "summaries_unchanged_count",
        "max_candidate_count",
        "max_provider_request_body_bytes",
    ):
        field_value = getattr(run_info, field_name)
        if field_value is not None and field_value < 0:
            raise ValueError(f"{field_name} must be non-negative")
    if run_info.original_candidate_count is not None and request is not None:
        if run_info.original_candidate_count != len(request.articles):
            raise ValueError("original_candidate_count does not match request")
    if (
        run_info.summaries_capped_count is not None
        and run_info.summaries_unchanged_count is not None
        and request is not None
        and run_info.summaries_capped_count + run_info.summaries_unchanged_count
        != len(request.articles)
    ):
        raise ValueError("summary projection counts do not match request")
    if run_info.legacy_evaluation not in {"not_evaluated", "keyword_gate_approximation"}:
        raise ValueError("unsupported legacy_evaluation")
    if request is not None and request.report_date != report_date:
        raise ValueError("request report_date does not match artifact report_date")
    if run_info.candidate_window_start and run_info.candidate_window_end:
        if run_info.candidate_window_start > run_info.candidate_window_end:
            raise ValueError("candidate collection window is inverted")
    elif run_info.candidate_window_start or run_info.candidate_window_end:
        raise ValueError("candidate collection window requires both endpoints")
    if run_info.status == "succeeded":
        if request is None or response is None:
            raise ValueError("a succeeded run requires request and response")
        if (
            run_info.failure_stage
            or run_info.failure_code
            or run_info.failure_diagnostic_code
            or run_info.failure_diagnostic_path
            or run_info.failure_diagnostic_article_id
        ):
            raise ValueError("a succeeded run cannot contain failure fields")
        if response.report_date != report_date:
            raise ValueError("response report_date does not match artifact report_date")
        response_payload = _serialize_response(response)
        try:
            validated_response = validate_curator_response(response_payload, request)
            validate_curator_content_policy(validated_response)
        except (CuratorContractError, CuratorContentPolicyError):
            raise
        return validated_response
    elif response is not None:
        raise ValueError("a failed run cannot contain a response artifact")
    return None


def _serialize_response(response: CuratorResponse) -> dict[str, Any]:
    return {
        "schema_version": response.schema_version,
        "report_date": response.report_date.isoformat(),
        "events": [
            {
                "event_id": event.event_id,
                "canonical_title": event.canonical_title,
                "summary": event.summary,
                "category": event.category,
                "importance": event.importance,
                "why_important": event.why_important,
                "evidence_article_ids": list(event.evidence_article_ids),
                "novelty": event.novelty,
                "confidence": event.confidence,
                "uncertainties": list(event.uncertainties),
            }
            for event in response.events
        ],
        "rejected_article_ids": [
            {
                "article_id": item.article_id,
                "reject_reason": item.reject_reason,
            }
            for item in response.rejected_article_ids
        ],
        "warnings": list(response.warnings),
    }


def _safe_trace_records(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    safe_records: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise ValueError("trace record must be an object")
        trace_type = str(record.get("trace_type") or "candidate")
        if trace_type == "candidate":
            safe_records.append(_safe_candidate_trace(record))
        elif trace_type == "fetch_failures":
            safe_records.append(_safe_fetch_failure_trace(record))
        else:
            raise ValueError("unsupported trace_type")
    return safe_records


def _safe_candidate_trace(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "trace_type": "candidate",
        "article_id": str(record.get("article_id", "")),
        "title": str(record.get("title", "")),
        "source": str(record.get("source", "")),
        "feed_name": str(record.get("feed_name", "")),
        "feed_role": str(record.get("feed_role", "")),
        "published_at": str(record.get("published_at", "")),
        "link": str(record.get("link", "")),
        "normalized_link": str(record.get("normalized_link", "")),
        "report_date": str(record.get("report_date", "")),
        "legacy_keyword_matched": bool(record.get("legacy_keyword_matched")),
        "legacy_matched_keywords": _safe_keywords(record.get("legacy_matched_keywords")),
        "legacy_selected": bool(record.get("legacy_selected")),
        "legacy_score": None,
        "legacy_category": "",
        "legacy_reject_reason": str(record.get("legacy_reject_reason", "")),
    }


def _safe_fetch_failure_trace(record: Mapping[str, Any]) -> dict[str, Any]:
    raw_failures = record.get("candidate_failures")
    if not isinstance(raw_failures, (list, tuple)):
        raise ValueError("fetch_failures trace requires candidate_failures list")
    failures: list[dict[str, str]] = []
    for failure in raw_failures:
        if isinstance(failure, Mapping):
            feed_name = failure.get("feed_name", "")
            raw_error = failure.get("failure_code", failure.get("error", ""))
        elif isinstance(failure, (list, tuple)) and len(failure) >= 2:
            feed_name, raw_error = failure[0], failure[1]
        else:
            raise ValueError("fetch failure must contain feed name and error")
        failures.append(
            {
                "feed_name": _safe_trace_text(feed_name),
                "failure_code": _classify_failure_code(raw_error),
            }
        )
    return {"trace_type": "fetch_failures", "candidate_failures": failures}


def _classify_failure_code(value: Any) -> str:
    text = str(value or "").lower()
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if any(term in text for term in ("parse", "json", "xml", "bozo")):
        return "parse_error"
    if any(term in text for term in ("http", "url", "network", "connection", "connect")):
        return "network_error"
    return "unknown_failure"


def _safe_trace_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())[:256]


def _safe_keywords(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, Mapping):
        return {}
    output: dict[str, list[str]] = {}
    for key, raw_values in value.items():
        if isinstance(raw_values, (list, tuple)):
            output[str(key)] = [str(item) for item in raw_values]
    return output


def _legacy_evaluation_token(value: str) -> str:
    if value not in {"not_evaluated", "keyword_gate_approximation"}:
        raise ValueError("unsupported legacy_evaluation")
    return value


def _verify_staged_artifacts(
    staging_dir: Path,
    *,
    run_payload: Mapping[str, Any],
    succeeded: bool,
    request_present: bool,
) -> None:
    expected = {"run.json", "trace.json", "review.md"}
    if request_present:
        expected.add("request.json")
    if succeeded:
        expected.add("response.json")
    actual = {path.name for path in staging_dir.iterdir()}
    if actual != expected:
        raise OSError("shadow artifact integrity check failed")
    stored_run = json.loads((staging_dir / "run.json").read_text(encoding="utf-8"))
    if stored_run != dict(run_payload):
        raise OSError("shadow run metadata integrity check failed")
    if request_present:
        request_bytes = (staging_dir / "request.json").read_bytes()
        if len(request_bytes) != run_payload["curator_request_bytes"]:
            raise OSError("curator request byte measurement integrity check failed")
        json.loads(request_bytes.decode("utf-8"))
    trace_payload = json.loads((staging_dir / "trace.json").read_text(encoding="utf-8"))
    if not isinstance(trace_payload, list):
        raise OSError("trace artifact integrity check failed")
    if succeeded:
        response_payload = json.loads((staging_dir / "response.json").read_text(encoding="utf-8"))
        if not isinstance(response_payload, dict):
            raise OSError("response artifact integrity check failed")
    if not (staging_dir / "review.md").read_bytes():
        raise OSError("review artifact integrity check failed")


def _render_review(
    *,
    report_date: date,
    run_id: str,
    request: CuratorRequest | None,
    response: CuratorResponse | None,
    trace_records: Sequence[Mapping[str, Any]],
    run_info: ShadowRunInfo,
) -> str:
    curator_request_bytes = (
        len(serialize_curator_request(request)) if request is not None else None
    )
    if run_info.curator_request_bytes is not None:
        curator_request_bytes = run_info.curator_request_bytes
    lines = [
        "# AI Curator Shadow Review",
        "",
        f"- Report date: `{report_date.isoformat()}`",
        f"- Run ID: `{run_id}`",
        f"- Status: `{run_info.status}`",
        f"- Provider: `{_review_text(_metadata_text(run_info.provider_id))}` / `{_review_text(_metadata_text(run_info.model))}`",
        f"- Attempts: `{run_info.attempts}`",
        f"- Validation: `{_safe_token(run_info.validation_status)}`",
        f"- Candidate count: `{len(request.articles) if request is not None else 0}`",
        f"- Curator request bytes: `{_review_text(str(curator_request_bytes)) if curator_request_bytes is not None else 'not applicable'}`",
        f"- Provider request body bytes: `{run_info.provider_request_body_bytes if run_info.provider_request_body_bytes is not None else 'not applicable'}`",
    ]
    if run_info.input_mode:
        lines.append(f"- Input mode: `{_safe_token(run_info.input_mode)}`")
        if run_info.original_candidate_count is not None:
            lines.append(f"- Original candidate count: `{run_info.original_candidate_count}`")
        if run_info.summary_max_chars is not None:
            lines.append(f"- Provider summary cap: `{run_info.summary_max_chars}`")
        if run_info.summaries_capped_count is not None:
            lines.append(f"- Summaries capped: `{run_info.summaries_capped_count}`")
        if run_info.summaries_unchanged_count is not None:
            lines.append(f"- Summaries unchanged: `{run_info.summaries_unchanged_count}`")
        if run_info.max_candidate_count is not None:
            lines.append(f"- Max candidate count: `{run_info.max_candidate_count}`")
        if run_info.max_provider_request_body_bytes is not None:
            lines.append(
                "- Max provider request body bytes: "
                f"`{run_info.max_provider_request_body_bytes}`"
            )
    if run_info.candidate_window_start and run_info.candidate_window_end:
        lines.append(
            "- Candidate collection window: "
            f"`{_datetime_text(run_info.candidate_window_start)}` to "
            f"`{_datetime_text(run_info.candidate_window_end)}`"
        )
    else:
        lines.append("- Candidate collection window: `not applicable`")
    if run_info.failure_stage or run_info.failure_code:
        lines.extend(
            [
                f"- Failure stage: `{_safe_token(run_info.failure_stage)}`",
                f"- Failure code: `{_safe_token(run_info.failure_code)}`",
            ]
        )
    failure_diagnostic = _safe_failure_diagnostic(run_info, request)
    if failure_diagnostic:
        diagnostic_text = [f"code=`{failure_diagnostic['code']}`"]
        if "path" in failure_diagnostic:
            diagnostic_text.append(f"path=`{failure_diagnostic['path']}`")
        if "article_id" in failure_diagnostic:
            diagnostic_text.append(f"article_id=`{failure_diagnostic['article_id']}`")
        lines.append(f"- Failure diagnostic: {'; '.join(diagnostic_text)}")

    if response is not None and request is not None:
        article_by_id = {article.article_id: article for article in request.articles}
        lines.extend(["", "## AI Events", ""])
        if response.events:
            for event in response.events:
                evidence = ", ".join(event.evidence_article_ids)
                evidence_sources = "; ".join(
                    f"{_review_text(article_by_id[article_id].source)} — "
                    f"{_review_text(article_by_id[article_id].title)}"
                    for article_id in event.evidence_article_ids
                    if article_id in article_by_id
                )
                lines.extend(
                    [
                        f"### {_review_text(event.canonical_title)}",
                        "",
                        f"- Summary: {_review_text(event.summary)}",
                        f"- Why important: {_review_text(event.why_important)}",
                        f"- Importance: `{event.importance}`; category: `{event.category}`; confidence: `{event.confidence}`",
                        f"- Evidence: `{_review_text(evidence)}`",
                        f"- Evidence sources: {_review_text(evidence_sources)}",
                    ]
                )
                if event.uncertainties:
                    lines.append(f"- Uncertainties: {_review_text('; '.join(event.uncertainties))}")
                lines.append("")
        else:
            lines.extend(["No AI events returned.", ""])

        lines.extend(["## Rejected Articles", ""])
        rejected_by_id = {item.article_id: item for item in response.rejected_article_ids}
        if rejected_by_id:
            for article_id, rejected in rejected_by_id.items():
                article = article_by_id.get(article_id)
                title = article.title if article is not None else article_id
                lines.append(f"- {_review_text(title)} — `{rejected.reject_reason}`")
        else:
            lines.append("No AI-rejected articles returned.")
        lines.append("")
    else:
        lines.extend(["", "## Result", "", "No validated AI response was written.", ""])

    selected = [
        _review_text(str(record.get("title", record.get("article_id", ""))))
        for record in trace_records
        if record.get("trace_type") == "candidate" and bool(record.get("legacy_selected"))
    ]
    if run_info.legacy_evaluation == "not_evaluated":
        legacy_label = "not evaluated"
    else:
        legacy_label = "keyword-gate approximation"
    lines.extend(["## Legacy Comparison", "", f"- Legacy comparison: `{legacy_label}`"])
    if run_info.legacy_evaluation == "not_evaluated":
        lines.append("- Legacy selection was not evaluated for this fixture run.")
    else:
        lines.append("- This is not the final production digest selection.")
    lines.append(f"- Legacy-selected candidate count: `{len(selected)}`")
    if selected:
        lines.extend(["", "### Legacy Selected Candidates", ""])
        lines.extend(f"- {title}" for title in selected)
    else:
        lines.append("- No legacy-selected candidates.")
    lines.extend(
        [
            "",
            "## Human Review",
            "",
            "- [ ] AI event grouping and canonical titles are factually supported.",
            "- [ ] Importance and novelty labels are appropriate.",
            "- [ ] Evidence article ids point to the intended candidate articles.",
            "- [ ] Rejected articles and rejection reasons are reasonable.",
            "- [ ] No investment advice or unsupported claims should enter production.",
            "",
        ]
    )
    return "\n".join(lines)


def _review_text(value: str) -> str:
    cleaned = " ".join(str(value).replace("\r", " ").replace("\n", " ").split())
    escaped_html = html.escape(cleaned, quote=True)
    for character in ("\\", "`", "*", "_", "[", "]", "(", ")", "#", "!", ">", "|", "~"):
        escaped_html = escaped_html.replace(character, f"\\{character}")
    return escaped_html


def _safe_token(value: str) -> str:
    text = str(value or "")
    if not _SAFE_TOKEN_PATTERN.fullmatch(text):
        return "redacted"
    return text


def _input_mode_token(value: str) -> str:
    if value not in {"", "full", "phase3b_fixture", "phase4_live"}:
        raise ValueError("unsupported input_mode")
    return value


def _safe_failure_diagnostic(
    run_info: ShadowRunInfo,
    request: CuratorRequest | None,
) -> dict[str, str]:
    """Serialize only bounded rule/path metadata from a failed validation."""

    diagnostic: dict[str, str] = {}
    code = _safe_diagnostic_token(run_info.failure_diagnostic_code)
    path = _safe_diagnostic_token(run_info.failure_diagnostic_path)
    if code:
        diagnostic["code"] = code
    if path:
        diagnostic["path"] = path

    article_id = str(run_info.failure_diagnostic_article_id or "")
    known_article_ids = (
        {article.article_id for article in request.articles} if request is not None else set()
    )
    if article_id in known_article_ids:
        safe_article_id = _safe_diagnostic_token(article_id)
        if safe_article_id:
            diagnostic["article_id"] = safe_article_id
    return diagnostic


def _safe_diagnostic_token(value: str) -> str:
    text = str(value or "")
    if len(text) > 128 or not _SAFE_TOKEN_PATTERN.fullmatch(text):
        return "redacted" if text else ""
    return text


def _metadata_text(value: str) -> str:
    text = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())
    return text[:256]


def _datetime_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_json(path: Path, payload: Any) -> None:
    path.write_bytes(_json_bytes(payload))
