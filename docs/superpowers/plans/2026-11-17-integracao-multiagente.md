# Primeira entrega da integração multiagente do Sócio Digital

O objetivo é permitir que uma empresa faça uma pergunta fiscal, confirme a competência, leia uma resposta fundamentada, abra a versão citada da norma e salve uma orientação como tarefa. A primeira entrega inclui supervisor, especialista jurídico, diagnóstico fiscal e planejamento. Referências de projeto: [desenho multiagente](../../arquitetura/diagramas/socio-digital-design-backend-2.excalidraw) e [especificação do MVP](../specs/2026-11-10-backend-mvp-design.md).

## Ponto de partida

O frontend do PR #24 já usa sessão, empresas, conversas, operações, evidências, cálculos, tarefas e biblioteca. A implementação deve partir de uma revisão que contenha esse frontend. Na inspeção local de 17/11, a API respondeu em /health, /ready indicou indisponibilidade no RAG e norm_versions estava vazia. O teste de conversa com o banco real cobre o caminho sem acervo. Uma resposta com citação exige uma versão publicada e recuperável.

## Desenho proposto

Manter FastAPI, PostgreSQL e o worker existentes. Implementar os quatro papéis como módulos Python no worker, com entradas e saídas tipadas em Pydantic. Um agente pode usar uma ferramenta determinística sem fazer uma chamada ao modelo. O navegador continua enviando uma mensagem, recebendo HTTP 202 e consultando a operação e o histórico. A autorização da empresa ocorre na API e o worker usa o contexto persistido da operação.

| Papel | Entrada e ferramentas | Saída e limite |
|---|---|---|
| Supervisor | Pergunta, empresa autorizada, competência, histórico da conversa | Seleciona etapas, solicita campos faltantes e consolida os resultados validados. Uma passagem por especialista por execução, com tentativas técnicas limitadas pelo worker. |
| Jurídico | Pergunta, data de referência, catálogo e índice legal_versions_v1 | Afirmações com identificadores de documento, versão e âncora recuperados. Sem fonte aplicável, informa contexto insuficiente. |
| Diagnóstico fiscal | Perfil, competência, evidências da empresa e motor de cálculo existente | Fatos com origem, data e escopo. Simulação inclui premissas e versão da regra revisada. Pagamento sem comprovação oficial fica não verificado. |
| Planejamento | Fatos e referências validados, incluindo lacunas | Até três orientações vinculadas ao suporte disponível. A ação explícita do usuário cria a tarefa pelo endpoint existente. |

Exemplo de execução: uma pergunta sobre a regra do DAS e o pagamento do mês aciona jurídico e diagnóstico fiscal. Se faltar competência, o supervisor pede confirmação e retoma a mesma operação. A síntese distingue a regra aplicável da evidência de pagamento. Uma consulta apenas normativa pode usar somente o jurídico.

## Sequência de implementação e aceite

1. **Alinhar o contrato HTTP.** Em frontend/src/services/api.ts, interpretar error.message e error.fields das rotas do produto e preservar detail das rotas legadas. Mapear body.cnpj ao campo cnpj. Atualizar frontend/src/tests/api.test.ts com o envelope real. Aceite: erro de CNPJ aparece no campo correto, conflito de cadastro informa o motivo e sessão expirada pede novo acesso.
2. **Preparar uma referência reproduzível.** Conferir separadamente Qdrant, modelos de embedding e geração no Ollama, fila e storage. Pela CLI de backend/api/app/legal, ingerir uma norma do acervo com fonte oficial, versão e vigência conferidas. Aceite: versão pronta em /normas, texto acessível pelo navegador e trecho recuperado pelo índice versionado. Registrar qual documento, versão e pergunta reproduzem o resultado.
3. **Conectar os quatro papéis no worker.** Evoluir backend/api/app/assistant/orchestrator.py reaproveitando a recuperação jurídica, a validação de citações e os serviços fiscal e de evidências. Vincular cada etapa ao operation_id e à empresa, registrar estado, duração e falha, e reutilizar resultados persistidos na retomada. Aceite em backend/api/tests/mvp/test_assistant.py: pergunta mista consulta os dois especialistas, esclarecimento retoma a operação, fonte ausente gera resposta limitada e reentrega do job não duplica a resposta nem o cálculo.
4. **Fechar o fluxo no navegador.** Em frontend/src/pages/Assistente.tsx e Leitor.tsx, conferir o resultado consolidado contra as respostas reais do worker. Preservar leitura das mensagens já gravadas. Aceite: resposta após confirmação, citação abre a versão e o trecho corretos, retorno recupera a mensagem e um próximo passo vira uma única tarefa. Testar também versão indisponível e regra fiscal ausente para a competência.
5. **Automatizar a regressão.** Estender frontend/e2e e backend/api/tests/mvp/test_mvp_workflow.py em ambiente isolado. No CI, usar documentos de teste e respostas de modelo controladas para verificar contratos e persistência. Na homologação, repetir a pergunta de referência com Ollama e acervo reais. Aceite adicional: trocar de conta não permite acessar a conversa ou o anexo da outra empresa, e atualizar uma tarefa não altera a verificação fiscal.

## Definição de pronto

Guardar como evidência da entrega a execução dos testes, o identificador da operação, as etapas realizadas e a versão jurídica aberta no leitor. Para o cenário com simulação numérica, usar uma competência coberta por regra revisada com referência registrada. Nenhum dado fiscal precisa ser presumido para demonstrar o cenário de ausência de regra.

## Reprodução local da primeira entrega

Com a stack local do Compose ativa, os modelos configurados no Ollama e as migrações aplicadas, execute a partir de `backend/api` com o ambiente Python do backend ativado.

```sh
python -m app.legal.cli ingest --file ../../data/referencias/lc123-art13.md --metadata ../../data/referencias/lc123-art13.json --key lc123-art13-caput-2007-07
```

A chave permite repetir a ingestão do mesmo excerto. A biblioteca identifica o conteúdo como o caput do art. 13 da LC 123/2006. A versão contém somente a introdução do artigo e remete à publicação oficial da Câmara dos Deputados.

Para repetir a homologação com o modelo real, defina `PW_LEGAL_REFERENCE=1` e execute `npm run test:e2e` em `frontend`. O teste cadastra uma conta de demonstração, pergunta sobre a periodicidade do recolhimento e o pagamento da guia e confirma outubro de 2026. A asserção no leitor exige que o texto destacado contenha “documento único de arrecadação”. O teste volta à conversa e verifica a orientação na lista de tarefas.

Na execução local de 17/11/2026, a operação `176ab20a-6c87-475a-b157-91519af7535b` consultou supervisor, diagnóstico fiscal, jurídico, síntese e planejamento. A citação abriu a versão `ddadc314-274a-4052-8e10-bca277ded01d` na âncora `s1-4c5266be658f`. O próximo passo gerou a tarefa `f92c7782-d19d-4810-8bde-eca0edfd54f8` na conta de teste. Os UUIDs pertencem ao banco local e variam entre instalações.
