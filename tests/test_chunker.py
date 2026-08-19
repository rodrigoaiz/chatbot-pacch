from chatbot_pacch.models import ExtractedDocument, Section
from chatbot_pacch.portal.chunker import chunk_document


def test_chunk_document_splits_content_and_preserves_heading() -> None:
    document = ExtractedDocument(
        url="https://example.test/recurso",
        title="Recurso",
        subject="Historia",
        object_title="Objeto",
        lastmod=None,
        sections=(
            Section(
                heading="Características",
                blocks=("Primer párrafo " * 20, "Segundo párrafo " * 20),
            ),
        ),
    )
    chunks = chunk_document(document, max_chars=220, overlap_chars=30)
    assert len(chunks) >= 2
    assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))
    assert all(chunk.heading == "Características" for chunk in chunks)
    assert all(chunk.text for chunk in chunks)
    assert all(not chunk.text.startswith("árrafo") for chunk in chunks[1:])
