# Backend multiagente — primeira entrega

Status: aprovado pelo usuário em 2026-11-17, com a instrução de prosseguir. A abordagem incremental foi escolhida pelo usuário; as escolhas técnicas propostas neste documento fazem parte do desenho aprovado.

## Objetivo e escopo

Evoluir o assistente empresarial para um supervisor LLM com três especialistas: jurídico, diagnóstico fiscal e planejamento. Entregar o fluxo completo usando os serviços existentes, com evidências rastreáveis, validação determinística e retomada após falhas.

Fontes: diagramas `docs/arquitetura/diagramas/socio_digital_arquitetura.excalidraw` e `docs/arquitetura/diagramas/socio-digital-design-backend-2.excalidraw`, código atual de `backend/api/app` e escolha do usuário pela abordagem 1 nesta conversa.

Entram nesta entrega: supervisor e especialistas reais com chamadas LLM e responsabilidades distintas; contratos tipados; persistência de runs e etapas; ferramentas restritas; recuperação jurídica versionada; cálculos e evidências existentes; plano de até três ações; validação; API de acompanhamento; telemetria e testes de integração.

Ficam para depois: conectores oficiais, consentimentos para provedores externos, lembretes e seus canais, frontend, autenticação de equipe, implantação pública e publicação de regras fiscais reais revisadas. Não será necessário reescrever autenticação, biblioteca, tarefas ou motor fiscal.

## Abordagens consideradas

1. **Evolução incremental com os serviços atuais — escolhida pelo usuário.** Permite validar agentes, contratos e recuperação de falhas antes de depender de integrações externas.
2. **Entrega conjunta com conectores e lembretes.** Amplia o escopo inicial e depende de provedores, credenciais e canais ainda não definidos. Adiada.

Escolhas técnicas propostas pelo assistente: manter FastAPI, PostgreSQL, Redis/RQ, S3, Qdrant e Ollama; implementar inicialmente a coordenação com código Python e contratos Pydantic, sem introduzir framework de agentes. Continuar usando os modelos configurados. Um agente é uma etapa LLM com entrada, saída e ferramentas próprias; não apenas um novo nome para o fluxo fixo atual.

## Base existente e mudanças necessárias

- `assistant/service.py` já cria operações idempotentes, fixa a empresa da conversa e registra contexto. Deve passar a vincular cada operação de resposta a uma execução multiagente.
- `assistant/orchestrator.py` hoje consulta evidências e executa cálculo ou RAG em um fluxo fixo. Sua responsabilidade passa a ser coordenar as etapas persistidas.
- `assistant/tools.py` já filtra normas por publicação, território, vigência e âncoras. Deve virar uma ferramenta do agente jurídico, preservando essas garantias.
- `jobs/worker.py` atualmente mantém a transação da operação durante o handler. A execução multiagente precisa de checkpoints confirmados em transações curtas e chamadas externas fora delas.
- Motor fiscal, evidências e tarefas continuam sendo serviços de domínio. Agentes não acessam livremente SQL, bucket, rede ou outras empresas.
- Telemetria atual cobre `/rag/query`; execuções do assistente precisam de rastreio próprio.

## Fluxo de execução

1. A API autentica, verifica a empresa e a conversa, aplica limites e registra mensagem, operação e run na mesma transação. Repetir a chave com o mesmo pedido devolve a mesma operação; payload diferente continua sendo conflito.
2. A resolução existente captura o perfil e os dados explícitos. O supervisor recebe esse contexto e um histórico limitado, identifica a intenção e produz um plano tipado com especialistas necessários, dependências e dados ausentes.
3. O código valida o plano. A empresa e o proprietário vêm da sessão e da conversa; o LLM não pode escolhê-los. Dados financeiros e confirmações não podem ser presumidos.
4. Se faltar competência ou entrada necessária, a execução entra em `awaiting_data`. A resposta pede apenas os dados ausentes. A confirmação retoma o mesmo run e preserva o histórico de etapas e revisões do contexto, sem editar automaticamente o perfil.
5. Jurídico e diagnóstico fiscal executam conforme o plano. Cada um usa apenas suas ferramentas. São etapas logicamente independentes; a primeira entrega as executa sequencialmente para controlar memória e concorrência no Ollama local. Paralelismo fica como otimização posterior.
6. O agente de planejamento recebe apenas resultados validados e propõe de zero a três ações. Pode ser dispensado em perguntas que não pedem nem exigem próximos passos.
7. O supervisor sintetiza os resultados em uma chamada final. A validação em código confere estrutura, referências e limites antes de persistir a mensagem final e concluir a operação.

Máximo proposto: cinco chamadas LLM lógicas por rodada — plano, jurídico, fiscal, planejamento e síntese. Especialistas desnecessários são omitidos. Não há delegação recursiva ou ciclos autônomos. Solicitar dados encerra a rodada; uma confirmação explícita pode iniciar outra dentro do mesmo run. Limites por rodada e por run impedem confirmações ilimitadas.

## Responsabilidades e ferramentas

**Supervisor:** escolhe somente agentes da lista permitida, ordena dependências, solicita esclarecimentos e sintetiza. Não chama diretamente RAG, motor fiscal nem consultas de evidências. Pode responder saudações e mensagens sem conteúdo fiscal sem acionar especialistas.

**Jurídico:** interpreta os trechos obtidos pela ferramenta jurídica. Retorna afirmações associadas a `document_id`, `version_id` e `anchor_id`, além de limitações. Não confirma situação empresarial.

**Diagnóstico fiscal:** recebe os resultados do serviço de evidências e, quando solicitado, do motor determinístico. A etapa LLM interpreta os resultados, sem calcular valores. Entradas monetárias usam o contrato Decimal existente e procedência explícita. Texto livre pode fornecer candidatos, mas ambiguidades e condições obrigatórias exigem confirmação; o modelo não pode definir `conditions_confirmed=true` por conta própria. Falta de regra revisada continua retornando `rule_unavailable`.

**Planejamento:** propõe ações sustentadas pelos resultados anteriores, com prioridade e pré-condições. Não cria tarefas nem atribui pagamento ou regularidade. Prazo normativo exige referência verificável; prazo sugerido é identificado como sugestão. Responsável permanece opcional e declarado, sem presumir equipe ou contador.

As ferramentas são executadas por adapters em código, com empresa e proprietário vinculados pelo servidor. O planejamento não recebe credenciais nem ferramentas mutáveis. Nesta entrega não existem ferramentas de envio, pagamento ou consulta fiscal externa.

## Contratos e validação

Contratos Pydantic rejeitam campos inesperados e limitam listas e textos:

- `ExecutionContext`: run, operação, trace, proprietário, empresa, competência, revisão do snapshot e dados confirmados. Identidade e permissões são dados internos confiáveis.
- `SupervisorPlan`: intenção, especialistas selecionados, campos ausentes e justificativa operacional curta. Não armazenar raciocínio interno do modelo.
- `LegalResult`: estado, afirmações com referências permitidas, trechos utilizados e limitações.
- `FiscalResult`: estado, fatos com IDs de evidência, origem, coleta, validade e escopo; referência de cálculo, regra, versão e premissas quando existentes.
- `ActionPlan`: até três ações com título, prioridade, pré-condições, referências de suporte, responsável opcional e prazo opcional qualificado.
- `FinalAnswer`: texto, referências aos resultados, ações e estado de resposta.

O validador rejeita citações inexistentes, referências de outra empresa, evidências fora do escopo ou competência, resultados de cálculos divergentes do motor e ações sem suporte ou pré-condições necessárias. A data relevante é a competência consultada, inclusive em perguntas históricas; não exigir que toda norma esteja vigente hoje.

Resultados normativos, simulações e evidências declaradas permanecem distinguíveis. Evidência ausente ou vencida não vira débito confirmado. Uma guia anexada não comprova pagamento. Concluir uma tarefa não muda os indicadores fiscais.

A validação estrutural não prova a correção semântica de toda frase. Para reduzir esse limite, fatos e valores sensíveis da resposta são renderizados a partir dos resultados estruturados e afirmações jurídicas carregam referências. A avaliação deve medir também contradições e conclusões sem suporte.

Saída inválida não é publicada. Erros transitórios podem repetir a etapa dentro do orçamento; saída inválida termina com estado controlado de falha ou insuficiência, sem ciclos de correção abertos. Se parte das ferramentas falhar, só publicar resposta parcial quando a síntese se limitar aos resultados disponíveis e explicitar a parte não verificada.

## Recuperação jurídica e os dois caminhos de RAG

Preservar `/rag/query` e sua coleção. O assistente continua usando o catálogo e índice jurídicos versionados; não misturar anexos privados no índice compartilhado.

Reaproveitar busca híbrida e reranking existentes por adapters compatíveis com documento/versão/âncora. Criar uma nova geração do índice versionado se o schema vetorial precisar mudar; reconstruir via ingestão administrativa e habilitar explicitamente após validação. Não alterar a coleção existente silenciosamente nem executar reindexação automática no startup.

Busca densa continua disponível como fallback explícito enquanto o índice híbrido não estiver preparado ou o reranker estiver indisponível. Registrar a estratégia utilizada. Filtros de publicação, vigência, território e revalidação no catálogo se aplicam a todas as estratégias, inclusive fallback.

## Persistência, retomada e concorrência

Adicionar migrações para:

- `agent_runs`: vínculo único com operação, conversa, empresa e proprietário; trace; estado; snapshot e sua revisão; plano validado; limites e consumo; início, término e resultado.
- `agent_steps`: run, rodada/revisão de contexto, agente, etapa, estado, tentativa, versão de prompt, modelo, hash de entrada, saída validada, métricas e erro seguro. Restrição única para a identidade lógica da etapa.
- `tool_invocations`: etapa, ferramenta, chave idempotente, referências de entrada/resultado, estado e duração. Dados privados seguem o mesmo isolamento da conversa.

Estados do run: `queued`, `running`, `awaiting_data`, `succeeded`, `failed`. Estados da resposta preservam os significados existentes, como `answered` e `insufficient_context`; estado de execução e estado da resposta são conceitos distintos.

Reivindicar a etapa em transação curta com lease e token de execução; fazer a chamada externa fora da transação; validar e confirmar o resultado em outra transação, apenas se o token ainda for válido. Expiração permite retomada por outro worker, sem aceitar gravação tardia do anterior. Uma etapa concluída com a mesma entrada e revisão não é executada novamente. Resultados de revisões antigas não podem ser reaproveitados se dependerem de dados alterados.

Não prometer execução exatamente uma vez: uma chamada LLM pode repetir após queda entre chamada e checkpoint. Seus resultados não podem duplicar mensagens ou efeitos de domínio. Cálculos passam a ter identidade vinculada a run/etapa, evitando registros duplicados nas retomadas.

Continuar serializando mensagens da mesma conversa sem manter lock durante inferência. Reconciliar leases expirados e retomar runs incompletos pelo mecanismo durável de operações/dispatcher. A mudança de transações não pode quebrar ingestão ou os outros handlers existentes.

## API e compatibilidade

Manter o envio HTTP 202 e os campos atuais `operation_id`, `status`, `status_url` e `missing_fields`. Acrescentar `run_id`, `trace_id` e `run_url` quando houver execução multiagente.

Adicionar consulta autenticada de run e resumo de etapas, com estado, duração, falhas seguras e referências. Não expor prompts completos, raciocínio interno ou payloads privados de ferramentas nesse endpoint. A autorização verifica operação, empresa e conversa; recursos alheios retornam 404.

Preservar `MessageView.next_steps` como lista de textos para os consumidores atuais. Expor as ações estruturadas em campo aditivo. A criação explícita de tarefa por mensagem/índice continua funcionando, preservando o suporte e a origem da ação sem criação automática.

Mensagens históricas continuam legíveis e não ganham runs artificiais. Operações pendentes anteriores à implantação precisam de estratégia explícita no plano: drenagem antes da troca ou conversão idempotente no primeiro processamento. Não exigir reprocessamento de conversas concluídas.

## Limites, observabilidade e segurança

Configurar prazo total, timeout por etapa, chamadas/tokens máximos por run, limite de rodadas de esclarecimento e concorrência por empresa. Proposta inicial: uma execução ativa por empresa, até duas rodadas de confirmação, até duas tentativas por etapa transitória e prazo de processamento de até dez minutos por rodada; espera pelo usuário não consome prazo de inferência. Ajustar os valores por medição com o Qwen local antes de considerá-los definitivos.

Registrar tokens reais quando disponíveis e estimativas identificadas quando não houver medição. Versões de modelo/prompt, estratégia de recuperação, latência, estado, motivo de abstenção e falhas são rastreáveis por run/etapa. No Ollama local, custo monetário permanece não aplicável, sem inventar valores.

Isolamento usa inicialmente a autorização por proprietário já existente, estendida aos novos recursos e ferramentas. Não criar um modelo fictício de organizações; nesta entrega, o proprietário da conta define o tenant. RLS é defesa adicional futura, não uma garantia já implementada.

Tratar texto do usuário e documentos como dados não confiáveis. O executor aplica allowlist de ferramentas e valida todos os argumentos. Logs e métricas não contêm senhas, cookies, documentos ou conversas. Checkpoints com conteúdo necessário ficam protegidos no banco como as mensagens existentes. Sem expurgo automático novo nesta entrega; retenção de produção continua pendente antes de deploy público.

## Verificação e critérios de aceite

1. Pergunta jurídica executa supervisor e jurídico, retorna referência da versão correta e permite resolver a âncora no leitor.
2. Pergunta fiscal usa apenas evidências da empresa e cálculos do motor; ausência de regra revisada não produz valor inventado.
3. Pergunta combinada reúne resultados dos dois especialistas, gera até três ações e preserva referências até a resposta final.
4. Falta de dados pausa o run; confirmação retoma a mesma execução com nova revisão de contexto e sem sobrescrever perfil.
5. Reenvio, concorrência, queda do worker e lease expirado não duplicam mensagem, tarefa ou cálculo e não publicam resultados de worker obsoleto.
6. Citação inventada, referência de outra empresa, competência incompatível e saída fora do contrato são rejeitadas.
7. Tarefas continuam explícitas e sua conclusão não altera situação fiscal.
8. Timeout ou indisponibilidade de modelo, índice ou reranker têm resultado observável, orçamento limitado e fallback documentado.
9. Regressões cobrem autenticação, CSRF, isolamento, ingestão/publicação, histórico e endpoints existentes. Testes de integração usam stack e dados próprios.
10. Smoke test com Ollama real demonstra plano, delegação e síntese, medindo chamadas, tokens e latência. Testes com modelos simulados não substituem essa evidência.

## Sequência proposta e decisões do plano

Implementar primeiro contratos e persistência; depois executor durável; agentes e adapters; validação e integração HTTP; recuperação híbrida versionada; por fim regressões, cenários de falha e demonstração real. A implementação deve manter incrementos verificáveis, sem deixar a API dependente de módulos incompletos.

O plano define nomes finais de schemas/rotas, migrações, índices, leases, tratamento de operações pendentes, limites calibrados e estratégia de publicação do índice híbrido. Alterações que ampliem escopo, publiquem regras fiscais ou introduzam integrações externas voltam para decisão do usuário.
