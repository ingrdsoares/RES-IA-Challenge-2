# Bateria de agentes com busca híbrida e reranker

O runner usa `AgentTools.legal`, o mesmo caminho de recuperação do backend. A única exceção funcional na recuperação é ignorar vigência no experimento, conforme autorizado. Também são injetados os parâmetros experimentais de geração e uma verificação que impede fallback silencioso do reranker.

## Executar quando desejado

```bash
.venv/bin/python scripts/evaluate_agent_flows.py \
  --num-ctx 16384 \
  --thinking \
  --num-predict 4096 \
  --reranker-url http://localhost:18080 \
  --output docs/avaliacao/bateria-50-agentes-16k-thinking-hibrida.json
```

Esse comando inicia inferências reais e não foi executado nesta preparação. Nenhuma bateria é iniciada pelos testes automatizados do runner.

## Pré-requisitos

- PostgreSQL, Redis, armazenamento de documentos, Qdrant e Ollama disponíveis.
- Coleção híbrida construída e ativa no catálogo, compatível com os documentos prontos.
- Serviço real de reranking ativo na URL informada. O endpoint `/health` precisa responder. Ausência de configuração ou coleção híbrida impede iniciar a bateria.
- Qwen3:8b e qwen3-embedding:0.6b instalados no Ollama.

O script não sobe serviços nem constrói índices automaticamente. O ambiente local teve uma geração híbrida de 348 pontos preparada e ativada durante a preparação. O contêiner `sd-eval-reranker`, criado para a verificação inicial, foi parado a pedido do usuário. A disponibilidade real de reranking não foi validada até o fim; os testes abaixo usam respostas controladas, sem acionar modelos.

## Parâmetros e garantias

- Perguntas: `backend/evaluation/data/agent_flow_50.json`.
- Recuperação: `top_k` e `score_threshold` efetivos de `Settings`; defaults atuais 8 e 0,5, respectivamente. Esses parâmetros não são os 5 e 0,3 dos lotes densos anteriores.
- Busca híbrida: coleção ativa, mesmos filtros e fusão de resultados do backend.
- Reranker: mesma implementação do backend; sucesso HTTP e quantidade de scores são verificados. Falha não pode ser mascarada como reordenação bem-sucedida.
- Cada busca registra estratégia das fontes e auditoria da chamada ao reranker. Queda para busca densa é rejeitada como erro, não aceita como teste híbrido.
- Contexto 16.384, thinking ativado e geração máxima 4.096 via flags. Timeout por agente 300 s no modo thinking, rodada 600 s. Os limites e a coleção são registrados nos parâmetros.
- Salva cada caso, inclusive falhas. Se ainda ficar em fila após as tentativas limitadas, interrompe o lote como incompleto em vez de avançar silenciosamente.
- Retomada exige parâmetros e dataset iguais. IDs com estado `queued`/`running` não contam como concluídos. Uma nova tentativa desses IDs usa fixtures novas; o registro anterior é preservado em `metadata.prior_nonterminal_records`, sem duplicar o caso principal.
- Os estados `failed` e `awaiting_data` contam como resultados de fluxo para a avaliação, sem significar resposta correta.
- `evaluation_status=complete` exige todos os casos com resultado terminal do experimento. A revisão de qualidade continua separada da execução.

## Validação sem modelos

```bash
.venv/bin/python -m pytest backend/api/tests/test_battery_runner.py -q
```

Os testes cobrem configuração e thinking, proteção da retomada, parâmetros reais de recuperação, passagem pela ferramenta do backend, falha explícita e sucesso auditado do reranker, repetição limitada de operações em fila e substituição do registro incompleto na retomada.

Esses testes validam o código com dependências controladas. Não demonstram disponibilidade dos serviços nem qualidade das respostas reais. Uma futura execução com serviços ativos precisa ser auditada antes de ser apresentada como bateria híbrida completa.
