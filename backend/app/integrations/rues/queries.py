"""Controlled SoQL relevance expressions, evaluated before source LIMIT/OFFSET.

These expressions affect ordering only; the existing case/space-insensitive candidate
filter is retained. All user text is quoted as a literal, never inserted as SoQL code.
"""

from app.core.normalization import compact_name, normalize_name


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def normalized_words() -> str:
    expression = "unaccent(upper(razon_social))"
    # Only verified literal text functions are used (regex_replace is not supported).
    for separator in ".,-/&'\"()_":
        expression = f"replace({expression}, {literal(separator)}, ' ')"
    # Collapse runs of up to 16 spaces without an unsupported regex operation.
    for _ in range(4):
        expression = f"replace({expression}, '  ', ' ')"
    return f"trim({expression})"


WORDS = normalized_words()
COMPACT = f"replace({WORDS}, ' ', '')"
NAME_TIEBREAK = f"{WORDS} ASC, upper(razon_social) ASC, :id ASC"


def name_order(name: str) -> str:
    phrase = normalize_name(name)
    compact = compact_name(name)
    # The first true CASE condition wins. Whole words precede word prefixes, so
    # ZULU / ZULU SAS / GLOBAL ZULU rank ahead of ZULUAGA or AZULU.
    tiers = [
        f"trim(upper(razon_social)) = {literal(name.upper().strip())}, 0",
        f"{COMPACT} = {literal(compact)}, 1",
        f"{WORDS} like {literal(phrase + ' %')}, 2",
        f"({WORDS} like {literal('% ' + phrase + ' %')} OR "
        f"{WORDS} like {literal('% ' + phrase)}), 3",
        f"({COMPACT} like {literal(compact + '%')} OR "
        f"{WORDS} like {literal('% ' + phrase + '%')}), 4",
        "true, 5",
    ]
    return f"case({', '.join(tiers)}) ASC, {NAME_TIEBREAK}"


def nit_order(verification_digit: str | None = None) -> str:
    if verification_digit is not None:
        return (
            f"case(digito_verificacion = {literal(verification_digit)}, 0, true, 1) ASC, "
            f"{NAME_TIEBREAK}"
        )
    return NAME_TIEBREAK
