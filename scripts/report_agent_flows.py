"""Render the real-flow observations and explicit human/model-assisted review as Markdown."""

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results", type=Path, default=Path("docs/avaliacao/2026-11-17-bateria-50-agentes.json")
    )
    parser.add_argument(
        "--reviews", type=Path, default=Path("docs/avaliacao/2026-11-17-bateria-50-revisao.json")
    )
    parser.add_argument(
        "--dataset", type=Path, default=Path("backend/evaluation/data/agent_flow_50.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("docs/avaliacao/2026-11-17-bateria-50-agentes.md")
    )
    args = parser.parse_args()
    data = json.loads(args.results.read_text())
    reviews = json.loads(args.reviews.read_text())
    dataset = json.loads(args.dataset.read_text())
    cases = {case["id"]: case for case in data["cases"]}
    classifications = Counter(
        reviews[c["id"]]["classification"] for c in data["cases"] if c["id"] in reviews
    )
    states = Counter(c.get("operation", {}).get("status", "execution_error") for c in data["cases"])
    meta = data["metadata"]
    lines = [
        "# Bateria de 50 fluxos reais dos agentes",
        "",
        f"Executados: **{len(cases)}/50**. Revisados qualitativamente: **{sum(classifications.values())}/50**.",
        "",
        "## Ambiente e critério",
        "",
        f"- Modelo real: `{meta['model']}`; embeddings: `{meta['embedding_model']}`. Código base: `{meta['revision']}`.",
        f"- Catálogo: `{meta['catalog']}`. Apenas três versões estão indexadas, com {meta['indexed_chunks']} trechos; os outros 4.023 documentos não participaram da recuperação.",
        "- Fontes: acervo real do projeto; sem normas demonstrativas. Empresas, guia declarada e conta são fixtures fictícias de avaliação.",
        "- Vigência ignorada apenas neste experimento, conforme autorização. Isso não verifica atualidade/aplicabilidade tributária.",
        "- Busca densa, limiar 0,3, até cinco trechos, sem reranker. Inferência e serviços de domínio reais; chamadas HTTP em processo via TestClient e executor acionado diretamente, sem testar transporte RQ neste lote.",
        "- Cada caso inicia conversa nova. Nenhuma regra fiscal foi publicada pelo avaliador. A guia declarada de 2026-10 não comprova pagamento.",
        "- Classificação qualitativa: adequada, parcial, incorreta ou falha técnica. Revisão técnica assistida pelo agente, comparando pergunta, resposta e trechos disponíveis; não é avaliação fiscal independente.",
        "- Estado de execução `succeeded` não equivale a resposta correta. Solicitações de dados são avaliadas pelo contrato estruturado, pois podem não produzir mensagem textual.",
        "",
        "## Resultado agregado",
        "",
        f"Estados técnicos: `{dict(states)}`.",
        "",
        f"Classificações revisadas: `{dict(classifications)}`.",
        "",
        "| Avaliação | Casos |",
        "| --- | ---: |",
        *[
            f"| {label} | {classifications.get(label, 0)} |"
            for label in ("adequada", "parcial", "incorreta", "falha técnica")
        ],
        "",
        "Adequada: atende ao pedido central e respeita as fontes/limites. Parcial: omissão relevante, esclarecimento desnecessário, fundamento insuficiente ou abstenção que deixa de responder tema esperado. Incorreta: afirmação ou fórmula errada/extrapolação sem suporte. Falha técnica: nenhuma resposta publicada por falha da operação. Uma abstenção é adequada quando a pergunta exige fonte fora da cobertura (por exemplo, ISS municipal ou julgamento recente do CARF).",
        "",
        "Três das avaliações adequadas são solicitações estruturadas de competência (A28, A41, A42), não respostas completas. O quarto esclarecimento (A21) foi desnecessário. Os casos não receberam uma segunda mensagem com os dados solicitados: este lote avalia a primeira interação de cada pergunta.",
        "",
        f"Tempo acumulado dos casos: {sum(c['duration_seconds'] for c in data['cases']):.2f} s; mediana: {statistics.median(c['duration_seconds'] for c in data['cases']):.2f} s; maior duração: {max(c['duration_seconds'] for c in data['cases']):.2f} s.",
        "",
        "## Principais achados",
        "",
        "1. **Erros de conteúdo publicados:** A06 contradiz o trecho sobre empregado; A07 generaliza elegibilidade de atividades; A23 altera a fórmula da alíquota efetiva. Ter um ID de citação válido não impediu esses erros.",
        "2. **Citações inconsistentes bloqueiam respostas:** A11, A13, A14, A19, A20 e A43 chegaram à síntese, mas os marcadores inline não corresponderam aos IDs declarados. O bloqueio evita publicação inconsistente, mas a recuperação para o usuário não funciona neste caminho.",
        "3. **Saídas inválidas nos agentes:** A31 e A36 falharam no fiscal; A39 falhou no plano. A telemetria registra invalid_agent_result, sem detalhar qual campo falhou. A36 foi o caso mais lento.",
        "4. **Recuperação e uso do contexto:** há abstenções dentro dos temas esperados da LC 123; A12 usa trecho transitório para uma questão de abertura de empresa e A18 usa parcelamento para justificar permanência no regime. A23 errou mesmo com a fórmula no trecho recuperado.",
        "5. **Fricção e utilidade:** A21 pede competência para definição geral de RBT12; A37 não produz as duas ações pedidas; A38 não explica fator R nem lista entradas. O planejamento só foi executado em A37 e A40, e só A40 publicou ação.",
        "6. **Proteções que funcionaram:** A27 não inventou imposto sem regra revisada; A29/A30/A32/A35 não afirmaram comprovação indevida; A46/A49 não publicaram a confirmação forçada; A47 não criou artigo; A48 não orientou ocultação. Os planos internos de A46/A49 mostram suscetibilidade à premissa do usuário: a proteção observada no resultado fiscal vem da renderização determinística, não de uma garantia de raciocínio correto do supervisor.",
        "7. **Nenhuma tarefa criada automaticamente:** todos os casos mantiveram tasks_created=0. Não houve emissão de certidão, publicação de regras fiscais reais ou confirmação oficial simulada.",
        "",
        "## Conclusão da bateria",
        "",
        "A qualidade deste lote é insuficiente para considerar a orientação fiscal autônoma validada. Os 21 casos adequados não representam uma taxa geral de acerto do produto: o roteiro é dirigido, a cobertura vetorial tem três versões, a vigência foi ignorada e a revisão não foi independente. A prioridade indicada pelos resultados é corrigir interpretação/aderência à fonte, composição das citações, recuperação de falhas de contrato, distinção entre dúvida geral e cálculo particular e planejamento com suporte. O código do produto permaneceu fixo durante a medição; este trabalho não aplica essas correções.",
        "",
        "## Resumo dos casos",
        "",
        "| Caso | Tema | Execução | Avaliação | Segundos |",
        "| --- | --- | --- | --- | --- |",
    ]
    for spec in dataset:
        c = cases.get(spec["id"])
        review = reviews.get(spec["id"], {})
        lines.append(
            f"| {spec['id']} | {spec['category']} | {c.get('operation', {}).get('status', 'erro') if c else 'pendente'} | {review.get('classification', 'pendente')} | {c.get('duration_seconds', '—') if c else '—'} |"
        )
    lines += ["", "## Perguntas, respostas e avaliação", ""]
    for spec in dataset:
        c = cases.get(spec["id"])
        review = reviews.get(spec["id"], {})
        lines += [
            f"### {spec['id']} — {spec['category']}",
            "",
            f"**Pergunta:** {spec['question']}",
            "",
            f"**Perfil:** {spec['profile']}. **Esperado:** {spec['expected']}",
            "",
        ]
        if not c:
            lines += ["Execução pendente.", ""]
            continue
        response = c.get("response")
        operation = c.get("operation", {})
        lines += [
            f"**Execução:** `{operation.get('status', 'erro')}`; estado da resposta: `{(response or {}).get('status', 'sem mensagem')}`; {c['duration_seconds']} s.",
            "",
            f"**Agentes:** {', '.join(a['name'] + ' (' + a['status'] + ')' for a in c.get('agents', [])) or 'nenhuma etapa LLM executada'}.",
            "",
            "**Resposta observada:**",
            "",
        ]
        text = (
            response["text"]
            if response
            else "Sem mensagem textual. Resultado estruturado: "
            + json.dumps(operation.get("result", c.get("execution_error")), ensure_ascii=False)
        )
        lines += ["> " + part for part in text.splitlines()] + [""]
        if response and response.get("actions"):
            lines += (
                ["**Ações propostas:**", ""]
                + ["- " + action["title"] for action in response["actions"]]
                + [""]
            )
        if response and response.get("citations"):
            lines += ["**Fontes fornecidas à resposta:**", ""]
            for source in response["citations"]:
                lines += [
                    f"- [{source['title']}]({source['official_url']}) — âncora `{source['anchor_id']}`, versão `{source['version_id']}`."
                ]
            lines += [""]
        lines += [
            f"**Avaliação:** {review.get('classification', 'pendente')}. {review.get('reason', 'Revisão qualitativa ainda não realizada.')}",
            "",
        ]
        lines += [
            "<details><summary>Saídas estruturadas dos agentes</summary>",
            "",
            "```json",
            json.dumps(
                [
                    {
                        "name": a["name"],
                        "status": a["status"],
                        "result": a["result"],
                        "error": a["error"],
                    }
                    for a in c.get("agents", [])
                ],
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
            "</details>",
            "",
        ]
    lines += [
        "## Artefatos e reprodução",
        "",
        f"- Entradas: `{args.dataset}`.",
        f"- Evidências completas: `{args.results}`.",
        f"- Revisão explícita: `{args.reviews}`.",
        "- Executar: `.venv/bin/python scripts/evaluate_agent_flows.py`. O runner retoma IDs já concluídos; para outro lote, use um `--output` diferente.",
        "- Gerar este Markdown: `.venv/bin/python scripts/report_agent_flows.py`.",
        "- Os timestamps, versões, mensagens e snapshots de ferramentas permitem auditar as classificações.",
    ]
    args.output.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
