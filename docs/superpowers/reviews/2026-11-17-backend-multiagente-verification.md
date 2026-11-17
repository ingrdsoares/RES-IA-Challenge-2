# Verificação do backend multiagente — 2026-11-17

Implementação nativa na branch `feat/backend-multiagente`, a partir de `ff75d45`.
Desenho aprovado: `docs/superpowers/specs/2026-11-17-backend-multiagente-design.md`.

## Entrega

- Supervisor LLM, jurídico, diagnóstico fiscal e planejamento, executados sequencialmente pelo worker de produção.
- Contratos Pydantic, chamadas estruturadas ao Ollama e validação de referências entre resultados.
- Runs e etapas com snapshots, revisões, tokens de lease, tentativas, orçamento e métricas por papel.
- Checkpoints em transações curtas; chamadas LLM fora das transações de checkpoint.
- Reutilização do resultado das ferramentas na repetição da etapa; cálculo único por etapa.
- Pausa/retomada por confirmação estruturada, sem editar automaticamente o perfil.
- API HTTP 202 compatível, trace/run e andamento em `/operacoes/{id}`; mensagens com ações estruturadas e `next_steps` preservados.
- Tarefas explícitas preservam o suporte da ação de origem e não alteram indicadores fiscais.
- Publicação administrativa de gerações híbridas em novas coleções, com catálogo/âncoras conferidos e recuperação densa como fallback.
- Migrações `0011_agent_runs` e `0012_legal_hybrid`; configurações do worker/API/dispatcher documentadas.

## Evidências

- Baseline antes da implementação: 345 aprovados, cinco pulados.
- Suíte completa após as correções: 372 aprovados, seis pulados, em 32,47 segundos. Os opcionais incluem o smoke multiagente, executado separadamente com dependências reais.
- Smoke real final: cinco etapas Qwen, retomada por dois novos processos do worker de produção após interrupção no checkpoint final, sem duplicar resposta. Tempo total: 33,84 segundos; inferência: 30,509 segundos; 4.678 tokens de entrada e 277 de saída.
- Contratos, leases, exclusividade por empresa, revisões de confirmação, isolamento de ferramentas, idempotência de cálculo, citação inventada, suporte de ações, busca híbrida e publicação de âncoras exercitados pelos novos testes.
- Upgrade `0010 → head`, downgrade para `0010` e novo upgrade aprovados em banco PostgreSQL temporário exclusivo.
- Testes de recuperação incluem expiração de lease, escritor obsoleto, repetição de etapa, falha transitória e interrupção após salvar a síntese e antes de publicar a mensagem.
- Ruff e formatação dos 65 arquivos do escopo verificados; `git diff --check` sem erros.
- Ruff global encontra problemas anteriores em `backend/api/evaluation/topologias.py`, `backend/api/app/rag.py` e scripts de experimentos. A formatação global também identifica cinco arquivos anteriores à entrega. Esses arquivos não foram modificados para fazer a entrega parecer globalmente verde.

## Demonstração com dependências reais

Comando:

```bash
MULTIAGENT_TEST_URL=http://localhost:11434 MULTIAGENT_QDRANT_URL=http://localhost:16333 \
  .venv/bin/python -m pytest backend/api/tests/mvp/test_multiagent_real.py -q -s
```

Usa PostgreSQL/Redis isolados, Qdrant real em coleção temporária e Qwen3:8b/Qwen3-embedding:0.6b locais. A pergunta combina norma demonstrativa, situação de pagamento, simulação sem regra revisada e próximo passo. Os cinco papéis são acionados; a resposta preserva a citação e informa a ausência de regra e de verificação fiscal. Não habilita regras fiscais reais.

Uma execução com cálculo ausente de regra levou 46,92 segundos incluindo preparação; a inferência somou 43,655 segundos, 4.663 tokens de entrada e 284 de saída. As métricas variam com o hardware e o estado do modelo. O teste também cobre interrupção após o checkpoint final e retomada/reenvio via `run_operation` em novos processos Python; não representa teste de indisponibilidade do cluster Redis ou reinício de containers em produção.

## Revisão e decisões

Revisão pelo próprio implementador, em passagem separada; não houve revisão independente ou subagentes.

A revisão identificou e corrigiu duas falhas com testes de regressão: simplificação do schema removia o campo de negócio `title`; e uma queda entre checkpoint de síntese e publicação podia deixar a operação sem retomada rápida. Também se verificaram filtros de versão/território, fechamento dos clientes, orçamento monotônico, autorização das ferramentas e compatibilidade dos handlers existentes.

Decisões de implementação em relação ao plano:

1. Branch dedicada no checkout existente; não foi criado outro worktree.
2. Testes de API e confirmação foram consolidados em `test_multiagent_workflow.py`; testes MVP permanecem sequenciais porque recriam o banco de teste.
3. O handler legado é preservado para consumidores explícitos/testes; `run_operation` usa o novo executor para `assistant.answer`.
4. Invocações das ferramentas ficam nos snapshots das etapas; não foi criada outra tabela de invocações.
5. Prazos normativos são rejeitados até existir extrator estruturado; prazo sugerido continua identificado.
6. Serviços determinísticos decidem entradas obrigatórias: o modelo não exige dados financeiros para ler evidências nem para substituir uma regra indisponível.
7. Síntese já salva pode ser publicada após o prazo de inferência, sem novas chamadas ao modelo.
8. Um commit integrado reúne runtime, metadados e migrações, em vez de commits intermediários com imports incompletos.

## Limites

Não foram entregues frontend, conectores oficiais, lembretes, RLS, revisão independente, deploy ou regras fiscais homologadas. A validação de estrutura e IDs não prova correção semântica de toda interpretação jurídica ou de todo texto de ação; revisão humana e avaliações de qualidade continuam necessárias. O servidor renderiza resultados fiscais para impedir que o texto livre substitua valores e estados do domínio.

O histórico de versões e checkpoints não tem expurgo automático. Gerações de índice que falhem durante construção ficam sem ativação e podem precisar de limpeza administrativa futura. A suíte em Python 3.14 mantém avisos de depreciação existentes; o runtime Docker continua baseado na configuração Python do projeto.

## Testes práticos adicionais

Cinco cenários com Qwen e embeddings reais, PostgreSQL e Qdrant: jurídico, situação fiscal,
cálculo sem regra, consulta combinada com planejamento e cálculo com parâmetros artificiais.
Os quatro primeiros passaram na execução conjunta; o último passou após corrigir a validação
do texto fiscal que é substituído pela renderização do servidor. O valor conhecido da fixture
é 800.00; esses parâmetros não são regras tributárias homologadas.

As perguntas, respostas finais, ações, saídas e métricas de cada agente estão em
`2026-11-17-agent-practical-results.json`. Os testes exigem seleção exata de especialistas,
conteúdo jurídico pertinente, citação, resposta fiscal sem comprovação indevida e valor do motor.
Os prompts passaram à versão multiagent-v2 para corrigir delegação excessiva.

Regressão posterior: 373 aprovados e dez pulados. A contagem de pulados cresceu porque o
único smoke opt-in virou cinco casos parametrizados; os cinco foram executados separadamente.
Dos seis pulados originais, dois dependiam de QDRANT_TEST_URL, um de OLLAMA_TEST_URL, um
habilitava o smoke multiagente, um exigia API/stack dedicada via MVP_TEST_URL e outro precisava
de torch/bert_score ausentes da venv. O benchmark BERT e o fluxo MVP de API implantada não
foram executados nesta rodada de testes práticos dos agentes.
