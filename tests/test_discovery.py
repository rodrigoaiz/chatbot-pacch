from chatbot_pacch.models import CatalogObject, SitemapEntry
from chatbot_pacch.portal.discovery import (
    match_pages,
    parse_catalog,
    parse_sitemap,
    slugify,
)


def test_slugify_preserves_meaning_without_accents() -> None:
    assert (
        slugify("Historia Universal Moderna y Contemporánea I")
        == "historia-universal-moderna-y-contemporanea-i"
    )


def test_parse_catalog_extracts_resource_heading_links() -> None:
    html = """
    <main>
      <h3>Historia Universal Moderna y Contemporánea I</h3>
      <article><h5><a href="/historiauniversal1/feudalismo">Feudalismo</a></h5></article>
      <article><h5><a href="https://otro.example/recurso">Externo</a></h5></article>
    </main>
    """
    objects = parse_catalog(html, "https://portalacademico.cch.unam.mx")
    assert len(objects) == 1
    assert objects[0].title == "Feudalismo"
    assert objects[0].root_url.endswith("/historiauniversal1/feudalismo")


def test_parse_sitemap_and_match_descendants() -> None:
    xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://portalacademico.cch.unam.mx/historiauniversal1/feudalismo</loc><lastmod>2026-01-01</lastmod></url>
      <url><loc>https://portalacademico.cch.unam.mx/historiauniversal1/feudalismo/origen</loc></url>
      <url><loc>https://portalacademico.cch.unam.mx/biologia1/celula</loc></url>
    </urlset>"""
    _, entries = parse_sitemap(xml)
    objects = [
        CatalogObject(
            root_url="https://portalacademico.cch.unam.mx/historiauniversal1/feudalismo",
            title="Feudalismo",
            subject="Historia Universal Moderna y Contemporánea I",
            subject_slug="historia-universal-moderna-y-contemporanea-i",
        )
    ]
    pages = match_pages(
        objects,
        entries,
        subject_slug="historia-universal-moderna-y-contemporanea-i",
        index_all_objects=False,
        max_pages=10,
    )
    assert [page.url for page in pages] == [entries[0].url, entries[1].url]
    assert pages[0].lastmod == "2026-01-01"


def test_match_pages_respects_limit() -> None:
    root = "https://portalacademico.cch.unam.mx/historiauniversal1/tema"
    pages = match_pages(
        [CatalogObject(root, "Tema", "Historia", "historia")],
        [SitemapEntry(f"{root}/{number}") for number in range(5)],
        subject_slug="historia",
        index_all_objects=False,
        max_pages=2,
    )
    assert len(pages) == 2
