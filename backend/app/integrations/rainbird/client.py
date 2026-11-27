"""Documented REST session API; bounded synthetic and authorized company inference.

References: docs.rainbird.ai/rainbird/developer-docs/api-reference/{decisions,evidence}
"""

import asyncio
import json
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import Settings
from app.integrations.rainbird.mapper import DECISIONS
from app.schemas.government_involvement import Decision, EvidenceNode


class RaeError(Exception):
    """Safe machine code only; never expose request bodies, URLs or vendor errors."""


class StartResponse(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    kmVersion: dict[str, Any] | None = None


class ResultFact(BaseModel):
    model_config = ConfigDict(extra="ignore")
    subject: str
    object: str
    factID: str = Field(min_length=1, max_length=300)
    certainty: float = Field(ge=1, le=100)
    relationship: str | None = None
    relationshipType: str | None = None


class ResultResponse(BaseModel):
    result: list[ResultFact]
    sid: str | None = None


def normalize_evidence(raw: dict[str, Any], *, limit: int = 500) -> EvidenceNode:
    """Normalize native evidence, including expression contributors and unresolved branches."""
    count = 0

    def visit(node: dict[str, Any], depth: int = 0) -> EvidenceNode:
        nonlocal count
        count += 1
        if count > limit or depth > 30:
            raise RaeError("evidence_limit")
        fact_id = node.get("factID")
        if not isinstance(fact_id, str):
            raise RaeError("invalid_evidence")
        if node.get("evidenceError"):
            return EvidenceNode(id=fact_id, kind="unresolved", label="evidence_unavailable")
        if node.get("repeated"):
            return EvidenceNode(id=fact_id, kind="fact", label=fact_id)
        if isinstance(node.get("evidence"), dict):
            return visit(node["evidence"], depth + 1)
        fact = node.get(
            "fact",
            {
                key: node[key]
                for key in ("subject", "relationship", "object", "certainty")
                if key in node
            },
        )
        if not isinstance(fact, dict):
            raise RaeError("invalid_evidence")

        def scalar(value: Any) -> str:
            if isinstance(value, dict):
                value = value.get("value", value.get("type", value))
            return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)

        label = (
            " → ".join(scalar(fact[key]) for key in ("subject", "relationship", "object"))
            if all(key in fact for key in ("subject", "relationship", "object"))
            else json.dumps(fact, ensure_ascii=False)
            if fact
            else fact_id
        )
        if len(label) > 10000:
            raise RaeError("invalid_evidence")
        result = EvidenceNode(
            id=fact_id, kind="rule" if node.get("source") == "rule" else "fact", label=label
        )
        rule = node.get("rule", {})
        if not isinstance(rule, dict):
            raise RaeError("invalid_evidence")
        for condition in rule.get("conditions", []):
            if not isinstance(condition, dict):
                raise RaeError("invalid_evidence")
            if "factID" in condition:
                result.children.append(visit(condition, depth + 1))
            expression = condition.get("expression", {})
            for function in expression.get("functions", {}).values():
                for contributor in function.get("facts", []):
                    result.children.append(visit(contributor, depth + 1))
        return result

    try:
        return visit(raw)
    except (TypeError, AttributeError, ValueError, RecursionError) as exc:
        raise RaeError("invalid_evidence") from exc


class RaeClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings = settings
        self.client = client

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = {
            "X-API-Key": self.settings.rae_api_key or "",
            "x-rainbird-engine": self.settings.rae_engine,
        }
        if self.settings.rae_evidence_key:
            headers["x-evidence-key"] = self.settings.rae_evidence_key
        try:
            async with self.client.stream(
                method,
                self.settings.rae_api_base_url + path,
                headers=headers,
                timeout=self.settings.rae_request_timeout_seconds,
                follow_redirects=False,
                **kwargs,
            ) as response:
                if response.status_code != 200:
                    code = {
                        400: "unsupported_request",
                        401: "invalid_credentials",
                        403: "access_denied",
                        404: "model_not_found",
                        429: "rate_limited",
                        413: "evidence_limit",
                    }.get(response.status_code, "api_unavailable")
                    raise RaeError(code)
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 2_000_000:
                        raise RaeError("response_limit")
                data = json.loads(body)
                if not isinstance(data, dict):
                    raise RaeError("invalid_response")
                return data
        except httpx.TimeoutException as exc:
            raise RaeError("timeout") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise RaeError("invalid_response") from exc

    async def _query(self, session: str, relationship: str) -> list[ResultFact]:
        raw = await self._request(
            "POST",
            f"/{quote(session, safe='')}/query",
            json={"subject": "evaluation", "relationship": relationship},
        )
        if "question" in raw:
            # Headless inference never guesses answers to missing input facts.
            raise RaeError("unresolved_question")
        response = ResultResponse.model_validate(raw)
        if response.sid is not None and response.sid != session:
            raise RaeError("invalid_session")
        if len(response.result) > 5000:
            raise RaeError("response_limit")
        if any(
            f.subject != "evaluation" or (f.relationship or f.relationshipType) != relationship
            for f in response.result
        ):
            raise RaeError("unexpected_decision")
        return response.result

    async def _evidence(
        self,
        fact_id: str,
        session: str,
        cache: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        # The published RBX guide guarantees evidence for inferred :RF: answers.
        if ":RF:" not in fact_id:
            return None
        if fact_id in cache:
            return cache[fact_id]
        path = f"/analysis/evidence/{quote(fact_id, safe='')}/{quote(session, safe='')}"
        try:
            tree = await self._request("GET", path, params={"full": "true"})
        except RaeError as exc:
            if str(exc) not in ("evidence_limit", "unsupported_request"):
                raise
            tree = await self._request("GET", path)
        if tree.get("factID") != fact_id:
            raise RaeError("invalid_evidence")

        seen: set[str] = set()

        async def expand(node: dict[str, Any], depth: int) -> None:
            if depth > 30:
                raise RaeError("evidence_limit")
            current = node.get("factID")
            if isinstance(current, str):
                if current in seen:
                    return
                seen.add(current)
            if len(seen) > 500:
                raise RaeError("evidence_limit")
            rule = node.get("rule", {})
            if not isinstance(rule, dict):
                raise RaeError("invalid_evidence")
            conditions = rule.get("conditions", [])
            if not isinstance(conditions, list):
                raise RaeError("invalid_evidence")
            references = []
            for condition in conditions:
                if not isinstance(condition, dict):
                    raise RaeError("invalid_evidence")
                if "factID" in condition:
                    references.append(condition)
                expression = condition.get("expression", {})
                for function in expression.get("functions", {}).values():
                    references.extend(function.get("facts", []))
            for ref in references:
                if not isinstance(ref, dict) or not isinstance(ref.get("factID"), str):
                    raise RaeError("invalid_evidence")
                child_id = ref["factID"]
                if ref.get("evidenceError") or ref.get("repeated") or child_id.startswith("WA:XX"):
                    continue
                if child_id in seen:
                    ref["repeated"] = True
                    continue
                nested = ref.get("evidence")
                if nested is None:
                    if len(cache) >= 500:
                        raise RaeError("evidence_limit")
                    if child_id in cache:
                        nested = cache[child_id]
                    else:
                        child_path = (
                            f"/analysis/evidence/{quote(child_id, safe='')}/"
                            f"{quote(session, safe='')}"
                        )
                        try:
                            nested = await self._request("GET", child_path)
                        except RaeError as exc:
                            if str(exc) == "model_not_found":
                                ref["evidenceError"] = "evidence_unavailable"
                                continue
                            raise
                        if nested.get("factID") != child_id:
                            raise RaeError("invalid_evidence")
                        cache[child_id] = nested
                    # Copy to avoid cycles in retained JSON when vendor facts share references.
                    nested = json.loads(json.dumps(nested))
                    ref["evidence"] = nested
                if not isinstance(nested, dict):
                    raise RaeError("invalid_evidence")
                await expand(nested, depth + 1)

        try:
            await expand(tree, 0)
        except (TypeError, AttributeError, ValueError, RecursionError) as exc:
            raise RaeError("invalid_evidence") from exc
        cache[fact_id] = tree
        return tree

    async def evaluate_synthetic(self, facts: list[dict[str, Any]]) -> tuple[list[Decision], str]:
        if self.settings.rae_execution_mode != "live_experimental":
            raise RaeError("not_configured")
        return await self._evaluate(facts)

    async def evaluate_company(self, facts: list[dict[str, Any]]) -> tuple[list[Decision], str]:
        if (
            not self.settings.rae_company_processing_authorized
            or self.settings.rae_execution_mode != "live"
        ):
            raise RaeError("company_processing_not_authorized")
        return await self._evaluate(facts, include_witnesses=True)

    async def _evaluate(
        self,
        facts: list[dict[str, Any]],
        *,
        include_witnesses: bool = False,
    ) -> tuple[list[Decision], str]:
        s = self.settings
        if not (
            s.rae_enabled
            and s.rae_execution_mode in ("live_experimental", "live")
            and s.rae_api_key
            and s.rae_model_id
            and (s.rae_model_reference_mode == "published_build" or s.rae_model_version is not None)
        ):
            raise RaeError("not_configured")
        # Prevent derived conclusions from ever being injected as input overrides.
        forbidden = set(DECISIONS) | {f"{d}_sufficiency" for d in DECISIONS}
        if any(f.get("relationship") in forbidden for f in facts):
            raise RaeError("derived_input_forbidden")
        try:
            async with asyncio.timeout(s.rae_request_timeout_seconds):
                # A wizard build is addressed by its published kmID, not an assumed
                # legacy integer version. Never request useDraft.
                params = (
                    {"version": s.rae_model_version}
                    if s.rae_model_reference_mode == "version"
                    else {}
                )
                started = StartResponse.model_validate(
                    await self._request(
                        "GET",
                        f"/start/{quote(s.rae_model_id, safe='')}",
                        params=params,
                    )
                )
                if started.kmVersion is not None:
                    version = started.kmVersion.get("id")
                    if not isinstance(version, str) or not version:
                        raise RaeError("invalid_model_version")
                elif s.rae_model_reference_mode == "published_build":
                    # Explicit build reference, never fabricated returned version metadata.
                    version = f"published-build:{s.rae_model_id}"
                else:
                    raise RaeError("invalid_model_version")
                for index in range(0, len(facts), 250):
                    batch = facts[index : index + 250]
                    if len(json.dumps(batch).encode()) > 100_000:
                        raise RaeError("request_limit")
                    injected = await self._request(
                        "POST",
                        f"/{quote(started.id, safe='')}/inject",
                        json=batch,
                    )
                    if injected.get("result") != "OK":
                        raise RaeError("injection_failed")
                common = await self._query(started.id, "common_diagnostic")
                decisions = []
                evidence_cache: dict[str, dict[str, Any]] = {}
                for dimension in DECISIONS:
                    results = await self._query(started.id, dimension)
                    if len(results) != 1:
                        raise RaeError("unresolved_decision")
                    result = results[0]
                    allowed = (
                        {"reported", "not_observed_in_scope", "undetermined"}
                        if dimension == "currently_reported_execution"
                        else {"documented", "no_scoped_matches", "undetermined"}
                        if dimension == "direct_participation"
                        else {"documented", "not_observed_in_scope", "undetermined"}
                    )
                    if result.object not in allowed:
                        raise RaeError("unexpected_decision")
                    suff = await self._query(started.id, f"{dimension}_sufficiency")
                    if len(suff) != 1:
                        raise RaeError("unresolved_sufficiency")
                    diagnostics = common + await self._query(started.id, f"{dimension}_diagnostics")
                    aliases = []
                    if include_witnesses and result.object in ("documented", "reported"):
                        relationship = {
                            "direct_participation": "eligible_contract",
                            "historical_participation": "historical_witness",
                            "recent_participation": "recent_witness",
                            "currently_reported_execution": "execution_witness",
                        }[dimension]
                        aliases = [f.object for f in await self._query(started.id, relationship)]
                        if not aliases:
                            raise RaeError("missing_supporting_contracts")
                    tree = await self._evidence(result.factID, started.id, evidence_cache)
                    suff_tree = await self._evidence(suff[0].factID, started.id, evidence_cache)
                    normalized = normalize_evidence(tree) if tree else None
                    warnings = []
                    if normalized and suff_tree:
                        normalized.children.append(normalize_evidence(suff_tree))
                    if tree is None or suff_tree is None:
                        warnings.append("native_evidence_not_available")

                    def incomplete(node: EvidenceNode) -> bool:
                        return node.kind == "unresolved" or any(
                            incomplete(c) for c in node.children
                        )

                    if normalized and incomplete(normalized):
                        warnings.append("native_evidence_incomplete")
                    decisions.append(
                        Decision.model_validate(
                            dict(
                                id=dimension,
                                supporting_aliases=aliases,
                                outcome=result.object,
                                evidence_status=suff[0].object,
                                evidence_tree_id=result.factID if tree else None,
                                evidence_tree=normalized,
                                native_evidence={"decision": tree, "sufficiency": suff_tree},
                                native_diagnostics=[
                                    d.model_dump(exclude_none=True) for d in diagnostics
                                ],
                                warnings=warnings,
                            )
                        )
                    )
                return decisions, version
        except (ValidationError, KeyError) as exc:
            raise RaeError("invalid_response") from exc
        except TimeoutError as exc:
            raise RaeError("timeout") from exc
