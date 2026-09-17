from chatbot_pacch.models import SearchResult, StoredChunk
from chatbot_pacch.rag.grounding import unsupported_precise_claims
from chatbot_pacch.rag.retrieval import (
    has_sufficient_evidence,
    temporal_evidence_bonus,
)


def _result(text: str, **overrides: object) -> SearchResult:
    values: dict[str, object] = {
        "chunk_id": 1,
        "title": "Primera etapa: Inicio",
        "subject": "Historia de Mexico I",
        "heading": "Primera etapa: Inicio",
        "text": text,
        "url": "https://portalacademico.cch.unam.mx/recurso",
        "score": 0.03,
        "semantic_score": 0.55,
        "lexical_rank": 1,
    }
    values.update(overrides)
    return SearchResult(**values)


def test_grounding_accepts_supported_date_and_ignores_citation_number() -> None:
    results = [_result("El movimiento inicio el 16 de septiembre de 1810.")]

    assert not unsupported_precise_claims(
        "Inicio el 16 de septiembre de 1810 [1].", results
    )


def test_grounding_rejects_unsupported_date() -> None:
    results = [_result("El movimiento inicio en septiembre de 1810.")]

    unsupported = unsupported_precise_claims(
        "Inicio el 9 de septiembre de 1810 [1].", results
    )

    assert "9 de septiembre de 1810" in unsupported


def test_grounding_rejects_invented_range() -> None:
    results = [_result("Se mencionan por separado los anos 1789 y 1799.")]

    assert "1789-1799" in unsupported_precise_claims(
        "El proceso abarco 1789-1799 [1].", results
    )


def test_exact_date_question_requires_full_date_evidence() -> None:
    question = "¿Cual fue la fecha de inicio de la Independencia de Mexico?"

    assert not has_sufficient_evidence([_result("El movimiento inicio en 1810.")], question)
    assert has_sufficient_evidence(
        [_result("El movimiento inicio el 16 de septiembre de 1810.")], question
    )


def test_temporal_evidence_bonus_prefers_complete_dates() -> None:
    question = "¿Cuando fue la fecha de inicio de la Independencia de Mexico?"
    dated = StoredChunk(
        chunk_id=1,
        title="Primera etapa",
        subject="Historia",
        heading="Inicio",
        text="El movimiento inicio el 16 de septiembre de 1810.",
        url="https://example.test/fecha",
    )
    year_only = StoredChunk(
        chunk_id=2,
        title="Introduccion",
        subject="Historia",
        heading="Inicio",
        text="El movimiento inicio en 1810.",
        url="https://example.test/ano",
    )

    assert temporal_evidence_bonus(question, dated) > temporal_evidence_bonus(
        question, year_only
    )
