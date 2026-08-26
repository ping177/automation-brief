#!/usr/bin/env python3
"""Explicit real-model v1.3 threshold evaluation.

This command is intentionally separate from the offline smoke suite.  It
requires a pinned local model revision and never fetches RSS or calls a
provider.  Results are printed as JSON and are not persisted automatically.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from canonical_domain import Article  # noqa: E402
from event_cluster import (  # noqa: E402
    ALGORITHM_VERSION,
    DEFAULT_THRESHOLD,
    MODEL_ID,
    MODEL_REVISION,
    PROJECTION_VERSION,
    SUMMARY_CHAR_LIMIT,
    SentenceTransformerEmbedder,
    cluster_articles,
    project_article,
)
from project_paths import get_project_paths  # noqa: E402


FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "event_clustering_v1_3.json"
MODEL_CACHE_ENV = "AUTOMATION_BRIEF_MODEL_CACHE"
EVAL_TIME = datetime(2026, 8, 26, 8, 0, tzinfo=timezone.utc)
METRIC_KEYS = (
    "true_positive",
    "false_positive",
    "false_negative",
    "true_negative",
    "overmerge_count",
    "split_count",
    "exact_membership_matches",
    "expected_cluster_count",
    "predicted_cluster_count",
)


class CachedEmbedder:
    def __init__(self, vectors: Mapping[str, Sequence[float]]) -> None:
        self._vectors = vectors

    def embed(self, text: str) -> Sequence[float]:
        return self._vectors[text]


def _load_fixture(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    cases = payload.get("cases") if isinstance(payload, Mapping) else None
    if not isinstance(cases, list) or not cases:
        raise ValueError("fixture must contain a non-empty cases array")
    allowed_classes = {
        "production-relevant",
        "robustness-only",
        "outside-normal-window",
    }
    allowed_relevance = {
        "production-realistic",
        "synthetic",
        "outside-normal-window",
    }
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("fixture case must be an object")
        if case.get("provenance") == "repository-supported":
            raise ValueError("fixture provenance must be explicit")
        if case.get("acceptance_class") not in allowed_classes:
            raise ValueError("fixture acceptance_class is invalid")
        if case.get("window_relevance") not in allowed_relevance:
            raise ValueError("fixture window_relevance is invalid")
    return cases


def _article(case_id: str, raw: Mapping[str, Any]) -> Article:
    key = raw.get("key")
    title = raw.get("title")
    summary = raw.get("summary")
    language = raw.get("language", "und")
    if not all(isinstance(value, str) and value for value in (key, title, language)):
        raise ValueError("fixture article requires key, title and language")
    if summary is not None and not isinstance(summary, str):
        raise ValueError("fixture summary must be a string or null")
    return Article.from_source(
        source=f"Fixture:{case_id}",
        url=f"https://fixture.example/v1-3/{case_id}/{key}",
        published_at=EVAL_TIME,
        collected_at=EVAL_TIME,
        language=language,
        title=title,
        summary=summary,
    )


def _case_articles(case: Mapping[str, Any]) -> tuple[list[Article], dict[str, Article]]:
    case_id = case.get("case_id")
    raw_articles = case.get("articles")
    if not isinstance(case_id, str) or not isinstance(raw_articles, list) or not raw_articles:
        raise ValueError("fixture case requires case_id and non-empty articles")
    by_key: dict[str, Article] = {}
    for raw in raw_articles:
        if not isinstance(raw, Mapping):
            raise ValueError("fixture article must be an object")
        key = raw.get("key")
        if not isinstance(key, str) or key in by_key:
            raise ValueError("fixture article keys must be unique strings")
        by_key[key] = _article(case_id, raw)
    return list(by_key.values()), by_key


def _expected_labels(case: Mapping[str, Any], by_key: Mapping[str, Article]) -> dict[str, int]:
    raw_clusters = case.get("expected_clusters")
    if not isinstance(raw_clusters, list):
        raise ValueError("fixture case requires expected_clusters")
    labels: dict[str, int] = {}
    for cluster_index, raw_cluster in enumerate(raw_clusters):
        if not isinstance(raw_cluster, list) or not raw_cluster:
            raise ValueError("expected cluster must be a non-empty array")
        for key in raw_cluster:
            if not isinstance(key, str) or key not in by_key or key in labels:
                raise ValueError("expected cluster references must be unique known keys")
            labels[key] = cluster_index
    if set(labels) != set(by_key):
        raise ValueError("expected clusters must cover every fixture article")
    return labels


def _pair_metrics(
    articles: Sequence[Article],
    by_key: Mapping[str, Article],
    expected_labels: Mapping[str, int],
    predicted: Sequence[Any],
) -> dict[str, float | int]:
    key_by_article_id = {article.article_id: key for key, article in by_key.items()}
    key_by_object_id = {id(article): key for key, article in by_key.items()}
    predicted_labels: dict[str, int] = {}
    for cluster_index, candidate in enumerate(predicted):
        for article_id in candidate.article_ids:
            predicted_labels[key_by_article_id[article_id]] = cluster_index

    true_positive = false_positive = false_negative = true_negative = 0
    for left_index, left in enumerate(articles):
        for right in articles[left_index + 1 :]:
            left_key = key_by_object_id[id(left)]
            right_key = key_by_object_id[id(right)]
            expected_same = expected_labels[left_key] == expected_labels[right_key]
            predicted_same = predicted_labels[left_key] == predicted_labels[right_key]
            if expected_same and predicted_same:
                true_positive += 1
            elif not expected_same and predicted_same:
                false_positive += 1
            elif expected_same and not predicted_same:
                false_negative += 1
            else:
                true_negative += 1

    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 1.0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 1.0
    )
    beta_squared = 0.25
    f05 = (
        (1 + beta_squared) * precision * recall / (beta_squared * precision + recall)
        if precision + recall
        else 0.0
    )

    overmerges = 0
    for candidate in predicted:
        labels = {
            expected_labels[key_by_article_id[article_id]]
            for article_id in candidate.article_ids
        }
        if len(labels) > 1:
            overmerges += 1

    splits = 0
    for expected_cluster_index in set(expected_labels.values()):
        predicted_cluster_ids = {
            predicted_labels[key]
            for key, label in expected_labels.items()
            if label == expected_cluster_index
        }
        if len(predicted_cluster_ids) > 1:
            splits += 1

    expected_memberships = {
        frozenset(key for key, label in expected_labels.items() if label == cluster_index)
        for cluster_index in set(expected_labels.values())
    }
    predicted_memberships = {
        frozenset(
            key_by_article_id[article_id] for article_id in candidate.article_ids
        )
        for candidate in predicted
    }
    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
        "precision": precision,
        "recall": recall,
        "f0_5": f05,
        "overmerge_count": overmerges,
        "split_count": splits,
        "exact_membership_matches": len(expected_memberships & predicted_memberships),
        "expected_cluster_count": len(expected_memberships),
        "predicted_cluster_count": len(predicted_memberships),
    }


def _memberships(
    predicted: Sequence[Any],
    by_key: Mapping[str, Article],
) -> list[list[str]]:
    key_by_article_id = {article.article_id: key for key, article in by_key.items()}
    groups = [
        sorted(key_by_article_id[article_id] for article_id in candidate.article_ids)
        for candidate in predicted
    ]
    return sorted(groups, key=lambda group: (group[0], len(group), group))


def _expected_memberships(case: Mapping[str, Any]) -> list[list[str]]:
    raw_clusters = case.get("expected_clusters")
    if not isinstance(raw_clusters, list):
        return []
    return [sorted(cluster) for cluster in raw_clusters if isinstance(cluster, list)]


def _acceptance_summary(case_results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    production_cases = [
        case for case in case_results if case.get("acceptance_class") == "production-relevant"
    ]
    robustness_cases = [
        case for case in case_results if case.get("acceptance_class") == "robustness-only"
    ]
    outside_window_cases = [
        case for case in case_results if case.get("acceptance_class") == "outside-normal-window"
    ]
    production_counts = {
        key: 0
        for key in ("true_positive", "false_positive", "false_negative", "true_negative")
    }
    production_overmerge = production_split = 0
    production_exact = production_expected = 0
    for case in production_cases:
        metrics = case["metrics"]
        for key in production_counts:
            production_counts[key] += int(metrics[key])
        production_overmerge += int(metrics["overmerge_count"])
        production_split += int(metrics["split_count"])
        production_exact += int(metrics["exact_membership_matches"])
        production_expected += int(metrics["expected_cluster_count"])

    true_positive = production_counts["true_positive"]
    false_positive = production_counts["false_positive"]
    false_negative = production_counts["false_negative"]
    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 1.0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 1.0
    )
    f05 = (
        1.25 * precision * recall / (0.25 * precision + recall)
        if precision + recall
        else 0.0
    )

    def _failed_case_ids(cases: Sequence[Mapping[str, Any]]) -> list[str]:
        return [
            str(case["case_id"])
            for case in cases
            if case["metrics"]["overmerge_count"]
            or case["metrics"]["split_count"]
            or case["metrics"]["exact_membership_matches"]
            != case["metrics"]["expected_cluster_count"]
        ]

    return {
        **production_counts,
        "production_case_count": len(production_cases),
        "production_critical_overmerge": production_overmerge,
        "production_critical_split": production_split,
        "production_exact_membership_matches": production_exact,
        "production_expected_cluster_count": production_expected,
        "production_precision": precision,
        "production_recall": recall,
        "production_f0_5": f05,
        "production_pass": bool(
            production_cases
            and production_overmerge == 0
            and production_split == 0
            and production_exact == production_expected
        ),
        "robustness_only_failures": _failed_case_ids(robustness_cases),
        "outside_window_observations": _failed_case_ids(outside_window_cases),
    }


def _default_cache_folder() -> str:
    configured = os.environ.get(MODEL_CACHE_ENV, "").strip()
    if configured:
        return configured
    return str(get_project_paths(repo_root=PROJECT_ROOT).runs_dir / "model-cache")


def _new_aggregate() -> dict[str, int]:
    return {key: 0 for key in METRIC_KEYS}


def _summary_metrics(aggregate: Mapping[str, int]) -> dict[str, float | int]:
    true_positive = aggregate["true_positive"]
    false_positive = aggregate["false_positive"]
    false_negative = aggregate["false_negative"]
    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 1.0
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 1.0
    )
    f05 = (
        1.25 * precision * recall / (0.25 * precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        **aggregate,
        "precision": precision,
        "recall": recall,
        "f0_5": f05,
    }


def _percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int((len(ordered) - 1) * fraction))
    return ordered[index]


def _similarity_distribution(
    cases: Sequence[tuple[list[Article], Mapping[str, Article]]],
    vectors: Mapping[str, Sequence[float]],
) -> dict[str, float | int | None]:
    values: list[float] = []
    for articles, _ in cases:
        for left_index, left in enumerate(articles):
            for right in articles[left_index + 1 :]:
                left_vector = vectors[project_article(left)]
                right_vector = vectors[project_article(right)]
                values.append(sum(a * b for a, b in zip(left_vector, right_vector)))
    return {
        "pair_count": len(values),
        "min": min(values) if values else None,
        "p50": _percentile(values, 0.50),
        "p90": _percentile(values, 0.90),
        "max": max(values) if values else None,
    }


def _thresholds(args: argparse.Namespace) -> list[float]:
    if args.thresholds:
        try:
            values = [
                float(value.strip())
                for value in args.thresholds.split(",")
                if value.strip()
            ]
        except ValueError as error:
            raise ValueError("thresholds must be numeric") from error
    else:
        if (
            not math.isfinite(args.threshold_start)
            or not math.isfinite(args.threshold_stop)
            or not -1 <= args.threshold_start <= 1
            or not -1 <= args.threshold_stop <= 1
            or not math.isfinite(args.threshold_step)
            or args.threshold_step <= 0
        ):
            raise ValueError("threshold range must be finite and within [-1, 1]")
        values = []
        current = args.threshold_start
        while current <= args.threshold_stop + 1e-12:
            values.append(round(current, 6))
            current += args.threshold_step
    if (
        not values
        or len(values) > 1000
        or any(not math.isfinite(value) or not -1 <= value <= 1 for value in values)
    ):
        raise ValueError("thresholds must be finite values in [-1, 1]")
    return values


def _evaluate_threshold(
    threshold: float,
    cases: Sequence[
        tuple[
            Mapping[str, Any],
            list[Article],
            Mapping[str, Article],
            Mapping[str, int],
        ]
    ],
    vectors: Mapping[str, Sequence[float]],
) -> dict[str, Any]:
    embedder = CachedEmbedder(vectors)
    aggregate = _new_aggregate()
    split_aggregates: dict[str, dict[str, int]] = {}
    case_results = []
    for case, articles, by_key, expected_labels in cases:
        result = cluster_articles(
            articles,
            embedder_factory=lambda: embedder,
            threshold=threshold,
        )
        metrics = _pair_metrics(articles, by_key, expected_labels, result.outputs)
        for key in METRIC_KEYS:
            aggregate[key] += int(metrics[key])
        split = case.get("split", "calibration")
        if not isinstance(split, str):
            split = "calibration"
        split_aggregate = split_aggregates.setdefault(split, _new_aggregate())
        for key in METRIC_KEYS:
            split_aggregate[key] += int(metrics[key])
        case_results.append(
            {
                "case_id": case["case_id"],
                "split": split,
                "acceptance_class": case.get("acceptance_class", "unspecified"),
                "window_relevance": case.get("window_relevance", "unspecified"),
                "status": result.status.value,
                "failure_count": len(result.failures),
                "expected_memberships": _expected_memberships(case),
                "actual_memberships": _memberships(result.outputs, by_key),
                "metrics": metrics,
            }
        )
    return {
        "threshold": threshold,
        **_summary_metrics(aggregate),
        "split_results": {
            split: _summary_metrics(values)
            for split, values in sorted(split_aggregates.items())
        },
        "acceptance": _acceptance_summary(case_results),
        "cases": case_results,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    parser.add_argument("--model-revision", default=MODEL_REVISION)
    parser.add_argument("--cache-folder", type=str, default=_default_cache_folder())
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--thresholds", help="comma-separated values; overrides start/stop/step")
    parser.add_argument("--threshold-start", type=float, default=0.70)
    parser.add_argument("--threshold-stop", type=float, default=0.95)
    parser.add_argument("--threshold-step", type=float, default=0.02)
    parser.add_argument("--accepted-threshold", type=float, default=DEFAULT_THRESHOLD)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        raw_cases = _load_fixture(args.fixture)
        threshold_values = _thresholds(args)
        if args.model_revision != MODEL_REVISION:
            raise ValueError("v1.3 accepted model revision is fixed")
        if not math.isfinite(args.accepted_threshold) or not -1 <= args.accepted_threshold <= 1:
            raise ValueError("accepted threshold must be finite and within [-1, 1]")
        if args.accepted_threshold not in threshold_values:
            threshold_values = [*threshold_values, args.accepted_threshold]
            threshold_values.sort()
        prepared_cases = []
        all_articles: list[Article] = []
        for case in raw_cases:
            split = case.get("split", "calibration")
            if split not in {"calibration", "held_out"}:
                raise ValueError("fixture split must be calibration or held_out")
            articles, by_key = _case_articles(case)
            labels = _expected_labels(case, by_key)
            prepared_cases.append((case, articles, by_key, labels))
            all_articles.extend(articles)

        initialization_started = time.perf_counter()
        embedder = SentenceTransformerEmbedder(
            model_revision=args.model_revision,
            cache_folder=args.cache_folder,
            local_files_only=args.local_files_only,
        )
        initialization_ms = (time.perf_counter() - initialization_started) * 1000
        vectors: dict[str, tuple[float, ...]] = {}
        embedding_started = time.perf_counter()
        for item in all_articles:
            projection = project_article(item)
            vector = embedder.embed(projection)
            norm = math.sqrt(sum(float(value) * float(value) for value in vector))
            if not math.isfinite(norm) or norm == 0:
                raise ValueError("model returned an invalid vector")
            vectors[projection] = tuple(float(value) / norm for value in vector)
        embedding_ms = (time.perf_counter() - embedding_started) * 1000
        results = [
            _evaluate_threshold(value, prepared_cases, vectors)
            for value in threshold_values
        ]
        accepted = next(
            item for item in results if item["threshold"] == args.accepted_threshold
        )
        repeat_a = _evaluate_threshold(args.accepted_threshold, prepared_cases, vectors)
        repeat_b = _evaluate_threshold(args.accepted_threshold, prepared_cases, vectors)
        embedding_dimensions = len(next(iter(vectors.values()))) if vectors else 0
        if embedding_dimensions != 384:
            raise ValueError("accepted E5-small model must emit 384-dimensional vectors")
        print(
            json.dumps(
                {
                    "model_id": embedder.model_id,
                    "model_revision": embedder.model_revision,
                    "projection_version": PROJECTION_VERSION,
                    "summary_cap": SUMMARY_CHAR_LIMIT,
                    "algorithm_version": ALGORITHM_VERSION,
                    "device": embedder.device,
                    "dtype": embedder.dtype,
                    "accepted_threshold": args.accepted_threshold,
                    "article_count": len(all_articles),
                    "embedding_dimensions": embedding_dimensions,
                    "timing_ms": {
                        "initialization": round(initialization_ms, 3),
                        "embedding": round(embedding_ms, 3),
                    },
                    "similarity_distribution": _similarity_distribution(
                        [(articles, by_key) for _, articles, by_key, _ in prepared_cases],
                        vectors,
                    ),
                    "threshold_results": results,
                    "accepted_candidate": accepted,
                    "deterministic_repeat": repeat_a == repeat_b,
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
        )
    except Exception as error:
        raise SystemExit(f"event clustering evaluation failed: {type(error).__name__}") from error


if __name__ == "__main__":
    main()
