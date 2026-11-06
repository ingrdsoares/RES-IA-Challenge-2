# Arquitetura de refino do acervo tributário

O recorte confirmado é **todos os regimes tributários, com foco no Distrito Federal**. A camada de refino organiza os materiais coletados, reduz repetições na consulta e distingue o núcleo tributário de dados estruturados, material complementar, histórico e itens incertos.

## O que se considera repetição

Há três problemas diferentes:

1. Arquivos idênticos: podem compartilhar um conteúdo identificado por hash.
2. Mesma norma em vários coletores: as ocorrências são ligadas a um documento lógico, sem perder as fontes.
3. Versões e extrações diferentes: continuam distintas, mesmo quando o hash primário coincide.

O exemplo real da SC Cosit 140/2025, ato 145726, mostra por que isso importa: uma coleta tem ementa/anexos e a outra também preserva uma visão adicional. Ambas possuem o mesmo hash primário. Fundi-las apenas por esse hash perderia informação.

## Fluxo

~~~mermaid
flowchart TD
    A[Coleta e originais preservados] --> B[Catálogo auditado]
    B --> C[Identidade e proveniência]
    C --> D[Documentos e versões]
    D --> E[Conteúdos únicos por hash]
    C --> F[Registro de datasets]
    D --> G[Política por perfil]
    G --> H[Núcleo candidato de consulta]
    G --> I[Complementares, histórico e revisão]
    D --> J[Contrato PostgreSQL]
    F --> J
~~~

A coleta permanece em backend/crawler/data. O novo pipeline fica em [backend/refino](../backend/refino/README.md), com saídas isoladas em backend/refino/data. Não há exclusão dos originais nem limpeza destrutiva nesta etapa.

## Modelo de dados

| Entidade | Responsabilidade |
|---|---|
| Documento | Identidade por autoridade/ID ou URL conservadora |
| Versão | Conteúdo diferente associado a um documento |
| Conteúdo | Markdown normalizado armazenado uma vez por hash |
| Ocorrência | Snapshot de entrada, fontes, datas, hashes e visões |
| Classificação | Perfil/política, categoria e motivos verificáveis |
| Dataset | Referência a CNPJ, tabelas, códigos e schemas com seus artefatos |
| Relação | Vínculos explícitos, inicialmente anexo/ato |

Atos RFB são identificados pelo ID do ato. Anexos usam ID do ato e ID do anexo. Outras fontes mantêm parâmetros e fragmentos funcionais de URL. Não se usa título ou ano isolado como identidade.

O texto mantém artigos, números, valores, tabelas e rasuras. A normalização limita-se a Unicode NFC, finais de linha e retirada de frontmatter reconhecido como metadado de coleta. Similaridade aproximada não determina exclusão.

Uma representação preferida é escolhida por critérios técnicos de integridade/cobertura. Essa escolha não significa que o texto esteja vigente. As demais versões e todas as ocorrências continuam acessíveis.

## Política de relevância

| Categoria | Destinação |
|---|---|
| Núcleo | Candidatos tributários federais/distritais no perfil selecionado |
| Complementar | Apoio, editoriais, modelos e atos administrativos operacionais |
| Histórico | Agendas e competências históricas explicitamente identificadas |
| Revisão | Relevância ou integridade a confirmar |
| Evidência | Índices, comparações e trechos já representados no documento de origem |
| Dados estruturados | Cadastros, tabelas, códigos e schemas, consultados separadamente |

O perfil padrão tributario_df cobre todos os regimes. Perfis alternativos permitem MEI/Simples DF ou cobertura nacional. A política e seus motivos ficam versionados; nada é apagado por palavra-chave. Tipos explícitos de pessoal ficam fora do núcleo, mesmo mencionando Simples Nacional.

A classificação é candidata. Portarias genéricas ainda podem tratar tanto de procedimentos fiscais como de organização interna, exigindo revisão de ementa. Leis antigas não são descartadas por ano; vigência e produção de efeitos continuam dependentes de verificação.

CNPJ é registrado como dataset com referência ao manifesto e às partições completas. Não se transforma uma tabela parcial de Markdown em prova de cobertura de todo o cadastro, nem se copiam centenas de milhares de empresas para o índice textual.

## Execução e controle

O manifesto registra hashes do catálogo, do código e da política, além da identidade dos metadados/Markdown lidos. Alterações na auditoria do catálogo geram outra execução, impedindo reutilizar um núcleo calculado antes de um problema de integridade.

As saídas são publicadas em diretório próprio somente após geração completa. Reexecução valida todos os hashes antes de reutilizar resultados. Caminhos de entrada e saída são delimitados; uma saída não pode sobrescrever a camada coletada.

O [contrato SQL](../backend/refino/schema.sql) prepara PostgreSQL com integridade entre documento, versão, ocorrência e dataset. Ele não foi aplicado a um servidor nesta etapa. O [README do refino](../backend/refino/README.md) descreve os JSONL e a reprodução.

## Etapas seguintes

1. Revisar a fila e os casos administrativos ambíguos.
2. Fragmentar normas por dispositivo, preservando contexto da visão e competência.
3. Normalizar relações explícitas de alteração/revogação.
4. Validar/importar o contrato no PostgreSQL.
5. Conectar busca com filtros por regime, competência, jurisdição e natureza.

O núcleo reduz ruído e repetição na consulta, mas não substitui revisão jurídica, validação de OCR ou cálculo determinístico de tributos.

## Primeira execução validada

| Medida | Quantidade |
|---|---:|
| Ocorrências preservadas | 7.213 |
| Documentos lógicos | 6.291 |
| Versões | 7.040 |
| Conteúdos únicos | 6.877 |
| Repetições textuais evitadas | 225 |
| Ocorrências agrupadas por identidade | 922 |
| Documentos no núcleo candidato | 5.024 |
| Registros de datasets | 37 |

A [validação real](refino-validacao.json) conferiu 6.889 artefatos e todas as ocorrências, sem erros. O [handoff independente de modelo](../handoff/refino/CONTINUAR.md) reúne decisões, código, estado e próximos passos. A instrução de parada ao atingir o limite da sessão também está registrada.
