import re
import unicodedata
from dataclasses import dataclass


class InvalidIdentifier(ValueError):
    pass


@dataclass(frozen=True)
class Nit:
    number: str
    verification_digit: str | None = None


def normalize_nit(value: str) -> Nit:
    """A DV is accepted only after an explicit hyphen; never truncate bare digits."""
    value = value.strip()
    if not re.fullmatch(r"[0-9][0-9.\s]*(?:\s*-\s*[0-9])?", value):
        raise InvalidIdentifier(
            "Use digits, optional dots/spaces, and an optional -verification digit."
        )
    parts = value.split("-")
    display = re.sub(r"\s", "", parts[0])
    if "." in display and not re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{3})+", display):
        raise InvalidIdentifier("Dots must separate groups of three digits.")
    number = display.replace(".", "")
    if not 5 <= len(number) <= 15:
        raise InvalidIdentifier("NIT must contain 5 to 15 digits; leading zeroes are preserved.")
    return Nit(number, parts[1].strip() if len(parts) == 2 else None)


def looks_like_nit(value: str) -> bool:
    return bool(re.match(r"^[\d.\s-]+$", value)) or bool(re.match(r"^\d.*-\d$", value))


def normalize_name(value: str) -> str:
    text = "".join(
        c for c in unicodedata.normalize("NFKD", value.upper()) if not unicodedata.combining(c)
    )
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    # Keep legal suffixes, but fold their dotted/spaced spellings deterministically.
    text = re.sub(r"\bS\s+A\s+S\b", "SAS", text)
    text = re.sub(r"\bS\s+A\b", "SA", text)
    return " ".join(text.split())
