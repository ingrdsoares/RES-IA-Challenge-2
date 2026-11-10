from decimal import ROUND_HALF_UP, Decimal, localcontext

from app.fiscal.parameters import SimplesParameters


def simulate_simples(inputs, parameters, cnae):
    rule = SimplesParameters.model_validate(parameters)
    activity = rule.activities.get(cnae)
    if (
        not activity
        or not inputs.conditions_confirmed
        or inputs.rbt12 is None
        or inputs.revenue is None
    ):
        raise ValueError("Dados ou atividade não cobertos")
    if inputs.rbt12 <= 0:
        raise ValueError("Receita acumulada zero exige regra específica")
    if activity.factor_r and inputs.payroll12 is None:
        raise ValueError("Folha obrigatória")
    with localcontext() as context:
        context.prec = 50
        factor = inputs.payroll12 / inputs.rbt12 if activity.factor_r else None
        annex = (
            ("III" if factor >= rule.factor_r_threshold else "V")
            if activity.factor_r
            else activity.annex
        )
        band = next((band for band in rule.annexes[annex] if inputs.rbt12 <= band.upper), None)
        if not band:
            raise ValueError("Receita fora das faixas revisadas")
        rate = ((inputs.rbt12 * band.rate - band.deduction) / inputs.rbt12).quantize(
            Decimal(1).scaleb(-rule.rate_places), rounding=ROUND_HALF_UP
        )
        if rate < 0 or rate > 1:
            raise ValueError("Regra não cobre esta receita")
        amount = (inputs.revenue * rate).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        components = {
            key: (amount * share).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
            for key, share in band.shares.items()
        }
        if components:
            target = max(sorted(components), key=lambda key: band.shares[key])
            components[target] += amount - sum(components.values())
        return {
            "amount": f"{amount:.2f}",
            "annex": annex,
            "effective_rate": str(rate),
            "factor_r": str(factor) if factor is not None else None,
            "components": {key: f"{value:.2f}" for key, value in components.items()},
            "assumptions": rule.limitations,
            "mode": "simulation",
            "rounding": "ROUND_HALF_UP",
            "rate_places": rule.rate_places,
        }
