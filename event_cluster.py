"""Deterministic v1.3 semantic clustering from Articles to EventCandidates.

The module keeps the embedding boundary injectable so the normal offline suite
does not import, initialize, or download a model runtime.
"""

from __future__ import annotations

import math
import re
import time
import unicodedata
from typing import Any, Callable, Iterable, Mapping, Optional, Protocol, Sequence

from canonical_domain import (
    Article,
    EventCandidate,
    FailureCode,
    ItemFailure,
    StageName,
    StageResult,
    StageStatus,
)


MODEL_ID = "intfloat/multilingual-e5-small"
MODEL_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
PROJECTION_VERSION = "article-title-summary-v1"
SUMMARY_CHAR_LIMIT = 300
ALGORITHM_VERSION = "identity-guarded-connected-components-v2"
EDGE_POLICY_VERSION = "semantic-title-anchor-v1"
DEFAULT_THRESHOLD = 0.91
HIGH_CONFIDENCE_THRESHOLD = 0.925
MIN_TITLE_IDENTITY_SPAN = 4
NEAR_THRESHOLD_BAND = 0.03
MAX_DIAGNOSTIC_EDGES = 256
IMMUTABLE_REVISION_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class EmbeddingBackend(Protocol):
    """Minimal local embedding boundary owned by the clustering stage."""

    def embed(self, text: str) -> Sequence[float]:
        ...


SimilarityFunction = Callable[[Sequence[float], Sequence[float]], float]
DiagnosticSink = Callable[[Mapping[str, Any]], Optional[str]]


def project_article(article: Article) -> str:
    """Build the sole versioned text representation sent to the embedder."""

    projection = f"query: {article.title}"
    if article.summary is not None and article.summary.strip():
        projection += f"\n{article.summary[:SUMMARY_CHAR_LIMIT]}"
    return projection


def normalize_title_for_edge_policy(title: str) -> str:
    """Normalize a title to Unicode alphanumeric identity text."""

    if not isinstance(title, str):
        raise ValueError("title must be text")
    normalized = unicodedata.normalize("NFKC", title).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _normalized_titles_share_identity_span(first: str, second: str) -> bool:
    if len(first) < MIN_TITLE_IDENTITY_SPAN or len(second) < MIN_TITLE_IDENTITY_SPAN:
        return False
    first_spans = {
        first[index : index + MIN_TITLE_IDENTITY_SPAN]
        for index in range(len(first) - MIN_TITLE_IDENTITY_SPAN + 1)
    }
    return any(
        second[index : index + MIN_TITLE_IDENTITY_SPAN] in first_spans
        for index in range(len(second) - MIN_TITLE_IDENTITY_SPAN + 1)
    )


def _accept_edge(
    first_title: str,
    second_title: str,
    similarity: float,
    threshold: float,
) -> bool:
    if similarity >= max(threshold, HIGH_CONFIDENCE_THRESHOLD):
        return True
    return similarity >= threshold and _normalized_titles_share_identity_span(
        first_title,
        second_title,
    )


def _edge_policy_metadata(threshold: float) -> dict[str, str | int | float]:
    return {
        "edge_policy_version": EDGE_POLICY_VERSION,
        "base_similarity_floor": threshold,
        "high_confidence_threshold": HIGH_CONFIDENCE_THRESHOLD,
        "title_identity_min_span": MIN_TITLE_IDENTITY_SPAN,
    }


def _failure_sort_key(failure: ItemFailure) -> tuple[int, str, str]:
    return (
        1 if failure.item_id is None else 0,
        failure.item_id or "",
        failure.code.value,
    )


def _result(
    outputs: Sequence[EventCandidate],
    failures: Sequence[ItemFailure],
    diagnostic_ref: str | None = None,
) -> StageResult[EventCandidate]:
    ordered_outputs = tuple(outputs)
    ordered_failures = tuple(sorted(failures, key=_failure_sort_key))
    if ordered_failures and ordered_outputs:
        status = StageStatus.PARTIAL
    elif ordered_failures:
        status = StageStatus.FAILED
    else:
        status = StageStatus.SUCCEEDED
    return StageResult(
        stage=StageName.EVENT_CLUSTER,
        status=status,
        outputs=ordered_outputs,
        failures=ordered_failures,
        diagnostic_ref=diagnostic_ref,
    )


def _invalid_input() -> StageResult[EventCandidate]:
    return _result((), (ItemFailure(code=FailureCode.INVALID_INPUT),))


def _local_model_failure(item_id: str | None = None) -> ItemFailure:
    return ItemFailure(item_id=item_id, code=FailureCode.LOCAL_MODEL_FAILED)


def _cosine_similarity(first: Sequence[float], second: Sequence[float]) -> float:
    return sum(left * right for left, right in zip(first, second))


def _normalize_vector(vector: Sequence[float]) -> tuple[float, ...]:
    if isinstance(vector, (str, bytes)):
        raise ValueError("embedding must be a numeric sequence")
    values = tuple(float(value) for value in vector)
    if not values or any(not math.isfinite(value) for value in values):
        raise ValueError("embedding must contain finite values")
    norm = math.sqrt(sum(value * value for value in values))
    if not math.isfinite(norm) or norm == 0.0:
        raise ValueError("embedding norm must be finite and non-zero")
    return tuple(value / norm for value in values)


def _components(
    articles: Sequence[Article],
    vectors: Sequence[Sequence[float]],
    threshold: float,
    similarity_function: SimilarityFunction,
) -> tuple[
    tuple[EventCandidate, ...],
    list[tuple[str, str, float]],
    list[tuple[str, str, float]],
]:
    parent = list(range(len(articles)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        if left_root < right_root:
            parent[right_root] = left_root
        else:
            parent[left_root] = right_root

    accepted_edges: list[tuple[str, str, float]] = []
    near_threshold_rejected: list[tuple[str, str, float]] = []
    normalized_titles = tuple(
        normalize_title_for_edge_policy(article.title) for article in articles
    )
    for left in range(len(articles)):
        for right in range(left + 1, len(articles)):
            similarity = float(similarity_function(vectors[left], vectors[right]))
            if not math.isfinite(similarity):
                raise ValueError("similarity must be finite")
            if _accept_edge(
                normalized_titles[left],
                normalized_titles[right],
                similarity,
                threshold,
            ):
                union(left, right)
                accepted_edges.append(
                    (articles[left].article_id, articles[right].article_id, similarity)
                )
            elif abs(similarity - threshold) <= NEAR_THRESHOLD_BAND:
                near_threshold_rejected.append(
                    (articles[left].article_id, articles[right].article_id, similarity)
                )

    groups: dict[int, list[str]] = {}
    for index, article in enumerate(articles):
        groups.setdefault(find(index), []).append(article.article_id)
    candidates = tuple(
        sorted(
            (EventCandidate.from_article_ids(article_ids) for article_ids in groups.values()),
            key=lambda candidate: candidate.event_candidate_id,
        )
    )
    return candidates, accepted_edges, near_threshold_rejected


def _safe_diagnostic_value(value: Any) -> str | int | float | bool | None:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return None


def _backend_metadata(embedder: Any) -> dict[str, str | int | float | bool | None]:
    metadata = getattr(embedder, "diagnostic_metadata", None)
    if callable(metadata):
        try:
            metadata = metadata()
        except Exception:
            return {}
    if not isinstance(metadata, Mapping):
        return {}
    return {
        str(key): _safe_diagnostic_value(value)
        for key, value in metadata.items()
        if isinstance(key, str)
    }


def _emit_diagnostics(
    sink: DiagnosticSink | None,
    payload: Mapping[str, Any],
) -> str | None:
    if sink is None:
        return None
    try:
        reference = sink(payload)
    except Exception:
        return None
    return reference if isinstance(reference, str) and reference.strip() else None


def _failure_diagnostics(
    *,
    model_id: str,
    model_revision: str | None,
    device: str,
    dtype: str,
    input_count: int,
    valid_article_count: int,
    embedded_count: int,
    failed_count: int,
) -> dict[str, Any]:
    """Build safe diagnostics for paths that cannot produce memberships."""

    return {
        "model_id": model_id,
        "model_revision": model_revision,
        "projection_version": PROJECTION_VERSION,
        "summary_cap": SUMMARY_CHAR_LIMIT,
        "clustering_algorithm_version": ALGORITHM_VERSION,
        "device": device,
        "dtype": dtype,
        "input_count": input_count,
        "valid_article_count": valid_article_count,
        "embedded_count": embedded_count,
        "failed_count": failed_count,
        "accepted_edges": [],
        "near_threshold_rejected_pairs": [],
    }


def cluster_articles(
    articles: Iterable[Article],
    *,
    embedder_factory: Callable[[], EmbeddingBackend] | None,
    threshold: float = DEFAULT_THRESHOLD,
    similarity_function: SimilarityFunction | None = None,
    diagnostic_sink: DiagnosticSink | None = None,
    model_id: str = MODEL_ID,
    model_revision: str | None = MODEL_REVISION,
    device: str = "cpu",
    dtype: str = "float32",
) -> StageResult[EventCandidate]:
    """Cluster canonical Articles with deterministic local semantic edges."""

    if isinstance(articles, (str, bytes)):
        return _invalid_input()
    try:
        input_articles = tuple(articles)
    except Exception:
        return _invalid_input()
    try:
        normalized_threshold = float(threshold)
    except (TypeError, ValueError, OverflowError):
        return _invalid_input()
    if not math.isfinite(normalized_threshold) or not -1.0 <= normalized_threshold <= 1.0:
        return _invalid_input()
    if not input_articles:
        diagnostic_ref = _emit_diagnostics(
            diagnostic_sink,
            {
                **_failure_diagnostics(
                    model_id=model_id,
                    model_revision=model_revision,
                    device=device,
                    dtype=dtype,
                    input_count=0,
                    valid_article_count=0,
                    embedded_count=0,
                    failed_count=0,
                ),
                "threshold": normalized_threshold,
                **_edge_policy_metadata(normalized_threshold),
                "timing_ms": {
                    "initialization": 0.0,
                    "embedding": 0.0,
                    "clustering": 0.0,
                },
            },
        )
        return _result((), (), diagnostic_ref)

    failures: list[ItemFailure] = []
    valid_articles: list[Article] = []
    seen_ids: set[str] = set()
    for item in input_articles:
        if not isinstance(item, Article):
            failures.append(ItemFailure(code=FailureCode.ITEM_VALIDATION_FAILED))
            continue
        if item.article_id in seen_ids:
            failures.append(
                ItemFailure(item_id=item.article_id, code=FailureCode.ITEM_VALIDATION_FAILED)
            )
            continue
        seen_ids.add(item.article_id)
        valid_articles.append(item)
    valid_articles.sort(key=lambda item: item.article_id)
    if not valid_articles:
        diagnostic_ref = _emit_diagnostics(
            diagnostic_sink,
            {
                **_failure_diagnostics(
                    model_id=model_id,
                    model_revision=model_revision,
                    device=device,
                    dtype=dtype,
                    input_count=len(input_articles),
                    valid_article_count=0,
                    embedded_count=0,
                    failed_count=len(failures),
                ),
                "threshold": normalized_threshold,
                **_edge_policy_metadata(normalized_threshold),
                "timing_ms": {
                    "initialization": 0.0,
                    "embedding": 0.0,
                    "clustering": 0.0,
                },
            },
        )
        return _result((), failures, diagnostic_ref)
    if len(valid_articles) == 1:
        diagnostic_ref = _emit_diagnostics(
            diagnostic_sink,
            {
                **_failure_diagnostics(
                    model_id=model_id,
                    model_revision=model_revision,
                    device=device,
                    dtype=dtype,
                    input_count=len(input_articles),
                    valid_article_count=1,
                    embedded_count=0,
                    failed_count=len(failures),
                ),
                "threshold": normalized_threshold,
                **_edge_policy_metadata(normalized_threshold),
                "timing_ms": {
                    "initialization": 0.0,
                    "embedding": 0.0,
                    "clustering": 0.0,
                },
            },
        )
        candidate = EventCandidate.from_article_ids((valid_articles[0].article_id,))
        return _result((candidate,), failures, diagnostic_ref)
    if not callable(embedder_factory):
        model_failure = _local_model_failure()
        all_failures = (*failures, model_failure)
        diagnostic_ref = _emit_diagnostics(
            diagnostic_sink,
            {
                **_failure_diagnostics(
                    model_id=model_id,
                    model_revision=model_revision,
                    device=device,
                    dtype=dtype,
                    input_count=len(input_articles),
                    valid_article_count=len(valid_articles),
                    embedded_count=0,
                    failed_count=len(all_failures),
                ),
                "threshold": normalized_threshold,
                **_edge_policy_metadata(normalized_threshold),
            },
        )
        return _result((), all_failures, diagnostic_ref)

    initialization_started = time.perf_counter()
    try:
        embedder = embedder_factory()
        embed = getattr(embedder, "embed")
        if not callable(embed):
            raise TypeError("embedder does not expose embed")
    except Exception:
        initialization_ms = (time.perf_counter() - initialization_started) * 1000
        model_failure = _local_model_failure()
        all_failures = (*failures, model_failure)
        metadata = {
            **_failure_diagnostics(
                model_id=model_id,
                model_revision=model_revision,
                device=device,
                dtype=dtype,
                input_count=len(input_articles),
                valid_article_count=len(valid_articles),
                embedded_count=0,
                failed_count=len(all_failures),
            ),
            "threshold": normalized_threshold,
            **_edge_policy_metadata(normalized_threshold),
            "timing_ms": {
                "initialization": round(initialization_ms, 3),
                "embedding": 0.0,
                "clustering": 0.0,
            },
        }
        diagnostic_ref = _emit_diagnostics(diagnostic_sink, metadata)
        return _result((), all_failures, diagnostic_ref)
    initialization_ms = (time.perf_counter() - initialization_started) * 1000

    embedded_articles: list[Article] = []
    vectors: list[tuple[float, ...]] = []
    embedding_started = time.perf_counter()
    for item in valid_articles:
        try:
            vector = _normalize_vector(embed(project_article(item)))
            if vectors and len(vector) != len(vectors[0]):
                raise ValueError("embedding dimensions must match")
        except Exception:
            failures.append(_local_model_failure(item.article_id))
            continue
        embedded_articles.append(item)
        vectors.append(vector)
    embedding_ms = (time.perf_counter() - embedding_started) * 1000
    if not embedded_articles:
        metadata = {
            **_failure_diagnostics(
                model_id=model_id,
                model_revision=model_revision,
                device=device,
                dtype=dtype,
                input_count=len(input_articles),
                valid_article_count=len(valid_articles),
                embedded_count=0,
                failed_count=len(failures),
            ),
            "threshold": normalized_threshold,
            **_edge_policy_metadata(normalized_threshold),
            "timing_ms": {
                "initialization": round(initialization_ms, 3),
                "embedding": round(embedding_ms, 3),
                "clustering": 0.0,
            },
        }
        metadata.update(_backend_metadata(embedder))
        diagnostic_ref = _emit_diagnostics(diagnostic_sink, metadata)
        return _result((), failures, diagnostic_ref)

    clustering_started = time.perf_counter()
    try:
        candidates, accepted_edges, near_threshold_rejected = _components(
            embedded_articles,
            vectors,
            normalized_threshold,
            similarity_function or _cosine_similarity,
        )
    except Exception:
        model_failure = _local_model_failure()
        all_failures = (*failures, model_failure)
        metadata = {
            **_failure_diagnostics(
                model_id=model_id,
                model_revision=model_revision,
                device=device,
                dtype=dtype,
                input_count=len(input_articles),
                valid_article_count=len(valid_articles),
                embedded_count=len(embedded_articles),
                failed_count=len(all_failures),
            ),
            "threshold": normalized_threshold,
            **_edge_policy_metadata(normalized_threshold),
            "timing_ms": {
                "initialization": round(initialization_ms, 3),
                "embedding": round(embedding_ms, 3),
                "clustering": round(
                    (time.perf_counter() - clustering_started) * 1000,
                    3,
                ),
            },
        }
        metadata.update(_backend_metadata(embedder))
        diagnostic_ref = _emit_diagnostics(diagnostic_sink, metadata)
        return _result((), all_failures, diagnostic_ref)
    clustering_ms = (time.perf_counter() - clustering_started) * 1000

    metadata = {
        "model_id": model_id,
        "model_revision": model_revision,
        "projection_version": PROJECTION_VERSION,
        "summary_cap": SUMMARY_CHAR_LIMIT,
        "clustering_algorithm_version": ALGORITHM_VERSION,
        "threshold": normalized_threshold,
        **_edge_policy_metadata(normalized_threshold),
        "device": device,
        "dtype": dtype,
        "input_count": len(input_articles),
        "valid_article_count": len(valid_articles),
        "embedded_count": len(embedded_articles),
        "failed_count": len(failures),
        "failed_article_ids": sorted(
            failure.item_id for failure in failures if failure.item_id is not None
        ),
        "accepted_edges": [
            {
                "article_ids": [left, right],
                "similarity": round(similarity, 6),
            }
            for left, right, similarity in accepted_edges[:MAX_DIAGNOSTIC_EDGES]
        ],
        "near_threshold_rejected_pairs": [
            {
                "article_ids": [left, right],
                "similarity": round(similarity, 6),
            }
            for left, right, similarity in near_threshold_rejected[:MAX_DIAGNOSTIC_EDGES]
        ],
        "timing_ms": {
            "initialization": round(initialization_ms, 3),
            "embedding": round(embedding_ms, 3),
            "clustering": round(clustering_ms, 3),
        },
    }
    metadata.update(_backend_metadata(embedder))
    diagnostic_ref = _emit_diagnostics(diagnostic_sink, metadata)
    return _result(candidates, failures, diagnostic_ref)


class SentenceTransformerEmbedder:
    """Lazy local adapter for the approved Sentence Transformers model."""

    def __init__(
        self,
        *,
        model_revision: str,
        model_id: str = MODEL_ID,
        cache_folder: str | None = None,
        local_files_only: bool = False,
    ) -> None:
        normalized_revision = (
            model_revision.strip().lower() if isinstance(model_revision, str) else ""
        )
        if not IMMUTABLE_REVISION_PATTERN.fullmatch(normalized_revision):
            raise ValueError("model_revision must be a 40-character immutable commit SHA")
        from sentence_transformers import SentenceTransformer, __version__ as st_version
        import torch
        import transformers

        self.model_id = model_id
        self.model_revision = normalized_revision
        self.device = "cpu"
        self.dtype = "float32"
        self._diagnostic_versions = {
            "sentence_transformers_version": st_version,
            "transformers_version": transformers.__version__,
            "torch_version": torch.__version__,
        }
        self._model = SentenceTransformer(
            model_id,
            device="cpu",
            revision=normalized_revision,
            cache_folder=cache_folder,
            local_files_only=local_files_only,
            trust_remote_code=False,
        )

    def embed(self, text: str) -> tuple[float, ...]:
        if not isinstance(text, str) or not text:
            raise ValueError("embedding text must be a non-empty string")
        encoded = self._model.encode(
            [text],
            convert_to_numpy=True,
            normalize_embeddings=False,
            show_progress_bar=False,
        )
        return tuple(float(value) for value in encoded[0])

    def diagnostic_metadata(self) -> Mapping[str, Any]:
        return {
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "device": self.device,
            "dtype": self.dtype,
            **self._diagnostic_versions,
        }


__all__ = [
    "ALGORITHM_VERSION",
    "DEFAULT_THRESHOLD",
    "EDGE_POLICY_VERSION",
    "EmbeddingBackend",
    "HIGH_CONFIDENCE_THRESHOLD",
    "MIN_TITLE_IDENTITY_SPAN",
    "MODEL_ID",
    "MODEL_REVISION",
    "PROJECTION_VERSION",
    "SentenceTransformerEmbedder",
    "SUMMARY_CHAR_LIMIT",
    "cluster_articles",
    "normalize_title_for_edge_policy",
    "project_article",
]
