from app.companies.service import require_company, snapshot
from app.fiscal.mei import simulate_mei
from app.fiscal.models import Calculation
from app.fiscal.registry import select_rule
from app.fiscal.simples import simulate_simples


def calculate(db, company_id, account_id, request, context_snapshot=None):
    company = require_company(db, account_id, company_id)
    company_data = context_snapshot or snapshot(company).model_dump(mode="json")
    rule = select_rule(db, request.kind, request.period)
    status = "rule_unavailable" if rule is None else "unsupported_case"
    calculation = Calculation(
        company_id=company_id,
        rule_id=rule.id if rule else None,
        status=status,
        request=request.model_dump(mode="json"),
        company_snapshot=company_data,
        result=None,
        reason="Não há regra revisada para esta competência"
        if not rule
        else "Cenário não suportado",
        references=rule.references if rule else [],
    )
    if rule:
        missing = [] if request.conditions_confirmed else ["conditions_confirmed"]
        required = ["activity"] if request.kind == "mei" else ["rbt12", "revenue"]
        if request.kind == "simples" and rule.parameters.get("activities", {}).get(
            company_data["cnae"], {}
        ).get("factor_r"):
            required.append("payroll12")
        missing.extend(name for name in required if getattr(request, name) is None)
        if missing:
            calculation.status, calculation.reason = (
                "missing_inputs",
                "Dados obrigatórios: " + ", ".join(missing),
            )
        else:
            try:
                calculation.result = (simulate_mei if request.kind == "mei" else simulate_simples)(
                    request, rule.parameters, company_data["cnae"]
                )
                calculation.status, calculation.reason = "calculated", None
                calculation.result["rule_version"] = rule.version
            except ValueError:
                calculation.status, calculation.reason = (
                    "unsupported_case",
                    "Cenário fora da cobertura da regra revisada",
                )
    db.add(calculation)
    db.flush()
    return calculation
