import json

REFERENCES = """- Lin (2004): https://aclanthology.org/W04-1013/
- Zhang et al. (2020): https://arxiv.org/abs/1904.09675
- Databricks:
https://docs.databricks.com/aws/en/agents/tutorials/ai-cookbook/evaluate-define-quality
- BERTimbau: https://huggingface.co/neuralmind/bert-base-portuguese-cased"""


def render(snapshot, summary, comparison, images):
    config = summary["config"]
    comparison_note = (
        "Disponível em Comparação e comparison.json; diferenças B − A, bootstrap pareado."
        if comparison
        else "Não realizada: uma única execução analisada."
    )
    text = f"""# Relatório de avaliação de RAG

## 1. Objetivo
Avaliar similaridade textual e semântica de respostas do RAG frente a referências revisadas.

## 2. Metodologia
ROUGE-L usa LCS da biblioteca rouge-score, tokenizer Unicode NFC/casefold com acentos e sem
stemming. BERTScore usa embeddings contextuais, configuração e revisão registradas nos
artefatos. Respostas operacionais inválidas não recebem zero artificial.

## 3. Perguntas e categorias
Perguntas únicas selecionadas: {summary["total_questions"]}. Tentativas planejadas:
{summary["planned_attempts"]}. A distribuição consta de summary.json e da aba Categorias.

## 4. Configuração
Execução: {snapshot.manifest.run_id}. Fingerprint: {snapshot.metric_fingerprint}.
Os detalhes do RAG, corpus, modelos e dependências estão em Configuração/manifest.json/results.json.

## 5. ROUGE-L
Resumo principal (comportamento esperado answer):
{json.dumps(summary["primary"]["metrics"]["rouge_l"], ensure_ascii=False)}.

## 6. BERTScore
Resumo principal: {json.dumps(summary["primary"]["metrics"]["bert_score"], ensure_ascii=False)}.
Valores ausentes indicam ausência de observações válidas ou falha identificada; não são nota zero.

## 7. Intervalos de confiança
Bootstrap percentil por pergunta, {config["bootstrap"]} reamostragens com reposição, seed
{config["seed"]}, IC de 95%. Sem pelo menos duas perguntas válidas, IC e desvio amostral são
indisponíveis. IC degenerado não prova ausência de incerteza populacional.

## 8. Variabilidade
Repetições são agregadas por pergunta antes da análise. Desvios dentro da pergunta são
apresentados separadamente; repetições não aumentam o número de perguntas independentes.

## 9. Dimensionamento
n = ceil((1,96*s/E)^2), E={config["margin"]}. Origem de s: {summary["sample_size_origin"]}.
Requer independência, representatividade e aproximação normal. Pilotos pequenos e variância
observada zero limitam a estimativa. Disponibilidade numérica não é garantia de suficiência
científica.

## 10. Comparação entre versões
{comparison_note}

## 11. Limitações
Similaridade não é porcentagem de correção factual e não há limiar universal de aprovação. A
seleção por respostas bem-sucedidas pode introduzir viés; verificar falhas e cobertura por
métrica. A avaliação não comprova adequação fiscal, correção de abstenções ou identidade do
conteúdo da coleção. A equipe deve manter corpus e referências congelados. O uso do conjunto
final para ajustes manuais deve ser evitado pela equipe. Sources são os trechos fornecidos ao
gerador, não todos os hits brutos. Correção de abstenção exige adjudicação independente.
Truncamento explícito de BERT, quando habilitado, avalia apenas parte do texto e fica
registrado.

## 12. Considerações finais
Os valores apresentados descrevem somente as perguntas efetivamente pontuadas. Não há conclusão
automática de aprovação. Para conjuntos sem pontuações, a análise de qualidade permanece
indisponível.

## Referências
{REFERENCES}
"""
    if images:
        text += "\n## Gráficos\n" + "".join(f"\n![{p.stem}]({p.name})\n" for p in images)
    else:
        text += "\nGráficos indisponíveis: observações insuficientes.\n"
    return text
