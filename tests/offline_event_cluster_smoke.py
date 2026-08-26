"""Offline v1.3 event clustering smoke tests.

The normal smoke suite injects deterministic embeddings and never imports or
downloads a model runtime.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from canonical_domain import Article, FailureCode, StageName, StageStatus  # noqa: E402
from event_cluster import (  # noqa: E402
    ALGORITHM_VERSION,
    DEFAULT_THRESHOLD,
    MODEL_ID,
    MODEL_REVISION,
    PROJECTION_VERSION,
    SUMMARY_CHAR_LIMIT,
    SentenceTransformerEmbedder,
    project_article,
    cluster_articles,
)


COLLECTED_AT = datetime(2026, 8, 26, 8, 0, tzinfo=timezone.utc)
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "event_clustering_v1_3.json"


def article(key: str, title: str, summary: str | None = None, language: str = "en") -> Article:
    return Article.from_source(
        source="Fixture",
        url=f"https://fixture.example/{key}",
        published_at=COLLECTED_AT,
        collected_at=COLLECTED_AT,
        language=language,
        title=title,
        summary=summary,
    )


class MappingEmbedder:
    def __init__(self, vectors: dict[str, tuple[float, ...]]) -> None:
        self.vectors = vectors
        self.calls: list[str] = []

    def embed(self, text: str) -> tuple[float, ...]:
        self.calls.append(text)
        return self.vectors[text]

    def diagnostic_metadata(self) -> dict[str, str]:
        return {
            "sentence_transformers_version": "fixture",
            "transformers_version": "fixture",
            "torch_version": "fixture",
        }


class SelectiveEmbedder(MappingEmbedder):
    def __init__(self, vectors: dict[str, tuple[float, ...]], failures: set[str]) -> None:
        super().__init__(vectors)
        self.failures = failures

    def embed(self, text: str) -> tuple[float, ...]:
        self.calls.append(text)
        if text in self.failures:
            raise RuntimeError("fixture embedding failure")
        return self.vectors[text]


def test_empty_input_is_successful_without_model_initialization() -> None:
    initialized = False

    def factory() -> MappingEmbedder:
        nonlocal initialized
        initialized = True
        raise AssertionError("empty input must not initialize the embedder")

    result = cluster_articles((), embedder_factory=factory, threshold=0.8)

    assert result.stage == StageName.EVENT_CLUSTER
    assert result.status == StageStatus.SUCCEEDED
    assert result.outputs == ()
    assert result.failures == ()
    assert initialized is False


def test_one_article_forms_a_singleton_candidate() -> None:
    item = article("one", "A single event")

    result = cluster_articles(
        (item,),
        embedder_factory=_unexpected_model_initialization,
        threshold=0.8,
    )

    assert result.status == StageStatus.SUCCEEDED
    assert len(result.outputs) == 1
    candidate = result.outputs[0]
    assert candidate.article_ids == (item.article_id,)
    assert set(candidate.__dataclass_fields__) == {"event_candidate_id", "article_ids"}


def _unexpected_model_initialization() -> MappingEmbedder:
    raise AssertionError("singleton input must not initialize the embedder")


def test_same_event_articles_cluster_and_order_is_independent() -> None:
    first = article(
        "first",
        "Central bank cuts rates",
        "Policy rate lowered by 25 basis points",
        "en",
    )
    second = article(
        "second",
        "央行降息 25 个基点",
        "中央银行宣布下调政策利率",
        "zh-CN",
    )
    unrelated = article("other", "Severe storm reaches the coast", "A storm made landfall", "en")
    vectors = {
        project_article(first): (1.0, 0.0, 0.0),
        project_article(second): (0.98, 0.1, 0.0),
        project_article(unrelated): (0.0, 1.0, 0.0),
    }

    first_embedder = MappingEmbedder(vectors)
    first_run = cluster_articles(
        (unrelated, second, first),
        embedder_factory=lambda: first_embedder,
        threshold=0.8,
    )
    repeated_run = cluster_articles(
        (first, unrelated, second),
        embedder_factory=lambda: MappingEmbedder(vectors),
        threshold=0.8,
    )

    assert first_run.status == StageStatus.SUCCEEDED
    assert repeated_run.status == StageStatus.SUCCEEDED
    assert [candidate.to_dict() for candidate in first_run.outputs] == [
        candidate.to_dict() for candidate in repeated_run.outputs
    ]
    assert len(first_run.outputs) == 2
    assert first_embedder.calls == [
        project_article(item)
        for item in sorted((first, second, unrelated), key=lambda item: item.article_id)
    ]
    assert sorted(first_run.outputs[0].article_ids + first_run.outputs[1].article_ids) == sorted(
        (first.article_id, second.article_id, unrelated.article_id)
    )


def test_projection_is_versioned_and_caps_summary() -> None:
    item = article("projection", "  title  ", "x" * 500)

    projection = project_article(item)

    assert PROJECTION_VERSION == "article-title-summary-v1"
    assert projection.startswith("query:   title  \n")
    assert len(projection.split("\n", 1)[1]) == 300
    assert project_article(article("no-summary", "Title only")) == "query: Title only"
    assert project_article(article("empty-summary", "Title only", "   ")) == "query: Title only"


def test_v13_accepted_runtime_defaults_are_frozen() -> None:
    assert MODEL_ID == "intfloat/multilingual-e5-small"
    assert MODEL_REVISION == "614241f622f53c4eeff9890bdc4f31cfecc418b3"
    assert PROJECTION_VERSION == "article-title-summary-v1"
    assert SUMMARY_CHAR_LIMIT == 300
    assert DEFAULT_THRESHOLD == 0.91
    assert ALGORITHM_VERSION == "connected-components-v1"


def test_accepted_threshold_membership_regression() -> None:
    first = article("accepted-first", "Same story announcement", "Shared facts")
    second = article("accepted-second", "Same story reaction", "Shared facts")
    distinct = article("accepted-distinct", "Different policy event", "Unrelated facts")
    vectors = {
        project_article(first): (1.0, 0.0),
        project_article(second): (0.98, 0.2),
        project_article(distinct): (0.0, 1.0),
    }

    result = cluster_articles(
        (distinct, second, first),
        embedder_factory=lambda: MappingEmbedder(vectors),
    )

    assert result.status == StageStatus.SUCCEEDED
    memberships = {frozenset(candidate.article_ids) for candidate in result.outputs}
    assert frozenset((first.article_id, second.article_id)) in memberships
    assert frozenset((distinct.article_id,)) in memberships


def test_fixture_acceptance_metadata_is_explicit() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    cases = {case["case_id"]: case for case in payload["cases"]}

    production_cases = {
        "iran_same_sanctions_event",
        "iran_action_reaction_event",
        "buyback_word_sense",
        "broad_geopolitical_topic",
    }
    for case_id, case in cases.items():
        assert case["provenance"] != "repository-supported"
        assert case["acceptance_class"] in {
            "production-relevant",
            "robustness-only",
            "outside-normal-window",
        }
        assert case["window_relevance"] in {
            "production-realistic",
            "synthetic",
            "outside-normal-window",
        }
        if case_id in production_cases:
            assert case["acceptance_class"] == "production-relevant"
            assert case["window_relevance"] == "production-realistic"


def test_l2_normalization_and_same_keyword_negative() -> None:
    first = article(
        "keyword-first",
        "Buyback announced by Australia",
        "A public gun buyback plan",
    )
    second = article(
        "keyword-second",
        "Share buyback approved by Samsung",
        "A corporate share repurchase",
    )
    third = article(
        "keyword-third",
        "Central bank reverse repo operation",
        "A liquidity reverse repo",
    )
    vectors = {
        project_article(first): (10.0, 0.0, 0.0),
        project_article(second): (9.0, 4.3589, 0.0),
        project_article(third): (0.0, 0.0, 10.0),
    }

    result = cluster_articles(
        (third, first, second),
        embedder_factory=lambda: MappingEmbedder(vectors),
        threshold=0.95,
    )

    assert result.status == StageStatus.SUCCEEDED
    assert len(result.outputs) == 3
    assert all(len(candidate.article_ids) == 1 for candidate in result.outputs)


def test_invalid_article_is_item_local_when_valid_candidates_remain() -> None:
    item = article("valid", "Valid article")
    embedder = MappingEmbedder({project_article(item): (1.0, 0.0)})

    result = cluster_articles(
        (object(), item),
        embedder_factory=lambda: embedder,
        threshold=0.8,
    )

    assert result.status == StageStatus.PARTIAL
    assert len(result.outputs) == 1
    assert result.failures[0].code == FailureCode.ITEM_VALIDATION_FAILED
    assert result.failures[0].item_id is None


def test_all_invalid_articles_fail_without_initializing_model() -> None:
    initialized = False

    def factory() -> MappingEmbedder:
        nonlocal initialized
        initialized = True
        raise AssertionError("invalid input must not initialize the embedder")

    result = cluster_articles(
        (object(),),
        embedder_factory=factory,
        threshold=0.8,
    )

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert result.failures[0].code == FailureCode.ITEM_VALIDATION_FAILED
    assert initialized is False


def test_partial_embedding_failure_keeps_successful_candidates() -> None:
    good = article("good", "Good article")
    bad = article("bad", "Bad article")
    embedder = SelectiveEmbedder(
        {project_article(good): (1.0, 0.0)},
        {project_article(bad)},
    )

    result = cluster_articles(
        (bad, good),
        embedder_factory=lambda: embedder,
        threshold=0.8,
    )

    assert result.status == StageStatus.PARTIAL
    assert result.outputs[0].article_ids == (good.article_id,)
    assert len(result.failures) == 1
    assert result.failures[0].item_id == bad.article_id
    assert result.failures[0].code == FailureCode.LOCAL_MODEL_FAILED


def test_all_embedding_failures_are_stage_failure() -> None:
    first = article("first-fail", "First failure")
    second = article("second-fail", "Second failure")
    embedder = SelectiveEmbedder(
        {},
        {project_article(first), project_article(second)},
    )

    result = cluster_articles(
        (first, second),
        embedder_factory=lambda: embedder,
        threshold=0.8,
    )

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert [failure.item_id for failure in result.failures] == sorted(
        (first.article_id, second.article_id)
    )
    assert all(failure.code == FailureCode.LOCAL_MODEL_FAILED for failure in result.failures)


def test_model_initialization_failure_is_stage_level() -> None:
    first = article("init-fail-first", "Initialization failure first")
    second = article("init-fail-second", "Initialization failure second")

    def factory() -> MappingEmbedder:
        raise RuntimeError("fixture model initialization failure")

    result = cluster_articles(
        (first, second),
        embedder_factory=factory,
        threshold=0.8,
    )

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert len(result.failures) == 1
    assert result.failures[0].code == FailureCode.LOCAL_MODEL_FAILED
    assert result.failures[0].item_id is None


def test_similarity_failure_is_stage_level_and_discards_membership() -> None:
    first = article("similarity-first", "Similarity first")
    second = article("similarity-second", "Similarity second")
    vectors = {
        project_article(first): (1.0, 0.0),
        project_article(second): (1.0, 0.0),
    }

    def broken_similarity(_: tuple[float, ...], __: tuple[float, ...]) -> float:
        raise RuntimeError("fixture similarity failure")

    result = cluster_articles(
        (first, second),
        embedder_factory=lambda: MappingEmbedder(vectors),
        threshold=0.8,
        similarity_function=broken_similarity,
    )

    assert result.status == StageStatus.FAILED
    assert result.outputs == ()
    assert result.failures[-1].code == FailureCode.LOCAL_MODEL_FAILED
    assert result.failures[-1].item_id is None


def test_connected_components_chain_behavior_is_explicitly_measured() -> None:
    first = article("chain-a", "Chain A")
    middle = article("chain-b", "Chain B")
    last = article("chain-c", "Chain C")
    vectors = {
        project_article(first): (1.0, 0.0),
        project_article(middle): (0.819, 0.574),
        project_article(last): (0.342, 0.94),
    }

    result = cluster_articles(
        (last, first, middle),
        embedder_factory=lambda: MappingEmbedder(vectors),
        threshold=0.8,
    )

    # A≈B and B≈C while A≠C demonstrates the known transitive edge risk.
    assert result.status == StageStatus.SUCCEEDED
    assert len(result.outputs) == 1
    assert set(result.outputs[0].article_ids) == {
        first.article_id,
        middle.article_id,
        last.article_id,
    }


def test_diagnostics_are_bounded_noncanonical_and_referenceable() -> None:
    first = article("diagnostic-first", "Diagnostic first")
    second = article("diagnostic-second", "Diagnostic second")
    near = article("diagnostic-near", "Diagnostic near threshold")
    captured: dict[str, object] = {}
    vectors = {
        project_article(first): (1.0, 0.0),
        project_article(second): (1.0, 0.0),
        project_article(near): (0.79, 0.613),
    }

    def sink(payload: dict[str, object]) -> str:
        captured.update(payload)
        return "diag://event-cluster/fixture"

    result = cluster_articles(
        (second, near, first),
        embedder_factory=lambda: MappingEmbedder(vectors),
        threshold=0.8,
        diagnostic_sink=sink,
    )

    assert result.status == StageStatus.SUCCEEDED
    assert result.diagnostic_ref == "diag://event-cluster/fixture"
    assert captured["model_id"] == "intfloat/multilingual-e5-small"
    assert captured["projection_version"] == PROJECTION_VERSION
    assert captured["summary_cap"] == 300
    assert captured["input_count"] == 3
    assert captured["embedded_count"] == 3
    assert captured["sentence_transformers_version"] == "fixture"
    assert captured["accepted_edges"]
    assert captured["near_threshold_rejected_pairs"]
    assert set(captured["accepted_edges"][0]) == {"article_ids", "similarity"}  # type: ignore[index]
    assert isinstance(captured["accepted_edges"][0]["similarity"], float)  # type: ignore[index]
    assert "timing_ms" in captured
    assert "embedding_vectors" not in captured


def test_invalid_threshold_is_fail_closed() -> None:
    item = article("threshold", "Invalid threshold")

    result = cluster_articles(
        (item,),
        embedder_factory=lambda: MappingEmbedder({}),
        threshold="not-a-number",  # type: ignore[arg-type]
    )

    assert result.status == StageStatus.FAILED
    assert result.failures[0].code == FailureCode.INVALID_INPUT


def test_sentence_transformer_adapter_requires_immutable_revision() -> None:
    for revision in ("", "main", "0" * 39):
        try:
            SentenceTransformerEmbedder(model_revision=revision)
        except ValueError as error:
            assert "revision" in str(error)
        else:
            raise AssertionError("adapter must reject a floating model identity")


def main() -> None:
    test_empty_input_is_successful_without_model_initialization()
    test_one_article_forms_a_singleton_candidate()
    test_same_event_articles_cluster_and_order_is_independent()
    test_projection_is_versioned_and_caps_summary()
    test_v13_accepted_runtime_defaults_are_frozen()
    test_accepted_threshold_membership_regression()
    test_fixture_acceptance_metadata_is_explicit()
    test_l2_normalization_and_same_keyword_negative()
    test_invalid_article_is_item_local_when_valid_candidates_remain()
    test_all_invalid_articles_fail_without_initializing_model()
    test_partial_embedding_failure_keeps_successful_candidates()
    test_all_embedding_failures_are_stage_failure()
    test_model_initialization_failure_is_stage_level()
    test_similarity_failure_is_stage_level_and_discards_membership()
    test_connected_components_chain_behavior_is_explicitly_measured()
    test_diagnostics_are_bounded_noncanonical_and_referenceable()
    test_invalid_threshold_is_fail_closed()
    test_sentence_transformer_adapter_requires_immutable_revision()
    print("offline event cluster smoke passed")


if __name__ == "__main__":
    main()
