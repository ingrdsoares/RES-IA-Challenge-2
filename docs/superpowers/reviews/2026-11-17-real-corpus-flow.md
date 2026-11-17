# Fluxo com acervo real — 2026-11-17

O usuário autorizou ignorar a vigência para testar o fluxo. Nenhuma data foi inventada.
A opção interna `ignore_validity_for_test` remove apenas o filtro temporal nessa chamada;
a API pública não expõe essa opção e o comportamento padrão continua exigindo datas.
Cada fonte recuperada registra `validity_check=ignored_for_test`.

## Carga realizada

- Origem: `data/recorte-rag-v1/recorte-publico.csv.gz`, sem os textos demonstrativos de `data/raw/recorte_demo`.
- 4.026 documentos armazenados no catálogo PostgreSQL e originais no bucket S3; zero falhas de importação.
- Três versões indexadas para este experimento: LC 123/2006 integral do recorte e dois documentos identificados no corpus como Resolução 140/2018. Total: 348 trechos.
- Os outros 4.023 documentos estão recebidos, com jobs de ingestão pendentes; não estão integralmente indexados nem disponíveis ao assistente.
- Serviços da aplicação em 5432/6379/9000/6333, com volumes persistentes; os testes automatizados usam portas e banco separados.
- A revisão temporal e territorial de cada norma não faz parte deste experimento. O escopo territorial da importação foi derivado do domínio da fonte; requer revisão posterior.

## Resultado técnico e semântico

| Cenário | Etapas executadas | Resultado |
| --- | --- | --- |
| Pergunta sobre valores fixos mensais do MEI | Supervisor, jurídico, síntese | Execução e conteúdo pertinentes, com citação da LC 123/2006 coletada da Câmara |
| Norma + pagamento de 2026-10 + próximo passo | Supervisor, jurídico, fiscal, planejamento, síntese | Execução concluída; estado fiscal corretamente não verificado e ação explícita. Conteúdo jurídico reprovado: confundiu recolhimento mensal com regras de desenquadramento por excesso de receita |

Conclusão: o teste comprova execução ponta a ponta com documentos reais, mas não aprova a qualidade jurídica do segundo cenário. Validar documento/versão/âncora não basta para demonstrar que a conclusão corresponde ao assunto perguntado. A recuperação da parte jurídica de perguntas compostas e a pertinência das afirmações precisam de ajuste e avaliação próprios.

Perguntas, respostas, fontes com URLs originais, ações e saídas de cada agente estão em
`2026-11-17-real-corpus-flow.json`. O recibo da carga está em `2026-11-17-real-corpus-import.json`.

## Correção encontrada no ambiente migrado

O banco da aplicação revelou ausência de `agent_steps.tool_result`, que existia apenas nos
schemas criados diretamente pelo ORM. A migração incremental `0013_agent_tool_result`
foi aplicada sem remover dados. O teste de migração agora verifica explicitamente essa coluna.

Regressão final: 374 aprovados, dez opcionais pulados, em 33,17 segundos. Testes direcionados
comprovam que ignorar vigência exige opção explícita e não altera o comportamento padrão.
A busca RAG legada de `/ready` apontou incompatibilidade da antiga coleção `knowledge_base`;
a recuperação jurídica deste experimento usa a coleção separada `legal_versions_v1`.
