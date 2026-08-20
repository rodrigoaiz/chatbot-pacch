from chatbot_pacch.ingest import _is_permanently_missing
from chatbot_pacch.portal.crawler import PortalRequestError


def test_permanent_http_errors_are_treated_as_missing_pages() -> None:
    assert _is_permanently_missing(PortalRequestError("404 Not Found"))
    assert _is_permanently_missing(PortalRequestError("410 Gone"))
    assert not _is_permanently_missing(PortalRequestError("503 Service Unavailable"))
