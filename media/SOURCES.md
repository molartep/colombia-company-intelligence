# Featured records and attribution

Recorded through the application's existing API on 19 November 2026. Bounded response projections and capture provenance are retained in `fixtures/ecopetrol.json`; screenshots are actual React output. External strings are not translated or rewritten. SECOP status/entity/modality retain the application's established display-only uppercase treatment.

## Identity

- Legal entity: **ECOPETROL S A**; base NIT **899999068**; verification digit **1**.
- Registration-scoped company UUID: `b02c94b3-d93f-4d9f-8ab9-f0ff51d97052`.
- Bogotá registration `1291197`. Search results include similarly named subsidiaries; the walkthrough opens this specific registration, not a consolidated corporate group.
- RUES / Confecámaras, published through Colombia's open-data portal: https://www.datos.gov.co/d/c82u-588k
- Retained record retrieved `2026-11-19T23:08:39.589503Z`; dataset update `2026-11-06T20:49:30Z`. The profile's latest retrieval status is `failed_to_retrieve`; the captured source pane retains that warning. A previous source record is not evidence of a successful current request.

## Capital Markets

- Publisher: Superintendencia Financiera de Colombia; RNVE issuer **ECOPETROL S.A.**, code `036`, entity type `260`.
- The application's identity match is verified. Five registered securities are retained in the fixture, including `AO PEC ECOPETROL S.A.`. Issuer snapshot `61c660c9-76d7-4a8c-9dc2-51a5aca7e658`.
- Exact public report: https://www.superfinanciera.gov.co/ReportesInformacionRelevante/faces/B_simevRelevantes/G_valoresInscritos/repoValoresInscritos.xhtml?entidad=036&tipoEntidad=260
- Only issuer registration and registered-securities panels are captured. The unfeatured quote collection is omitted from the persisted fixture. No quote prices are featured; price redistribution rights were not established. Registration is not proof of current exchange trading, liquidity or investment suitability.

## Government Contracts

- Agencia Nacional de Contratación Pública — Colombia Compra Eficiente, **SECOP II — Contratos Electrónicos**, dataset `jbjy-vk9h`.
- Dataset: https://www.datos.gov.co/d/jbjy-vk9h
- API: https://www.datos.gov.co/resource/jbjy-vk9h.json
- Successful recorded check: `2026-11-19T04:53:42.042046Z`; source update `2026-11-18T23:36:18Z`. The Spanish UI renders these in Bogotá time, which can fall on the preceding calendar day.
- **7 verified unique supplier contracts**, **5 distinct buyers**, **COP 8,137,440,199**. COP follows the existing application currency policy, rather than a verified source currency field; no currency conversion is performed. Five contracts have zero reported value. Latest available signature: **2025-11-04**; two records lack signature dates. Counts include those records; signature-based annual charts retain a missing-date bucket.
- The two recorded contract pages contain all seven contracts. Every included record has `match_status=verified` and normalized supplier identifier `899999068`. Decimal reconciliation and uniqueness are checked in `scripts/validate.py`.
- Opened contract: `CO1.PCCNTR.8317598`, reported value **COP 602,150,472**. Its source link as recorded by the application:
  https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUID=CO1.NTC.8768612&isFromPublicArea=True&isModal=true&asPopupView=true
- The notice link is preserved as source evidence; it is not an invented contract URL. The videos do not demonstrate external-page availability or promise the notice is a standalone contract permalink.

## Rights and portrayal

The application, original graphic composition and original sample-free music use the repository's MIT license. Public-source records retain their originating publishers' terms; repository licensing does not relicense third-party data. The publisher names identify sources, not endorsements. The included company identity is a real research example and implies no affiliation with Ecopetrol or the publishers. No investment, fraud, ownership or comprehensive background-check conclusions are made.
