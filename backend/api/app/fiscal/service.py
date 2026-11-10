from app.companies.service import require_company, snapshot
from app.fiscal.models import Calculation
from app.fiscal.registry import select_rule


def calculate(db, company_id, account_id, request):
    company = require_company(db, account_id, company_id)
    rule = select_rule(db, request.kind, request.period)
    status = "rule_unavailable" if rule is None else "unsupported_case"
    calculation = Calculation(
        company_id=company_id,
        rule_id=rule.id if rule else None,
        status=status,
        request=request.model_dump(mode="json"),
        company_snapshot=snapshot(company).model_dump(mode="json"),
        result=None,
        reason="Não há regra revisada para esta competência"
        if not rule
        else "Cenário não suportado",
        references=rule.references if rule else [],
    )
    db.add(calculation)
    db.flush()
    return calculation
