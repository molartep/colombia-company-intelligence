import pytest

from app.core.normalization import InvalidIdentifier, normalize_name, normalize_nit
from app.models.entities import Company
from app.services.identity import classify


@pytest.mark.parametrize(
    ("value", "number", "digit"),
    [
        ("900.123.456-7", "900123456", "7"),
        (" 000 123 456 - 7 ", "000123456", "7"),
        ("9001234567", "9001234567", None),
        ("000123456", "000123456", None),
    ],
)
def test_nit(value, number, digit):
    result = normalize_nit(value)
    assert (result.number, result.verification_digit) == (number, digit)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "NIT 900123456",
        "900123456-12",
        "900/123456",
        "-900123456",
        "123",
        "１２３４５６",
        "900123456--1",
        "900..123.456",
        "9.00123.456",
    ],
)
def test_bad_nit(value):
    with pytest.raises(InvalidIdentifier):
        normalize_nit(value)


def test_name():
    assert normalize_name("  Compañía Ágil S.A.S. ") == "COMPANIA AGIL SAS"
    assert normalize_name("Ágil S.A.") == normalize_name("Agil SA")
    assert normalize_name("Agil Ltda.") == "AGIL LTDA"
    assert normalize_name("Agil SAS") != normalize_name("Agil SA")


@pytest.mark.parametrize(
    ("query", "nit", "expected"),
    [
        ("000123456", "000123456", "exact_nit"),
        ("000123456-9", "000123456-9", "unresolved"),
        ("COMPAÑÍA SINTÉTICA ANDINA S.A.S.", None, "exact_legal_name"),
        ("compania sintetica andina sas", None, "normalized_name"),
        ("andina", None, "partial_name"),
        ("unrelated", None, "unresolved"),
    ],
)
def test_matching(record, query, nit, expected):
    company = Company(
        legal_name=record["razon_social"],
        normalized_name=normalize_name(record["razon_social"]),
        nit=record["nit"],
        verification_digit="7",
    )
    assert classify(company, query, normalize_nit(nit) if nit else None)[0] == expected
