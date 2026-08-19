from chatbot_pacch.models import DiscoveredPage
from chatbot_pacch.portal.extractor import extract_document


def _page() -> DiscoveredPage:
    return DiscoveredPage(
        url="https://portalacademico.cch.unam.mx/historiauniversal1/feudalismo/origen",
        lastmod="2026-01-01",
        object_root="https://portalacademico.cch.unam.mx/historiauniversal1/feudalismo",
        object_title="Feudalismo",
        subject="Historia Universal Moderna y Contemporánea I",
        subject_slug="historia-universal-moderna-y-contemporanea-i",
    )


def test_extract_document_keeps_academic_content_and_removes_navigation() -> None:
    html = """
    <html><body>
      <header><p>Portal Académico</p></header>
      <main id="main-content">
        <nav><a href="/">Menú</a></nav>
        <h1>Origen del feudalismo</h1>
        <p>El feudalismo se desarrolló durante la Edad Media.</p>
        <h2>Características</h2>
        <p>La tierra tuvo un papel central en las relaciones sociales.</p>
        <ul><li>Relaciones de vasallaje.</li><li>Economía agraria.</li></ul>
      </main>
      <footer>Newsletter</footer>
    </body></html>
    """
    document = extract_document(html, _page())
    assert document.title == "Origen del feudalismo"
    assert len(document.sections) == 2
    assert "Edad Media" in document.text
    assert "Relaciones de vasallaje" in document.text
    assert "Menú" not in document.text


def test_extract_document_discards_tiny_navigation_sections() -> None:
    html = """
    <main>
      <h1>Tema</h1>
      <p>Este contenido académico tiene suficiente información para conservarse.</p>
      <h2>Alumno:</h2>
      <p>Historia Universal 1</p>
    </main>
    """
    document = extract_document(html, _page())
    assert len(document.sections) == 1
    assert "Alumno" not in document.text


def test_extract_document_supports_legacy_empty_main_anchor() -> None:
    html = """
    <body>
      <a id="main-content"></a>
      <div class="row">
        <aside><p>Navegación lateral muy extensa que no debe indexarse.</p></aside>
        <section class="col-sm-9">
          <h1>La Ilustración</h1>
          <p>La Ilustración difundió ideas políticas y filosóficas durante el siglo XVIII.</p>
        </section>
      </div>
    </body>
    """
    document = extract_document(html, _page())
    assert document.title == "La Ilustración"
    assert "siglo XVIII" in document.text
    assert "Navegación lateral" not in document.text
