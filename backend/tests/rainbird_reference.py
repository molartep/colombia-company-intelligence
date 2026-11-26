"""TEST ONLY independent reference evaluator. Never imported by app/production code."""

from datetime import date


def evaluate(scenario, as_of=date(2026, 11, 26)):
    # Independent month arithmetic deliberately does not import the production mapper.
    import calendar

    total = as_of.year * 12 + as_of.month - 1 - scenario.get("months", 24)
    year, month = divmod(total, 12)
    boundary = date(year, month + 1, min(as_of.day, calendar.monthrange(year, month + 1)[1]))
    complete = scenario.get("complete", True) and not scenario.get("excluded", False)
    valid = [c for c in scenario.get("contracts", []) if c.get("eligible", True)]
    dates = [date.fromisoformat(c["signature"]) for c in valid if c.get("signature")]
    temporal_complete = (
        complete and all(c.get("signature") for c in valid) and all(d <= as_of for d in dates)
    )
    exec_complete = complete and all(
        c.get("status", "liquidated") != "unknown"
        and c.get("observed", True)
        and not c.get("status_conflict", False)
        for c in valid
    )
    historical = any(d < boundary for d in dates)
    recent = any(boundary <= d <= as_of for d in dates)
    execution = any(
        c.get("status") == "execution"
        and c.get("observed", True)
        and not c.get("status_conflict", False)
        for c in valid
    )
    outcomes = [
        "documented" if valid else "no_scoped_matches" if complete else "undetermined",
        "documented"
        if historical
        else "not_observed_in_scope"
        if temporal_complete
        else "undetermined",
        "documented"
        if recent
        else "not_observed_in_scope"
        if temporal_complete
        else "undetermined",
        "reported" if execution else "not_observed_in_scope" if exec_complete else "undetermined",
    ]
    suff = [
        "sufficient" if x != "undetermined" else "incomplete" if not complete else "missing"
        for x in outcomes
    ]
    if any(c.get("status_conflict") for c in valid) and not execution:
        suff[3] = "contradictory"
    if scenario.get("stale"):
        suff = ["stale"] * 4
        outcomes[3] = "undetermined"
    return {"outcomes": outcomes, "sufficiency": suff}
