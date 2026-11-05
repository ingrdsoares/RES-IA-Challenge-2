# Pipeline de avaliação do RAG — desenho

Status: proposta para aprovação. Branch: `feat/rag-evaluation`, derivada da implementação atual do backend.

## Objetivo e limites

Implementar avaliação automatizada do RAG existente com ROUGE-L e BERTScore, análise estatística, retomada e relatórios, incluindo Excel. O usuário escolheu uma CLI com etapas separadas e um comando que executa todas elas. Os documentos estão em tratamento e devem ser ignorados nesta fase; não há dataset de avaliação validado no repositório.

Esta entrega prepara e testa o pipeline. Não cria perguntas ou referências para completar quantidades, não popula Qdrant, não modifica arquitetura, prompts ou comportamento da aplicação e não apresenta resultados de fixtures como resultados reais do produto. A avaliação científica com o corpus real ocorrerá quando documentos e referências estiverem disponíveis.

## Estado atual verificado

- Python, FastAPI e schemas Pydantic em `backend/api/app/`; testes pytest em `backend/api/tests/`.
- `RagService.query(question: str) -> QueryResponse` já permite consulta interna, sem HTTP; a construção usa `Settings`, `VectorStore` e `LocalModels` existentes.
- `QueryResponse` contém `status`, `answer` e `sources`; estas são as passagens efetivamente enviadas à geração, possivelmente truncadas, não todos os hits brutos da recuperação.
- Estados existentes: `answered`, `insufficient_context`, `empty_knowledge_base`. Erros de dependências, timeout e ocupação têm classes próprias.
- Qdrant persistente e Ollama com Qwen; coleção `knowledge_base` com zero pontos na inspeção inicial desta tarefa.
- Configuração usa Pydantic Settings e variáveis de ambiente; logging padrão Python. Sem dataset real de perguntas/referências.

## Abordagens e escolha

1. **CLI em etapas, escolhida pelo usuário:** coletar respostas, calcular métricas e gerar relatórios independentemente, com dados persistidos entre etapas. Recalcular métricas, bootstrap e Excel não faz novas consultas ao RAG.
2. **Script único:** sequência menos flexível de coleta e análise com checkpoints. Não escolhido como organização principal, mas um comando de conveniência encadeará as etapas da CLI.

Consultar por HTTP seria útil para avaliar um serviço remoto e sua latência de transporte. Nesta entrega, a proposta é usar diretamente a interface interna existente para medir a consulta do RAG. Não implementar transporte HTTP adicional.

## Organização e instalação propostas

- Pacote `backend/api/evaluation/`, separado de `app/`, executável por `python -m evaluation` a partir de `backend/api/`.
- Módulos por responsabilidade: configuração/schemas, validação e seleção de dataset, adapter do RAG, armazenamento da execução, métricas, estatística, comparação, relatórios e CLI.
- `backend/api/requirements-eval.txt` separado das dependências de produção. Reutilizar Pydantic, NumPy, clientes e configuração atuais; acrescentar `rouge-score`, `bert-score`, PyTorch/Transformers compatíveis, `huggingface-hub`, `openpyxl` e Matplotlib.
- Ambiente de avaliação separado, preferencialmente Python 3.12, sem aumentar a imagem ou as dependências do serviço de produção. Documentar execução nativa e execução num container temporário com o pacote de avaliação montado.
- Versões explícitas verificadas na implementação, sem alterar as versões usadas pela aplicação para acomodar bibliotecas de avaliação.
- `backend/evaluation/README.md`, schema JSON do dataset e diretório de dados vazio/documentado; saídas e caches fora do versionamento. Não versionar documentos, pesos ou execuções reais automaticamente.

## Comandos e responsabilidades

Nomes propostos; opções detalhadas serão fixadas no plano:

- `validate`: validar dataset, duplicatas, splits e informar distribuição sem consultar o RAG.
- `template`: criar Excel vazio para preparação do dataset e modelo de relatório, sem linhas de perguntas ou valores de métricas inventados.
- `collect`: consultar o RAG sequencialmente e persistir cada tentativa.
- `score`: calcular métricas sobre respostas já armazenadas, em lotes para BERTScore.
- `report`: recalcular estatísticas e gerar JSON/CSV/Markdown/Excel/gráficos usando apenas dados locais.
- `run`: encadear validação, coleta, métricas e relatório.
- `compare`: comparar duas execuções já pontuadas, sem consultar modelos geradores.

Presets `pilot` com 30 perguntas e `reference` com até 200 como seleção inicial. Quantidade customizada e seleção de todo o dataset permitem expansão. Um piloto com menos de 30 casos válidos falha com mensagem clara em vez de gerar ou repetir perguntas; conjuntos menores podem ser executados explicitamente com limite customizado, identificados como exploratórios. O preset reference usa os casos disponíveis até o limite e informa a quantidade real.

Execução iniciada explicitamente pelo operador. Nesta entrega, rodar testes unitários, integração com RAG substituído por doubles e verificações de exportação, sem iniciar bateria real de 30/200 consultas ou baixar um modelo pesado automaticamente. Validar a métrica ROUGE real com fixtures de teste; BERTScore será testado com backend controlado e terá smoke test real opcional com modelo já disponível ou download explicitamente autorizado. Resultados de testes de software ficam identificados e separados de resultados do RAG.

## Dataset

Entrada JSONL ou JSON contendo lista de casos. Campos obrigatórios: `id`, `category`, `question`, `ground_truth`, todos strings não vazias. A pergunta deve ser aceita pelo `QueryRequest` existente. Categorias são livres/configuráveis; documentar sugestões de factual, paráfrase, múltiplos documentos, interpretação, sem resposta e ambígua/adversarial, sem quotas artificiais.

Campos opcionais:

- `expected_sources`: referências/IDs documentais esperados, apenas para rastreabilidade nesta entrega.
- `metadata`: objeto de metadados documentais e de revisão humana, preservado.
- `expected_behavior`: `answer` (padrão), `abstain` ou `clarify`.
- `split`: `development` (padrão) ou `final`.
- `group_id`: família de casos relacionados, quando conhecida, para impedir vazamento entre splits.

Rejeitar IDs duplicados e perguntas duplicadas após normalização Unicode NFKC, casefold e compactação de espaços; não contar repetições de execução como perguntas únicas. Não exigir a criação de splits com dados insuficientes. Quando houver splits, rejeitar mesma pergunta ou grupo em development e final, não selecionar final no piloto e exigir seleção explícita do split final. O pipeline não usa resultados finais para ajustes automáticos; documentar que a disciplina de não ajustar manualmente com esse conjunto depende da equipe.

Seleção reprodutível por seed, sem distribuição artificial por categoria; registrar exatamente IDs e ordem selecionados. Mesma seed, mesmo dataset e mesmas opções devem selecionar os mesmos casos. Dataset completo e subconjunto selecionado recebem hashes distintos.

## Integração e captura

Adapter fino instancia e fecha o serviço já existente. Cada pergunta é validada com o schema de produção e enviada uma vez por repetição configurada a `RagService.query`. Registrar duração com relógio monotônico envolvendo apenas essa chamada; download/carregamento do avaliador e métricas têm tempos separados.

Persistir ID, categoria, split, repetição, pergunta, referência, status original do RAG, resposta bruta, sources, timestamps, duração, erro tipado, configurações e hashes. Registrar o que a interface já disponibiliza; não adicionar hooks ao RAG para obter hits brutos.

Cada tentativa é independente em relação ao tratamento de exceções: falha não interrompe a bateria. Não implementar retries automáticos de consultas. Timeout do RAG usa os timeouts existentes; o pipeline não promete um timeout rígido global que o serviço síncrono não oferece. O tempo total pode incluir várias chamadas limitadas por seus próprios timeouts.

`empty_knowledge_base` é inelegível para avaliação de qualidade e nunca recebe zero artificial. Resposta vazia, exceção e timeout ficam explicitamente sem pontuação. `insufficient_context` com mensagem não vazia é uma abstenção sinalizada pela interface, distinta de falha operacional.

## Persistência, identidade e retomada

Cada diretório de execução contém manifest, checkpoints transacionais em SQLite e os artefatos exportados. Chave de tentativa: `(case_id, repeat_index)`, dentro de uma identidade de execução imutável. Proibir dois processos alterando a mesma execução simultaneamente.

Manifest registra dataset/IDs/ordem, parâmetros de seleção, repetição, seed, versão declarada do RAG, Git SHA, configurações relevantes, hash do prompt existente, modelos/digests Ollama disponíveis, identificador declarado da versão do corpus e metadados da coleção. Não registrar credenciais em URLs/configurações.

Exigir identificador de corpus para coleta real. A coleção deve permanecer estável durante cada bateria; contagem e metadados não provam que todo o corpus é idêntico. Essa limitação será explícita: a equipe é responsável por congelar a versão indicada. Não gerar snapshot, reindexar ou copiar a coleção nesta entrega.

Salvar resposta imediatamente após cada consulta e antes das métricas. Retomada confere manifest e hashes, reutiliza respostas concluídas e não as consulta novamente. Se o processo morrer depois de enviar uma consulta e antes de salvar a resposta, a tentativa fica `uncertain`: não é possível garantir exactly-once. Não reexecutá-la automaticamente; exigir opção explícita para tentar de novo, registrando a possibilidade de chamada duplicada. Falhas concluídas também exigem opção explícita de retry. Recalcular métricas não altera os checkpoints da coleta.

Mudanças de dataset, configuração do RAG, corpus declarado ou repetições exigem outra execução. Configurações de métricas são versionadas separadamente para permitir reavaliar respostas salvas sem destruir resultados anteriores. Alterar seed/reamostragens/margem de erro só recalcula estatísticas.

## ROUGE-L

Usar `rouge-score`, tipo `rougeL`, que calcula LCS sobre sequências de tokens; registrar Precision, Recall e F1 com peso simétrico. Não implementar LCS manualmente nem usar `rougeLsum` como substituto.

A tokenização padrão da biblioteca restringe tokens a ASCII alfanumérico e pode fragmentar palavras portuguesas acentuadas. Fornecer apenas um tokenizer Unicode à API oficial: normalização NFC, casefold e extração de sequências de letras/números Unicode, preservando acentos. Pontuação separa tokens; não remover stopwords, não aplicar stemming inglês e não remover acentos. Registrar a política e versões. Citações numéricas são mantidas por padrão para não modificar silenciosamente as respostas avaliadas; qualquer política alternativa futura deve ter identidade própria.

## BERTScore

Usar `bert-score` e um único `BERTScorer` por etapa, reaproveitado entre lotes. Proposta do assistente para português brasileiro: `neuralmind/bert-base-portuguese-cased` (BERTimbau Base), `num_layers=12`, `lang=pt`, `idf=False`, `rescale_with_baseline=False`, tokenizer lento/cased e batch inicial 4. CPU é o padrão reproduzível; permitir CUDA/MPS quando disponível, sem exigir GPU.

BERTimbau é um encoder treinado para português brasileiro, não o Qwen usado para geração/recuperação. A escolha de 12 camadas é configuração inicial explícita, sem alegar calibração ótima no domínio fiscal. Modelo, camadas, device, batch e demais parâmetros são configuráveis por CLI/arquivo, com ambiente opcional e precedência documentada (CLI > arquivo > ambiente > padrões).

Resolver e registrar a revisão imutável do modelo. Como BERTScorer não recebe `revision` diretamente, carregar snapshot local do Hub com revisão fixada e passar esse diretório à biblioteca, sem alterar sua implementação. Modelo local também pode ser informado; registrar hash do conteúdo/configuração. Downloads só em preparação explícita ou com opção de autorização, não como efeito oculto de report/bootstrap. Usar somente modelos compatíveis com Transformers, sem executar código remoto do modelo.

Registrar revisão, versão de BERTScore/Transformers/PyTorch, hash retornado pelo BERTScorer e fingerprint próprio estável dos parâmetros. O hash nativo pode incluir caminho local; o fingerprint próprio registra modelo/revisão/normalização de forma independente do caminho.

Para IDF habilitado, fixar o corpus de referências dos IDs selecionados, uma referência por pergunta única, sem multiplicar pesos por repetições; salvar hash desse corpus. Para rescaling habilitado com modelo sem baseline compatível, exigir baseline explícito e registrar seu hash; não ignorar a configuração nem presumir baseline inglês válido para português.

Preservar caixa e acentos em BERTScore, normalizar apenas NFC e espaços de forma documentada. Verificar comprimento tokenizado antes de pontuar. Padrão: textos que excedem o limite do encoder recebem falha específica de BERTScore, mantendo ROUGE se calculável; não truncar silenciosamente. Uma opção explícita de truncamento pode habilitar diagnóstico com comprimentos e aviso, separando configurações na comparação.

Registrar Precision, Recall e F1. Falha em lote deve ser isolada para identificar os casos afetados sem perder os outros; não recarregar o modelo por pergunta. Pontuações ausentes são `null`, com erro por métrica e denominadores específicos.

## Abstenções e ambiguidade

Calcular similaridade textual de respostas não vazias retornadas legitimamente, incluindo abstenções sinalizadas, mas separar agregados por `expected_behavior`. Os resultados principais de qualidade de resposta usam os casos `answer`; os de `abstain` e `clarify` são diagnósticos separados.

Para perguntas sem resposta, reportar quantidade de casos, sinal de abstenção do status, resposta produzida e fontes, com correção comportamental inicialmente `not_assessed`. Uma resposta com status `answered` também pode conter uma recusa textual: não inferir correção por similaridade nem por heurística lexical. Permitir arquivo de adjudicação humana por execução/ID/repetição, com julgamento e justificativa, para calcular acertos comportamentais revisados. Casos ambíguos seguem a mesma lógica para comportamento esperado de esclarecimento.

## Estatística

Para ROUGE-L F1 e BERTScore F1, geral e por categoria/expected_behavior:

- Contagens distintas de perguntas únicas, tentativas planejadas/executadas, respostas válidas, falhas operacionais, métricas calculadas e métricas ausentes. Casos parcialmente válidos ficam identificados, sem contagens sobrepostas apresentadas como partição.
- Média, mediana, desvio-padrão amostral (`ddof=1`), mínimo, máximo e percentis 5, 25, 75 e 95.
- IC 95% da média por bootstrap percentil de casos com reposição, 5.000 reamostragens e seed 42 por padrão, configuráveis.
- Sem observações: estatísticas `null`; com uma observação: média disponível, desvio amostral/IC/dimensionamento `null`; não inventar confiança. Com variância zero e ao menos dois casos, registrar IC degenerado e limitação.

Múltiplas execuções opcionais por pergunta são preservadas individualmente. Para agregados, cada pergunta contribui com a média de suas repetições válidas, mantendo peso igual por pergunta; bootstrap reamostra perguntas, nunca trata repetições como amostras independentes. Reportar variação entre repetições por pergunta e cobertura/falhas de repetições separadamente. Relações desconhecidas entre perguntas, como paráfrases da mesma fonte, continuam uma limitação de independência; grupos conhecidos não podem vazar entre splits.

Dimensionamento separado por métrica: aproximação `ceil((1.96*s/E)^2)`, margem inicial proposta `E=0.05` em unidades da métrica, configurável. Informar resultado bruto e mínimo operacional de dois casos quando houver desvio estimável, sem alegar que variância observada zero prova suficiência. Usar desvio dos valores por pergunta do piloto; comparar necessidade estimada ao número de perguntas independentes elegíveis disponíveis no split. Sem dados suficientes, informar indisponibilidade; não invalidar resultados automaticamente. Explicar hipóteses de independência, representatividade e aproximação normal, além das limitações de piloto pequeno e seleção por sucessos.

Não interpretar métricas como porcentagem de correção factual, não definir limiares universais e não converter scores em aprovação/reprovação.

## Comparação entre versões

Comparar duas execuções salvas. Exigir mesmos IDs selecionados e mesmas perguntas/referências/categorias/expected_behavior/split, configurações de métricas equivalentes, mesma revisão/IDF/baseline/normalização e desenho de repetições compatível. O RAG e seu corpus podem ter versões diferentes: essa diferença deve ficar explícita no manifest.

Parear por `(case_id, repeat_index)` com ambas as métricas disponíveis para cada análise; agregar diferenças por pergunta antes do bootstrap. Para cada métrica, apresentar diferenças por pergunta e das médias, IC por bootstrap pareado com os mesmos índices nas duas versões, contagem de vitórias/empates e recortes por categoria. Denominador e perguntas/repetições excluídas ficam explícitos. Não comparar médias calculadas sobre subconjuntos distintos como se fossem pareadas. Não exigir segunda versão para executar a avaliação principal.

## Artefatos e Excel

Diretório de execução com identidade única, contendo manifest/checkpoints e, para cada configuração de métricas/relatório:

- `results.json`: resultados completos, textos originais, fontes, metadados, erros e pontuações.
- `results.csv`: visão tabular com uma linha por tentativa e colunas de status/erros por métrica.
- `summary.json`: agregados, ICs, cobertura, variabilidade, estimativas amostrais e comparação quando houver.
- `report.md`: relatório em português cobrindo as 12 seções solicitadas, com conclusões descritivas baseadas somente no que foi observado, fontes metodológicas e limites.
- `report.xlsx`: planilha real, produzida com openpyxl, com abas Resultados, Resumo, Categorias, Falhas, Configuração, Abstenções, Variabilidade, Tamanho amostral, Fontes e Comparação quando aplicável. Cabeçalhos, filtros, congelamento, formatos numéricos e unidade dos scores explícitos.
- Gráficos PNG de distribuição, relação entre métricas e comparação por categoria quando houver dados suficientes; incluir no relatório e no Excel. Não gerar gráficos de distribuições inexistentes.

JSON é o registro integral. Excel tem limite de 32.767 caracteres por célula: preservar textos maiores em fragmentos numerados na aba Textos, com referência à tentativa/campo, em vez de truncar sem aviso. Neutralizar fórmulas nos campos textuais de CSV/Excel e tratar caracteres de controle incompatíveis com XLSX, registrando a transformação somente na apresentação; os originais permanecem no JSON.

O comando template gera uma planilha vazia utilizável enquanto o dataset real não existe. Fixtures de teste podem gerar relatórios temporários para verificar formatos, mas não se tornam dataset de referência nem resultados de demonstração do produto.

## Testes e critérios de aceitação

- Validação do dataset: campos, duplicatas, splits/grupos, categorias livres e limites de seleção sem geração de casos.
- Integração interna com doubles: sucesso, vazios, abstenção, falha, timeout e preservação das fontes, sem chamadas reais ao LLM.
- Retomada: nenhuma nova chamada para respostas salvas; tentativa incerta não repetida automaticamente; divergência de manifest rejeitada; métricas e bootstrap nunca consultam RAG.
- Métricas: ROUGE oficial com textos portugueses acentuados e expectativas verificáveis; BERTScore com backend controlado, carregado uma vez, lotes, overflow, falha parcial e metadados. Smoke real opcional conforme disponibilidade/autorização.
- Estatística: valores conhecidos, `ddof=1`, seed, casos vazios/unitários, reamostragem por pergunta, dimensionamento e bootstrap pareado.
- Relatórios: JSON/CSV/XLSX legíveis, abas/totais corretos, ausência de zero artificial para falhas, textos extensos, fórmulas tratadas e relatório sem conclusões inventadas.
- Executar suíte atual do backend e testes novos, sem alterar a coleção da aplicação. Entregar comandos exatos de instalação, preparação, piloto, conjunto inicial, retomada, comparação e interpretação.

## Decisões deixadas à implementação

Versões exatas compatíveis, nomes finais de opções e classes, estratégia de lock/SQLite, schema detalhado dos checkpoints, seleção determinística concreta e apresentação dos gráficos. Valores iniciais e escolhas adicionais do assistente estão descritos como propostas; aprovação deste desenho os incorpora ao escopo. Não introduzir servidor, UI web, agente avaliador ou serviço pago.

## Referências verificadas

- Lin (2004), ROUGE: https://aclanthology.org/W04-1013/ e PDF https://aclanthology.org/W04-1013.pdf
- Zhang et al. (2020), BERTScore: https://arxiv.org/abs/1904.09675 e texto https://arxiv.org/html/1904.09675v3
- Databricks, conjuntos representativos e revisão humana: https://docs.databricks.com/aws/en/agents/tutorials/ai-cookbook/evaluate-define-quality
- Implementação ROUGE/tokenizer: https://github.com/google-research/google-research/blob/master/rouge/tokenize.py
- Implementação BERTScore: https://github.com/Tiiiger/bert_score e https://raw.githubusercontent.com/Tiiiger/bert_score/master/bert_score/scorer.py
- Modelo português dos autores: https://huggingface.co/neuralmind/bert-base-portuguese-cased
- Revisões e cache do modelo: https://huggingface.co/docs/huggingface_hub/guides/download
- Excel: https://openpyxl.readthedocs.io/en/stable/
