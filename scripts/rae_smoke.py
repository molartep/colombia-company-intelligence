"""Explicit synthetic-only Rae smoke test; no company arguments or arbitrary input files.

Run from backend/: .venv/bin/python ../scripts/rae_smoke.py [--persist] [--refresh]
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from time import perf_counter
from uuid import UUID

import httpx
from sqlalchemy import select, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.core.config import get_settings
from app.db.session import Session
from app.integrations.rainbird.client import RaeClient, RaeError
from app.integrations.rainbird.mapper import ContractDiagnostics, fingerprint, map_facts
from app.models.government_involvement import InvolvementEvaluation
from app.schemas.government_involvement import InvolvementView
from app.schemas.secop import ContractView
from app.services.government_involvement import context


async def main(persist, refresh, live=False):
    settings = get_settings()
    if live:
        # Explicit command applies only to this fixed synthetic fixture.
        settings = settings.model_copy(
            update={
                "rae_enabled": True,
                "rae_execution_mode": "live_experimental",
            }
        )
    # Fixed repository-authored facts; cannot accept company IDs, NITs or external evidence.
    as_of = date(2026, 11, 26)
    contracts = [
        ContractView(
            contract_id="SYNTHETIC-RECENT",
            original_supplier_identifier="000000001",
            normalized_supplier_identifier="000000001",
            supplier_document_type="NIT",
            source_identifier="synthetic",
            status="in_execution",
            raw_status="En ejecución",
            signature_date=date(2026, 5, 14),
            retrieved_at=datetime(2026, 11, 26, 15, tzinfo=UTC),
            evidence_id=UUID("00000000-0000-0000-0000-000000000001"),
            source_url="https://www.datos.gov.co/d/jbjy-vk9h",
            source_link_label="Synthetic",
        )
    ]
    facts, refs, warnings = map_facts(
        contracts,
        as_of=as_of,
        months=settings.government_involvement_lookback_months,
        complete=True,
        stale=False,
        identity_verified=True,
        diagnostics={
            "SYNTHETIC-RECENT": ContractDiagnostics(
                signature_conflict=False,
                execution_status_conflict=False,
                value_conflict=False,
            )
        },
    )
    key = fingerprint(
        {
            "facts": facts,
            "refs": refs,
            "model": settings.rae_model_id,
            "version": settings.rae_model_version,
            "reference_mode": settings.rae_model_reference_mode,
            "engine": settings.rae_engine,
            "api_base": settings.rae_api_base_url,
            "policy": "government_involvement_v1",
            "date": str(as_of),
            "mode": settings.rae_execution_mode,
        }
    )

    async def run(session=None):
        if session:
            # Database lock protects this immutable cache key across CLI processes.
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": "rae:" + key},
            )
            if not refresh:
                cached = await session.scalar(
                    select(InvolvementEvaluation)
                    .where(
                        InvolvementEvaluation.input_fingerprint == key,
                        InvolvementEvaluation.created_at
                        > datetime.now(UTC) - timedelta(hours=settings.rae_cache_hours),
                    )
                    .order_by(InvolvementEvaluation.created_at.desc())
                    .limit(1)
                )
                if cached:
                    print(
                        json.dumps(
                            {"status": "cached", "evaluation_id": str(cached.id)}
                        )
                    )
                    return
        started = perf_counter()
        async with httpx.AsyncClient() as http:
            decisions, version = await RaeClient(settings, http).evaluate_synthetic(
                facts
            )
        expected = ["documented", "not_observed_in_scope", "documented", "reported"]
        if [d.outcome for d in decisions] != expected:
            raise RaeError("model_decision_mismatch")
        if any(d.evidence_status != "sufficient" for d in decisions):
            raise RaeError("model_sufficiency_mismatch")
        if any(d.evidence_tree is None or d.warnings for d in decisions):
            raise RaeError("evidence_validation_failed")
        elapsed = perf_counter() - started
        # Local provenance remains distinct from native Rae evidence, never fabricated
        # as a reasoning branch. This fixture's only contract is the local reference.
        result = InvolvementView(
            status="completed",
            engine={
                "provider": "Rainbird AI",
                "product": "Rae",
                "model_id": settings.rae_model_id,
                "model_version": version,
                "published_version": settings.rae_model_version,
                "model_reference_mode": settings.rae_model_reference_mode,
                "reasoning_engine": settings.rae_engine,
                "execution_mode": "live_experimental",
            },
            evaluation=context(as_of),
            decisions=decisions,
            input_fingerprint=key,
            source={"synthetic": True, "local_references": refs},
            diagnostics=warnings,
        )
        if session:
            session.add(
                InvolvementEvaluation(
                    input_fingerprint=key,
                    execution_mode="live_experimental",
                    payload=result.model_dump(mode="json"),
                )
            )
            await session.commit()
        print(
            json.dumps(
                {
                    "status": "completed",
                    "synthetic": True,
                    "round_trip_seconds": round(elapsed, 3),
                    "model_version": version,
                    "outcomes": {d.id: d.outcome for d in decisions},
                    "evidence_nodes": [d.evidence_tree_id for d in decisions],
                    "sufficiency": {d.id: d.evidence_status for d in decisions},
                    "diagnostic_counts": {
                        d.id: len(d.native_diagnostics) for d in decisions
                    },
                }
            )
        )

    try:
        if persist:
            async with Session() as session:
                await run(session)
        else:
            await run()
    except RaeError as exc:
        print(json.dumps({"status": "failed", "code": str(exc)}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Explicitly enable one synthetic-only live experiment",
    )
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.persist, args.refresh, args.live))
