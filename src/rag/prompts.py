"""
Templates de Prompts e Guardrails Anti-Alucinação para o Sócio Digital.
Frente: Ciência de Dados (Jhessica).
Projeto: Sócio Digital — Copiloto de Gestão Fiscal para Pequenos Negócios.
"""

DISCLAIMER_CRC_PADRAO = (
    "Aviso Regulatório: Esta análise tem finalidade didática e de organização prévia. "
    "A apuração e transmissão oficial das declarações fiscais no PGDAS-D e e-CAC devem ser validadas "
    "junto a um profissional contábil legalmente habilitado com registro no CRC (Decreto-Lei nº 9.295/1946)."
)

PROMPT_ABSTENCAO_MOTIVO = {
    "fora_de_escopo": "A questão aborda matéria fora do escopo de MEI e Simples Nacional ou envolve planejamento elisivo controvertido.",
    "sem_base_oficial": "Não foi localizada fundamentação oficial suficiente na base legal indexada para assegurar uma resposta com 100% de precisão.",
    "litigio_judicial": "A situação relatada envolve execução fiscal contenciosa ou litígio judicial, demandando assistência de advogado tributarista e contador perito.",
}
