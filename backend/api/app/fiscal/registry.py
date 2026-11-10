import json
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func, select

from app.fiscal.models import FiscalRule
from app.security import digest


def import_rule(db, data):
    payload = data.model_dump(mode="json")
    checksum = digest(json.dumps(payload, sort_keys=True))
    existing = db.scalar(
        select(FiscalRule).where(FiscalRule.kind == data.kind, FiscalRule.version == data.version)
    )
    if existing:
        if existing.checksum != checksum:
            raise HTTPException(409, "Versão da regra é imutável")
        return existing
    rule = FiscalRule(**payload, checksum=checksum)
    db.add(rule)
    db.flush()
    return rule


def select_rule(db, kind, period):
    return db.scalar(
        select(FiscalRule).where(
            FiscalRule.kind == kind,
            FiscalRule.status == "reviewed",
            FiscalRule.valid_from <= period,
            FiscalRule.valid_to >= period,
        )
    )


def review_rule(db, rule_id, reviewer: str, evidence: str):
    rule = db.get(FiscalRule, rule_id)
    if not rule:
        raise ValueError("Regra inexistente")
    if not reviewer.strip() or len(reviewer) > 120 or not evidence.strip() or len(evidence) > 512:
        raise ValueError("Revisor e evidência da revisão são obrigatórios")
    db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(rule.kind, 0))))
    db.refresh(rule)
    if rule.status == "reviewed":
        return rule
    overlap = db.scalar(
        select(FiscalRule.id)
        .where(
            FiscalRule.kind == rule.kind,
            FiscalRule.status == "reviewed",
            FiscalRule.valid_from <= rule.valid_to,
            FiscalRule.valid_to >= rule.valid_from,
        )
        .limit(1)
    )
    if overlap:
        raise ValueError("Vigência sobrepõe uma regra revisada")
    rule.status, rule.reviewed_by = "reviewed", reviewer.strip()
    rule.reviewed_at, rule.review_evidence = datetime.now(UTC), evidence.strip()
    db.flush()
    return rule
