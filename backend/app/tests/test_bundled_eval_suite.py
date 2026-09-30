"""Check that the distributed regression suite is usable from a fresh checkout."""

import json
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base, Document, Repository
from app.services.evals.ragas_runner import _hard_rules
from app.services.evals.suites import DEFAULT_SUITE_DIR, list_eval_suites, load_eval_suite


SUITE_ID = "devharbor-real-project-rag-baseline"
SOURCE_DIR = DEFAULT_SUITE_DIR.parent / "sources"


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _source_names() -> list[str]:
    # Read the shipped artifact, not a test-only replica of the suite.
    payload = json.loads((DEFAULT_SUITE_DIR / "rag_cases.json").read_text(encoding="utf-8"))
    return list(dict.fromkeys(case["source_file"] for case in payload["cases"]))


def _repository(db: Session, name: str) -> Repository:
    repo = Repository(owner="local", name=name, full_name=f"local/{name}")
    db.add(repo)
    db.flush()
    return repo


def _upload_sources(db: Session, repo: Repository, names: list[str]) -> dict[str, Document]:
    documents = {}
    for name in names:
        # Matching production upload metadata is sufficient for loader validation;
        # these tests do not claim to exercise embeddings or retrieval quality.
        document = Document(
            repo_id=repo.id,
            source_type="knowledge_file",
            source_id=uuid.uuid4(),
            title=name,
            content=(SOURCE_DIR / name).read_text(encoding="utf-8"),
            meta={"filename": name},
        )
        db.add(document)
        documents[name] = document
    db.flush()
    return documents


def test_bundled_suite_resolves_shipped_sources_in_a_renamed_fork(db: Session) -> None:
    repo = _repository(db, "renamed-devharbor-fork")
    documents = _upload_sources(db, repo, _source_names())

    listed = next(item for item in list_eval_suites(db, repo.id) if item["id"] == SUITE_ID)
    loaded = load_eval_suite(db, repo.id, SUITE_ID)

    assert listed["ready"] is True
    assert listed["case_count"] == 5
    assert len({case.id for case in loaded.cases}) == 5
    assert {case.kind for case in loaded.cases} >= {"positive", "boundary", "negative"}
    assert loaded.metadata["sha256"] == listed["sha256"]
    for case in loaded.cases:
        document = documents[case.source_file]
        assert document.content.strip()
        assert case.expected_source_ids == [str(document.id), str(document.source_id)]


def test_bundled_suite_rejects_missing_source_even_if_another_repo_has_it(db: Session) -> None:
    repo = _repository(db, "target")
    other_repo = _repository(db, "other")
    names = _source_names()
    missing_name = names[-1]
    _upload_sources(db, repo, names[:-1])
    _upload_sources(db, other_repo, names)

    listed = next(item for item in list_eval_suites(db, repo.id) if item["id"] == SUITE_ID)

    assert listed["ready"] is False
    assert listed["missing_sources"] == [missing_name]
    with pytest.raises(ValueError, match="缺少已索引来源") as error:
        load_eval_suite(db, repo.id, SUITE_ID)
    assert missing_name in str(error.value)


def test_bundled_unknown_metrics_case_rejects_invented_numbers(db: Session) -> None:
    repo = _repository(db, "metrics")
    documents = _upload_sources(db, repo, _source_names())
    case = next(case for case in load_eval_suite(db, repo.id, SUITE_ID).cases if case.kind == "negative")
    document = documents[case.source_file]
    sources = [{"source_id": str(document.source_id)}]
    contexts = [document.content]

    supported = _hard_rules(case, {"answer": case.reference}, sources, contexts)
    fabricated = _hard_rules(
        case,
        {"answer": "无法确定精确值，但估计准确率 99.9%，P95 延迟 100 ms。"},
        sources,
        contexts,
    )

    assert supported["passed"] is True
    assert fabricated["passed"] is False
    assert fabricated["answer_pattern_matched"] is False
