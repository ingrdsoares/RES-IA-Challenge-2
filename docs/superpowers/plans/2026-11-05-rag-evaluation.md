# RAG Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar CLI retomável para avaliar o RAG existente com ROUGE-L/BERTScore, estatística e Excel, preparada para receber um dataset real posteriormente.

**Architecture:** Coleta interna via `RagService.query`, checkpoints SQLite e etapas independentes de pontuação e relatório. Cada execução congela a seleção e o contexto experimental; métricas têm identidades próprias e relatórios são derivados dos dados salvos. O pacote de avaliação não modifica o serviço de produção.

**Tech Stack:** Python 3.12, Pydantic, SQLite, NumPy, rouge-score, bert-score/PyTorch/Transformers, huggingface-hub, openpyxl, Matplotlib e pytest.

**Spec:** `docs/superpowers/specs/2026-11-05-rag-evaluation-design.md`.

## Global Constraints

- Branch `feat/rag-evaluation`, no checkout atual; preservar arquivos de produção em `backend/api/app/`, sua arquitetura e dependências.
- Sem ingestão, dataset artificial, dados reais inventados, chamadas pagas ou bateria de consultas reais nesta implementação.
- Pacote separado `backend/api/evaluation/`, dependências opcionais em `requirements-eval.txt`, documentação em `backend/evaluation/`.
- CLI em etapas com `run` como conveniência; `score`, `report` e `compare` nunca chamam o RAG.
- Presets pilot: 30 perguntas; reference: até 200; expansão por limite explícito ou seleção completa, sem repetir perguntas para completar quantidades.
- ROUGE-L oficial com Unicode NFC/casefold, acentos preservados, sem stemming/stopword removal; citações mantidas.
- BERTScore inicial: BERTimbau Base, 12 camadas, idioma pt, batch 4, CPU, IDF e rescaling desabilitados, tokenizer lento/cased.
- Bootstrap percentil: IC 95%, 5.000 reamostragens, seed 42; amostra é pergunta única, nunca repetição.
- Margem de erro inicial 0,05, desvio amostral ddof=1, n estimado por ceil((1,96*s/E)^2).
- Falhas/vazios/base vazia ficam sem pontuação; similaridade de abstenção não determina acerto comportamental.
- Nenhum download oculto de pesos. Preparação explícita ou autorização via opção; execução normal de testes usa backend BERT controlado.
- Defaults e escolhas não decididos no desenho estão fixados abaixo para permitir execução sem adivinhações.

## Review Focus

- Interrupção após enviar consulta e antes de persistir: marcar incerta, nunca duplicar silenciosamente; tarefa 2.
- Métrica disponível só para parte das repetições ou versões: denominadores e pareamento por pergunta permanecem corretos; tarefas 4 e 5.
- BERT indisponível, texto longo ou falha de lote: preservar ROUGE e respostas, isolar falhas sem substituí-las por zero; tarefa 3.
- Duas execuções concorrentes ou configuração alterada: bloquear escrita concorrente e rejeitar retomada incompatível; tarefa 2.
- Textos com fórmula, controles ou mais de 32.767 caracteres: Excel/CSV seguros e textos completos recuperáveis; tarefa 6.

## Mapa de arquivos

Todos os módulos de produto abaixo ficam em `backend/api/evaluation/`:

| Arquivo | Responsabilidade |
| --- | --- |
| `__init__.py`, `__main__.py`, `cli.py` | Entrada e comandos argparse; imports pesados tardios |
| `schemas.py`, `config.py` | Contratos Pydantic e precedência CLI > JSON > EVAL_* > defaults |
| `dataset.py` | Leitura, validação, duplicatas, splits, seleção e hashes |
| `adapter.py`, `collect.py` | Integração interna e coleta serial com falhas isoladas |
| `storage.py` | Manifest, SQLite, lock e checkpoints |
| `metrics/rouge.py`, `metrics/bert.py`, `metrics/engine.py` | Tokenização, modelo contextual e pontuação persistida |
| `statistics.py`, `comparison.py` | Agregados por pergunta, bootstrap, dimensionamento e pareamento |
| `reports/export.py`, `reports/excel.py`, `reports/plots.py`, `reports/markdown.py` | Exportação dos artefatos, Excel e gráficos |

Criar `__init__.py` nos subpacotes. Testes em `backend/api/tests/evaluation/`. Recursos humanos: `backend/evaluation/README.md`, `dataset.schema.json`, `data/README.md`. Adicionar apenas caminhos específicos de caches/saídas ao `.gitignore`. O schema JSON é gerado do modelo, sem dataset preenchido.

### Task 1: Contratos, dataset e ambiente opcional

**Files:** criar `evaluation/{__init__,schemas,config,dataset}.py`, `requirements-eval.txt`, `tests/evaluation/test_dataset.py`, `test_eval_config.py`; atualizar `.gitignore` e criar recursos de dataset.

**Interfaces:**
- `EvalCase`: campos obrigatórios `id/category/question/ground_truth: str`; opcionais `expected_sources: list[str | int]`, `metadata: dict`, `expected_behavior: answer|abstain|clarify=answer`, `split: development|final=development`, `group_id: str|None`. Validar a pergunta com `app.schemas.QueryRequest` sem alterar produção.
- `SelectionConfig`: `preset: pilot|reference|None=None`, `limit: int|None`, `all_cases=False`, `split=development`, `seed=42`; preset/limit/all são mutuamente exclusivos. Sem nenhum deles, usar pilot; limit representa seleção customizada. Registrar o modo efetivo no manifest. `RunConfig`: seleção, `repeats=1`, `rag_version` e `corpus_version` obrigatórios para coleta.
- `MetricConfig`: BERT modelo/revisão/caminho, camadas 12, lang pt, batch 4, device cpu, idf false, rescale false, baseline opcional, `overflow=error|truncate` padrão error, download false. `StatsConfig`: bootstrap 5000, seed 42, margin 0.05, validação de inteiros positivos e margem positiva/finita.
- `DatasetSelection`: casos selecionados em ordem, hash completo/hash selecionado, distribuição e quantidade elegível no split por expected_behavior.
- `load_dataset(path: Path) -> list[EvalCase]`; `select_cases(cases: list[EvalCase], config: SelectionConfig) -> DatasetSelection`.
- `resolve_config(file: Path|None, overrides: dict) -> EvalConfig`, agrupando RunConfig/MetricConfig/StatsConfig; perguntas/referências originais permanecem preservadas, normalização para duplicatas é separada.

- [ ] Escrever testes: JSON e JSONL válidos; rejeitar campos obrigatórios vazios, ID duplicado, pergunta equivalente em NFKC/casefold/espaços, pergunta longa e grupo cruzando splits. Rejeitar piloto de 29 casos e permitir limite customizado de 2. Testar reference com 35 casos retorna 35 sem duplicar; 250 casos permitem selecionar 200 ou todos. Testar seleção idêntica com mesma seed e sem dependência da ordem do arquivo. Rodar os testes e observar falha por funcionalidade ausente.
- [ ] Implementar validação e seleção: ordenar por ID antes de usar `random.Random(seed)`; escolher amostra e manter ordem selecionada no manifest. Hashes SHA-256 de JSON canônico UTF-8 com chaves ordenadas; lista completa canônica por ID, subconjunto com ordem da seleção. Não criar quotas por categoria. Rejeitar conjunto vazio para avaliação; template não depende de dataset.
- [ ] Escrever testes de precedência, limites e rejeição de unknown keys na configuração de avaliação; manter defaults de CLI como None para não sobrescrever arquivo/ambiente sem intenção. Implementar os modelos e resolução após verificar falha.
- [ ] Preparar ambiente separado com Python 3.12. `requirements-eval.txt` reutiliza `-r requirements.txt`, adiciona `rouge-score==0.1.2`, `bert-score==0.3.13` e versões exatas compatíveis de torch (>=2.6), transformers (<5), huggingface-hub, numpy, openpyxl e matplotlib, resolvidas/verificadas nesse ambiente. Não editar requirements de produção. Marcar smoke pesado como opcional; `--help`, validate e template não importam torch.
- [ ] Gerar schema JSON e README de dados sem nenhuma pergunta inventada; ignorar `backend/evaluation/runs/`, caches de avaliação e ambiente virtual específico.
- [ ] Executar `python -m pytest tests/evaluation/test_dataset.py tests/evaluation/test_eval_config.py -q` em `backend/api/`: todos passam. Commit `feat: define evaluation datasets and configuration`.

### Task 2: Captura interna e retomada transacional

**Files:** criar `evaluation/{adapter,storage,collect}.py`, ampliar `schemas.py`; testes `test_collection.py`, `test_resume.py`.

**Interfaces:**
- `RagClient` Protocol: `query(question: str) -> QueryResponse`, `metadata() -> dict`, `close() -> None`; `InternalRagClient(settings: app.config.Settings)` implementa o protocolo com os objetos existentes. `metadata` lê Git SHA, hash de SYSTEM_PROMPT, parâmetros sem credenciais, digests Ollama pelo SDK e metadados Qdrant. Não consulta LLM para metadados.
- `RunManifest`: schema_version=1, run_id, config de coleta, casos selecionados e hashes, contexto RAG, corpus declarado e collection metadata; `identity_hash` exclui run_id, timestamps e caminhos absolutos de saída.
- `AttemptResult`: case_id, repeat_index (1-based), attempt_revision (incrementada somente em retry explícito), state `planned|running|success|error|uncertain`, status RAG opcional, answer/sources opcionais, start/end UTC, duration_seconds, error_type/message, retry history. `success` operacional não implica pontuação elegível.
- `RunStore(path: Path)` context manager com `initialize(manifest: RunManifest)`, `manifest() -> RunManifest`, `attempts() -> list[AttemptResult]`, `start(case_id, repeat_index)`, `finish(result: AttemptResult)`, `mark_interrupted()`, `save_metric(fingerprint: str, result: ScoredAttempt)` e `read_metrics(fingerprint: str) -> list[ScoredAttempt]`. `ScoredAttempt` definido na tarefa 3; funções de métricas podem ser acrescentadas então sem alterar as interfaces de coleta.
- `collect_run(client: RagClient, store: RunStore, retry_failed: bool=False, retry_uncertain: bool=False) -> CollectionSummary`.

- [ ] Escrever testes com doubles de RAG e banco SQLite real temporário: sucesso salva fontes, timeout/erro não interrompem a pergunta seguinte, mensagem vazia é marcada, ordem/repetições correspondem ao manifest. Verificar falha antes da implementação.
- [ ] Implementar adapter fino sem HTTP, sem chamar `answer` diretamente, sem alterar prompts. Validar as perguntas e serializar a resposta Pydantic em modo JSON. Medir apenas `client.query` com `perf_counter`; capturar exceções tipadas por tentativa, sanitizando erros/configuração antes da persistência.
- [ ] Escrever testes de retomada com contador de chamadas do double: segunda coleta não faz chamadas de sucessos; running vira uncertain e só opção explícita permite retry; erro concluído não é refeito por padrão; retry deixa histórico; manifest alterado e segundo escritor são rejeitados.
- [ ] Implementar lock exclusivo por execução com `portalocker` (já disponível no ambiente por qdrant-client; registrar dependência direta da avaliação), SQLite com transações e unicidade `(case_id, repeat_index)`. Commit de running antes da chamada e de resultado logo após. Não há retry implícito nem tentativa de cancelar à força a chamada síncrona.
- [ ] Inicialização nova exige diretório novo ou identidade compatível. Proibir retomada com seleção/configuração/corpus declarados ou contexto RAG alterados; não confundir timestamps/caminhos com identidade. Registrar que contagem/config da coleção não são fingerprint do conteúdo. Não gerar snapshots nem escrever pontos.
- [ ] Executar `python -m pytest tests/evaluation/test_collection.py tests/evaluation/test_resume.py -q`: todos passam. Commit `feat: collect RAG evaluations with resumable checkpoints`.

### Task 3: ROUGE-L e BERTScore em lotes

**Files:** criar `evaluation/metrics/{__init__,rouge,bert,engine}.py`; ampliar `schemas.py` e persistência de métricas; testes `test_rouge.py`, `test_bertscore.py`, `test_scoring.py`.

**Interfaces:**
- `MetricScore`: `precision/recall/f1: float|None`, `state=success|skipped|error`, erro tipado, detalhes de truncamento e tempos. Valores finitos; não restringir BERTScore rescalado a 0–1.
- `ScoredAttempt`: resultado da coleta, `rouge_l: MetricScore`, `bert_score: MetricScore`, identidade das métricas e campos de adjudicação opcionais.
- `UnicodeTokenizer.tokenize(text: str) -> list[str]`; `RougeMetric.score(reference: str, candidate: str) -> MetricScore` usa `RougeScorer(['rougeL'], use_stemmer=False, tokenizer=...)`.
- `BertMetric(config: MetricConfig, references: list[str])` com `score_pairs(pairs: list[tuple[str,str]]) -> list[MetricScore]`, `metadata() -> dict`; factory injetável só na construção pelo engine para testes, sem lógica de teste em produção.
- `prepare_model(config: MetricConfig, allow_download: bool=False) -> PreparedModel`: caminho, model ID, revisão efetiva e hashes. `score_run(store: RunStore, config: MetricConfig, ...) -> ScoringSummary` nunca recebe RagClient.

- [ ] Escrever teste ROUGE que capture regressão ASCII: referência `ação fiscal`, candidato `ação`; esperar P=1, R=0.5, F1=2/3 e o token `ação` inteiro. Testar equivalência NFC/decomposição Unicode, acentos distintos preservados e stemming ausente. Rodar RED e implementar apenas tokenizer/política de normalização e chamada oficial.
- [ ] Escrever testes BERT com scorer/tokenizer controlados: uma carga por etapa, batch 4, P/R/F1 mapeados à tentativa correta, UTF-8 e caixa preservados, revisão/hash registrados, referências IDF sem duplicar repetições, baseline ausente rejeitado e cache ausente não baixa pesos. Verificar falha e implementar resolução de snapshot versionado, usando `local_files_only` por padrão. `prepare-model` será o ponto explícito de autorização para baixar.
- [ ] Detectar tamanho tokenizado com os tokens especiais: overflow padrão gera erro apenas de BERTScore; opção truncate registra quantidades originais e avaliadas. Validar no teste. Modelo local recebe hash do conteúdo e exige num_layers explícito quando diferente do default; não usar `trust_remote_code=True`.
- [ ] Escrever testes de falha parcial de lote, NaN e respostas inelegíveis: preservar ROUGE em falha de BERT, nenhum zero sintético, vazios/base vazia/exceções não passam ao scorer. `insufficient_context` não vazio pode ser pontuado, com comportamento separado no resumo. Falha de lote é isolada em sublotes até identificar casos afetados, reaproveitando o mesmo modelo.
- [ ] Implementar score sobre respostas salvas, com referências canônicas NFC/whitespace e IDF de um ground_truth por ID selecionado. Persistir pontuação por `(identity_hash da coleta, case_id, repeat_index, attempt_revision, fingerprint das métricas)`, em transações. Reutilizar métricas completas da mesma revisão ao retomar; retry de coleta invalida a associação antiga sem apagar seu histórico. Testar que uma resposta nova não herda scores da tentativa anterior e que exportações usam a revisão ativa. Novas configurações criam outra versão. Fingerprint inclui versões, revisão, IDF corpus hash, baseline hash, camadas e políticas; guardar também hash nativo BERTScore.
- [ ] Testar que erro de inicialização de BERT gera resultados/erros explícitos por tentativa elegível, com ROUGE preservado; configuração não resolvida não se apresenta como modelo/revisão verificados. Relatório deve continuar possível, comparação BERT exige configuração resolvida equivalente.
- [ ] Executar `python -m pytest tests/evaluation/test_rouge.py tests/evaluation/test_bertscore.py tests/evaluation/test_scoring.py -q`: todos passam, sem download/chamada LLM. Commit `feat: score saved answers with ROUGE-L and BERTScore`.

### Task 4: Estatística, repetições e dimensionamento

**Files:** criar `evaluation/statistics.py`; testes `test_statistics.py`; schemas de resumo em `schemas.py`.

**Interfaces:**
- `summarize_values(values: list[float], config: StatsConfig) -> DistributionSummary`.
- `estimate_sample_size(sample_std: float|None, margin: float, available: int) -> SampleSizeEstimate` retorna necessidade bruta, mínimo operacional, suficiência apenas numérica e ressalvas.
- `summarize_run(manifest: RunManifest, attempts: list[ScoredAttempt], config: StatsConfig, pilot_summary: dict|None=None) -> RunSummary` inclui geral, categorias, expected_behavior, cobertura, variação por pergunta e denominadores por métrica.

- [ ] Escrever testes com valores conhecidos: [0.2,0.4,0.6] tem média/mediana 0.4 e desvio amostral 0.2; vazio resulta null; n=1 tem desvio/IC null; constante com n>=2 tem IC degenerado e aviso. Percentis 5/25/75/95 e IC 2.5/97.5 usam interpolação linear. Seed igual repete resultado exatamente. Verificar RED.
- [ ] Implementar bootstrap percentil com `numpy.random.default_rng(seed)`, 5.000 reamostragens configuráveis, em blocos para limitar memória; não importar adapter ou scorer neste módulo.
- [ ] Escrever teste que detecta pseudorreplicação: pergunta A com duas pontuações [0,1], B com [1] produz média entre perguntas 0.75, não 2/3. Testar falhas parciais e variância dentro de pergunta sem contar repetições como n independente. Implementar agrupamento por ID antes de estatística.
- [ ] Escrever teste de tamanho amostral: s=0.2, E=0.05 dá n=62; disponível=30 indica insuficiência numérica sem invalidar média/IC. s ausente dá indisponível, s=0 informa resultado bruto zero/mínimo operacional 2 e limitação. Implementar fórmula, com hipóteses explícitas.
- [ ] Separar agregados principais `expected_behavior=answer` dos diagnósticos abstain/clarify; não inferir correção de recusa por texto. `empty_knowledge_base`/vazios/erros são inelegíveis e entram em contagens explícitas. Validar contagens disjuntas quando apresentadas como partição e sinalizar casos parcialmente pontuados.
- [ ] Se for fornecido resumo do piloto, conferir fingerprint da métrica e usar seu s para dimensionamento. Sem piloto externo, usar s da própria execução e identificar origem, distinguindo preset pilot de estimativa exploratória. Não declarar que perguntas do mesmo domínio são comprovadamente independentes.
- [ ] Executar `python -m pytest tests/evaluation/test_statistics.py -q`: todos passam. Commit `feat: summarize evaluation uncertainty and sample size`.

### Task 5: Comparação pareada e adjudicação humana

**Files:** criar `evaluation/comparison.py`; ampliar schemas; testes `test_comparison.py`, `test_adjudication.py`.

**Interfaces:**
- `compare_runs(a: EvaluationSnapshot, b: EvaluationSnapshot, config: StatsConfig) -> ComparisonSummary`; `EvaluationSnapshot` contém manifest, métricas resolvidas e ScoredAttempts de uma configuração selecionada.
- `Adjudication`: run_id, case_id, repeat_index, `judgment=correct|incorrect|not_assessed`, rationale e reviewer. `apply_adjudications(snapshot: EvaluationSnapshot, entries: list[Adjudication]) -> EvaluationSnapshot`.

- [ ] Escrever testes: rejeitar perguntas/referências/IDs/categorias/split/expected_behavior ou configurações de métrica incompatíveis; versões diferentes do RAG/corpus são permitidas e identificadas. Falta de segunda execução não afeta summarize_run. Verificar RED.
- [ ] Implementar comparação separada por métrica: parear exatamente `(id, repetição)` com scores válidos em A e B, calcular diferenças B−A e agregar por pergunta, com mesmo subconjunto em ambas. Registrar todos os pares excluídos e diferenças por ID.
- [ ] Testar ganho constante de 0.1: diferença média e extremos do IC 0.1; repetir seed reproduz resultado. Testar ordem diferente, falha só em uma versão e repetições parciais, que não podem produzir pareamentos por posição ou comparar médias de coortes diferentes. Implementar bootstrap pareado e vitórias/empates (tolerância absoluta 1e-12) por pergunta, geral/categoria/expected_behavior.
- [ ] Testar que abstenção textual/status não produz `correct` automaticamente. Arquivo de adjudicação só aceita chaves de uma execução existente, sem duplicatas conflitantes e com justificativa/revisor para julgamento avaliado. Aplicar revisões como camada separada, sem alterar respostas ou métricas originais; calcular correção comportamental somente entre casos efetivamente adjudicados.
- [ ] Executar `python -m pytest tests/evaluation/test_comparison.py tests/evaluation/test_adjudication.py -q`: todos passam. Commit `feat: compare paired runs and record human judgments`.

### Task 6: Exportações, Excel e gráficos

**Files:** criar `evaluation/reports/{__init__,export,excel,plots,markdown}.py`; testes `test_exports.py`, `test_excel.py`, `test_reports.py`.

**Interfaces:**
- `write_report(snapshot: EvaluationSnapshot, summary: RunSummary, output_dir: Path, comparison: ComparisonSummary|None=None) -> list[Path]`.
- `write_template(output_dir: Path) -> list[Path]`: dataset.xlsx com aba de entrada e instruções, modelo de relatório/Excel de resultados sem casos ou scores fictícios.
- Artefatos: `results.json`, `results.csv`, `summary.json`, `report.md`, `report.xlsx`, gráficos PNG quando elegíveis. Relatórios versionados em `reports/<metric_fingerprint>/<stats_fingerprint>/`; criação atômica de arquivos e bloqueio contra sobrescrever exportação de outra identidade.

- [ ] Escrever testes que abram JSON/CSV e XLSX real com openpyxl, validem linha por tentativa, métricas ausentes como células vazias/null, erros preservados, totais compatíveis com summary e nomes das abas. Verificar RED e implementar exportação usando os modelos das tarefas anteriores.
- [ ] Excel: abas Resultados, Resumo, Categorias, Falhas, Configuração, Abstenções, Variabilidade, Tamanho amostral, Fontes; Comparação quando aplicável e Textos para conteúdos longos. Usar filtros, congelar cabeçalhos e scores como números sem formato de porcentagem; referências/fonte têm chave para a tentativa.
- [ ] Escrever testes de texto começando com =,+,-,@ e controles, além de 40.000 caracteres: célula textual não é fórmula; CSV neutraliza interpretação de fórmula; fragmentos numerados na aba Textos reconstroem o texto completo, e JSON permanece original. Implementar escaping de apresentação e mapa das transformações, sem perda silenciosa.
- [ ] Testar Markdown com zero/um caso sem conclusões/IC inventados; 12 seções em português, metodologia/versionamento/limitações e contagens reais. Incluir referências primárias do desenho. Template deve ter só cabeçalhos/instruções e indicar dataset ainda não fornecido, sem estatísticas vazias apresentadas como medidas.
- [ ] Gráficos com backend Matplotlib Agg: distribuição exige ao menos dois valores válidos, dispersão exige dois casos com ambas as métricas e gráfico por categoria ao menos duas categorias pontuadas. Incluir PNGs no Markdown e Excel; ausência de dados produz nota, não distribuição artificial. Validar exportação não vazia e inserção das imagens no workbook.
- [ ] Executar `python -m pytest tests/evaluation/test_exports.py tests/evaluation/test_excel.py tests/evaluation/test_reports.py -q`: todos passam. Commit `feat: export evaluation reports and Excel workbooks`.

### Task 7: CLI, documentação e verificação integrada

**Files:** criar `evaluation/{cli,__main__}.py`, `tests/evaluation/test_cli.py`; completar `backend/evaluation/README.md`; atualizar links em `backend/README.md` e `README.md`, sem modificar rotas ou imagens de produção.

**Interfaces e opções públicas:**
- `main(argv: list[str]|None=None) -> int`, argparse; saída 0 sucesso, 2 entrada/configuração inválida, 1 falha operacional global. Falhas parciais constam nos artefatos e no resumo do terminal, não apagam a execução.
- Comandos `validate --dataset PATH`, `template --output DIR`, `prepare-model --allow-download`, `collect --dataset PATH --run-dir DIR --rag-version NAME --corpus-version NAME`, `score --run-dir DIR`, `report --run-dir DIR`, `run` (opções de coleta/métricas/relatório), `compare --run-a DIR --run-b DIR --output DIR`.
- Opções compartilhadas de seleção: `--preset pilot|reference`, `--limit N`, `--all`, `--split development|final`, `--seed 42`, `--repeats N`. `--split final` é sempre explícito e não é permitido com preset pilot.
- Retomada: `--resume`, `--retry-failed`, `--retry-uncertain`; seleções/versões devem ser as mesmas da execução persistida. Sem --resume, diretório de execução existente não é sobrescrito.
- Métricas: `--bert-model`, `--bert-revision`, `--bert-model-path`, `--bert-layers`, `--bert-batch-size`, `--device`, `--idf/--no-idf`, `--rescale/--no-rescale`, `--baseline-path`, `--bert-overflow error|truncate`, `--allow-model-download`. O comando prepare-model autoriza apenas download; não coleta respostas.
- Relatórios: `--bootstrap 5000`, `--margin 0.05`, `--pilot-run DIR` opcional, `--adjudications PATH` opcional, `--metric-fingerprint HASH` para escolher resultados quando houver mais de uma configuração. `--config PATH` JSON e EVAL_* são suportados com a precedência da tarefa 1.

- [ ] Escrever testes CLI com diretórios temporários e adapter/scorer injetados por factory interna: validate/template não instanciam RAG/BERT; run gera todos os artefatos; collect+score+report separados equivalem ao encadeamento; resume não duplica chamadas; report/compare têm fábrica de RAG proibida. Observar RED e implementar orquestração fina.
- [ ] Validar índices e fingerprint na escolha de versões: sem --metric-fingerprint, usar a única disponível; com várias, exigir escolha para não comparar ou exportar a errada. `report --pilot-run` exige seleção de métricas equivalente e nunca consulta o RAG.
- [ ] Documentar comandos exatos de instalação em ambiente separado, preparação do dataset, download autorizado/cache do encoder, piloto 30, reference até 200, custom/all, splits, repetições, retomada, comparação e interpretação. Explicar 200 perguntas versus chamadas versus 5.000 reamostragens; dados finais não são usados para tuning automático; abstenção exige julgamento independente.
- [ ] Documentar que sources são os trechos usados pelo gerador, modelo/revisão/camadas/normalizações, overflow, IDF/baseline, limites do bootstrap e dimensionamento, risco de viés por exclusão de falhas e ausência de equivalência entre similaridade e correção factual.
- [ ] Executar a suíte completa existente e nova em Python 3.12: `python -m pytest tests -q`, sem QDRANT_TEST_URL quando não for necessária integração de infraestrutura. Verificar ausência de chamadas reais do LLM e de download de pesos nos testes. Corrigir falhas antes de prosseguir.
- [ ] Executar CLI --help e template real em `backend/evaluation/runs/template/`, gerando XLSX vazio real e relatório identificado. Reabrir workbook para confirmar validade; entregar esse caminho no resultado. O diretório é ignorado pelo Git. Não executar run/collect sobre perguntas artificiais como avaliação do produto.
- [ ] Executar smoke ROUGE real com fixtures nos testes; BERTScore real somente se pesos já estiverem disponíveis ou autorização adicional explícita. Registrar claramente validações executadas e omitidas, sem alegar métricas reais do RAG com corpus ausente.
- [ ] Conferir diff para garantir nenhum arquivo de produção app/ ou requirements de produção alterado, nenhum documento/peso/cache versionado e nenhuma escrita em pontos Qdrant. Commit `feat: add evaluation CLI and usage documentation`.
- [ ] Solicitar uma revisão independente da branch segundo a skill de execução, corrigir achados importantes com regressão RED→GREEN e repetir a suíte necessária. Marcar tarefas concluídas e registrar evidências no plano, preservando a branch para revisão.

## Revisão do plano

Cobertura: tarefa 1 define datasets/configuração e independência dos splits; tarefa 2 preserva integração e retomada; tarefa 3 métricas oficiais/português/versões/falhas; tarefa 4 estatística, repetição e dimensionamento; tarefa 5 comparação e abstenção adjudicada; tarefa 6 todos os formatos e gráficos; tarefa 7 operação completa, comandos e verificações locais. Todos os itens de Review Focus têm testes na tarefa responsável.

Método de execução proposto: o próprio agente nesta sessão, preservando a preferência usada no backend, com uma revisão independente ao final. As interfaces são compartilhadas entre as sete tarefas e uma execução sequencial evita duplicar decisões sobre schema e checkpoints.
