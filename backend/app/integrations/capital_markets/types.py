from enum import StrEnum


class RegistrationStatus(StrEnum):
    ACTIVE = "registered_active"
    CANCELLED = "registered_cancelled"
    HISTORICAL = "historical"
    NOT_FOUND = "not_found_in_checked_source"
    UNKNOWN = "unknown"


class ListingStatus(StrEnum):
    LISTED = "verified_listed"
    DELISTED = "verified_delisted"
    NOT_FOUND = "not_found_in_checked_source"
    UNKNOWN = "unknown"


class SecurityCategory(StrEnum):
    COMMON = "common_equity"
    PREFERRED = "preferred_equity"
    EQUITY = "other_equity"
    BONDS = "corporate_bonds"
    PAPER = "commercial_paper"
    SECURITIZED = "securitized_instruments"
    COLLECTIVE = "collective_investment_instruments"
    DEBT = "other_debt"
    OTHER = "other_or_unknown"


class MatchMethod(StrEnum):
    NIT = "exact_nit"
    EXTERNAL = "verified_external_identifier"
    NAME = "exact_legal_name"
    NORMALIZED = "normalized_name"
    MANUAL = "manual_review"


class MatchStatus(StrEnum):
    VERIFIED = "verified"
    POTENTIAL = "potential"
    REJECTED = "rejected"


ISSUER_SOURCE = "sfc_rnve"
SECURITIES_SOURCE = "sfc_rnve_securities"
BVC_SOURCE = "bvc_listings"
DIRECTORY_URL = "https://www.superfinanciera.gov.co/SIMEV2/rnve/emisoresinscritosvigentes"
SECURITIES_BASE = (
    "https://www.superfinanciera.gov.co/ReportesInformacionRelevante/faces/"
    "B_simevRelevantes/G_valoresInscritos/repoValoresInscritos.xhtml"
)
CONVENTIONS_URL = (
    "https://www.superfinanciera.gov.co/ReportesInformacionRelevante/faces/"
    "C_otrosRelevantes/C_titulosInscritos/links/convencionesTitulos.xhtml"
)
