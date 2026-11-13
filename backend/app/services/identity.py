from app.core.normalization import Nit, normalize_name
from app.models.entities import Company
from app.schemas.api import MatchType


def classify(company: Company, query: str, nit: Nit | None) -> tuple[MatchType, list[str]]:
    if nit:
        if company.nit != nit.number:
            return "unresolved", ["NIT does not match."]
        if nit.verification_digit and company.verification_digit != nit.verification_digit:
            return "unresolved", [
                "NIT matches, but supplied verification digit is missing or conflicting."
            ]
        return "exact_nit", [
            "Exact NIT; identity remains scoped to an individual registration record."
        ]
    if company.legal_name.casefold().strip() == query.casefold().strip():
        return "exact_legal_name", ["Legal name matches the source spelling."]
    if company.normalized_name == normalize_name(query):
        return "normalized_name", [
            "Name matches after deterministic punctuation and diacritic normalization."
        ]
    if normalize_name(query) in company.normalized_name:
        return "partial_name", ["Normalized query occurs in the legal name."]
    return "unresolved", ["Candidate requires manual review."]
