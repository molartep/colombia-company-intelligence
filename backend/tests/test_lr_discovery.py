"""Publisher links route retrieval; only page evidence establishes issuer identity."""

import pytest
from test_secondary_quotes import lr_index_fixture

from app.core.errors import SourceError
from app.integrations.capital_markets.lr_discovery import candidates, parse_directory
from app.integrations.capital_markets.parsers import MAX_BYTES
from app.integrations.capital_markets.secondary_quotes import LR_INDEX_URL


def test_directory_uses_only_publisher_stock_links_and_deduplicates():
    content = (
        lr_index_fixture(slug="unknown-route") * 2
        + b"""
        <a href="https://evil.test/indicadores-economicos/movimiento-accionario/stock">Wrong</a>
        <a href="/indicadores-economicos/movimiento-accionario/stock?redirect=evil">Wrong</a>
        <a href="javascript:alert(1)">Wrong</a>
        <a href="/indicadores-economicos/movimiento-accionario">Index</a>
        <a href="/indicadores-economicos/movimiento-accionario/../private">Wrong</a>
    """
    )
    pages = parse_directory(content)
    assert len(pages) == 1
    assert pages[0].url == LR_INDEX_URL + "/unknown-route"


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"<html>changed</html>",
        b"x" * (MAX_BYTES + 1),
        b"".join(lr_index_fixture(slug=f"route-{i}") for i in range(101)),
    ],
)
def test_directory_rejects_missing_or_excessive_catalog(content):
    with pytest.raises(SourceError) as error:
        parse_directory(content)
    assert error.value.code == "lr_directory_invalid"


def test_candidates_are_bounded_and_labels_never_become_urls():
    pages = parse_directory(
        b"".join(lr_index_fixture(slug=f"route-{i}", label="Sintética") for i in range(5))
        + lr_index_fixture(slug="preferred", label="PF Sintética")
    )
    selected = candidates(pages, ["COMPAÑÍA SINTÉTICA ANDINA S.A.S."], None)
    assert len(selected) == 3
    assert all(page.url in {p.url for p in pages} for page in selected)
    assert candidates(pages, ["Unrelated issuer"], LR_INDEX_URL + "/not-in-catalog") == []
    assert candidates(pages, ["Unrelated issuer"], pages[1].url) == [pages[1]]
