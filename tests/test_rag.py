from chatbot_pacch.models import SearchResult
from chatbot_pacch.audit import malformed_urls
from chatbot_pacch.rag.answer import (
    SYSTEM_PROMPT,
    build_messages,
    public_source_url,
    public_sources,
)
from chatbot_pacch.rag.retrieval import has_sufficient_evidence


def _result(**overrides: object) -> SearchResult:
    values: dict[str, object] = {
        "chunk_id": 1,
        "title": "Liberalismo político",
        "subject": "Historia Universal I",
        "heading": "Derechos naturales",
        "text": "Los derechos naturales comprenden la vida, libertad y propiedad.",
        "url": "https://portalacademico.cch.unam.mx/recurso",
        "score": 0.03,
        "semantic_score": 0.52,
        "lexical_rank": 1,
    }
    values.update(overrides)
    return SearchResult(**values)


def test_prompt_uses_numbered_sources_and_silent_safety_rule() -> None:
    messages = build_messages("¿Qué son?", [_result()])
    assert "<FUENTE 1>" in messages[1]["content"]
    assert "Pregunta: ¿Qué son?" in messages[1]["content"]
    assert "Aplica estas reglas en silencio" in SYSTEM_PROMPT


def test_prompt_requests_latex_for_mathematical_expressions() -> None:
    assert "LaTeX" in SYSTEM_PROMPT
    assert "$ ... $" in SYSTEM_PROMPT
    assert "$$ ... $$" in SYSTEM_PROMPT
    assert r"\( ... \)" in SYSTEM_PROMPT
    assert r"\[ ... \]" in SYSTEM_PROMPT


def test_public_sources_are_unique_by_url() -> None:
    sources = public_sources([_result(), _result(chunk_id=2)])
    assert len(sources) == 1
    assert sources[0]["title"] == "Liberalismo político"


def test_public_source_url_uses_valid_portal_mirror() -> None:
    url = "https://portalacademico.cch.unam.mx/alumno/biologia1/recurso"
    assert (
        public_source_url(url)
        == "https://e1.portalacademico.cch.unam.mx/alumno/biologia1/recurso"
    )


def test_public_source_url_keeps_modern_object_on_main_portal() -> None:
    url = "https://portalacademico.cch.unam.mx/ingles1/tell-me-about-you/cultural-clip"
    assert public_source_url(url) == url


def test_audit_detects_malformed_route() -> None:
    urls = [
        "https://portalacademico.cch.unam.mx/alumno/recurso",
        "https://portalacademico.cch.unam.mx/ingles1/recurso",
        "https://portalacademico.cch.unam.mx/alumno/recurso//roto",
    ]
    assert malformed_urls(urls, "https://portalacademico.cch.unam.mx") == [urls[2]]


def test_evidence_accepts_strong_match_and_rejects_unrelated_query() -> None:
    assert has_sufficient_evidence([_result()])
    assert not has_sufficient_evidence(
        [_result(semantic_score=0.1, lexical_rank=None)]
    )
    assert not has_sufficient_evidence(
        [_result(semantic_score=0.2, lexical_rank=1)]
    )
