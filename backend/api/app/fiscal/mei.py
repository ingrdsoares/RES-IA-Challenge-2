from decimal import ROUND_HALF_UP, Decimal, localcontext

from app.fiscal.parameters import MeiParameters


def simulate_mei(inputs, parameters, cnae):
    rule = MeiParameters.model_validate(parameters)
    if not inputs.conditions_confirmed or inputs.activity is None:
        raise ValueError("Dados obrigatórios ausentes")
    if rule.activities.get(cnae) != inputs.activity:
        raise ValueError("Atividade não coberta por esta regra")
    with localcontext() as context:
        context.prec = 50
        components = {
            "inss": (rule.salary * rule.inss_rate).quantize(Decimal(".01"), rounding=ROUND_HALF_UP),
            "icms": rule.icms if inputs.activity in ("trade", "mixed") else Decimal(0),
            "iss": rule.iss if inputs.activity in ("services", "mixed") else Decimal(0),
        }
        return {
            "amount": f"{sum(components.values()):.2f}",
            "components": {key: f"{value:.2f}" for key, value in components.items()},
            "assumptions": rule.limitations,
            "mode": "simulation",
            "rounding": "ROUND_HALF_UP",
        }
