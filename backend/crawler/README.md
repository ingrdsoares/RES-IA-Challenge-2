# Coleta inicial de dados em Markdown

Consulte o [catálogo das ferramentas](FERRAMENTAS.md) para localizar os módulos, bibliotecas auxiliares e ferramentas de refino.

Coletores de legislação, CNAE e notas explicativas, interpretações da Receita, manuais do Simples/MEI, obrigações, documentação fiscal, tabelas, cadastros e indicadores. Execução manual com resultados em Markdown e originais locais, sem banco de dados. PostgreSQL fica para uma etapa posterior.

## Executar

A partir da raiz do repositório, com Python 3.11+:

```bash
python -m pip install -r backend/crawler/requirements.txt
python -m backend.crawler.cnae
```

Para escolher outro destino:

```bash
python -m backend.crawler.cnae --output ./dados/cnae
```

O destino padrão é `backend/crawler/data/cnae/`, independentemente do diretório de trabalho. O comando imprime o caminho absoluto do Markdown e retorna código 1 em caso de falha. A execução como módulo deve partir da raiz do projeto.

## Arquivos gerados

```text
data/cnae/
└── <sha256-da-resposta>/
    ├── original.json
    └── cnaes.md
```

`cnaes.md` contém metadados (URL, fonte, camada de confiança, instante UTC, hash e quantidade), seguidos de uma seção por código CNAE, ordenada pelo código, com descrição, tabela de hierarquia e listas de atividades e observações disponíveis. Os códigos permanecem textuais, preservando zeros à esquerda. `original.json` guarda os bytes da resposta usada para gerar o Markdown, incluindo campos que não são exibidos.

Uma resposta com o mesmo hash reutiliza a versão existente e mantém a data da primeira coleta; não cria cópias. Conteúdo alterado cria outro diretório e preserva o anterior. O hash identifica os bytes: mudanças apenas na ordenação ou formatação do JSON também criam uma nova versão. O caminho retornado pelo comando identifica a versão daquela execução.

Toda a resposta é validada antes da escrita. Lista vazia, JSON inválido, código duplicado, descrição ausente ou hierarquia inválida interrompem a coleta. Os arquivos são preparados em diretório temporário e publicados juntos, sem substituir versões anteriores. Erros HTTP, de rede e de disco são informados no terminal. Uma versão já existente mas incompleta ou divergente exige revisão dos arquivos.

Os arquivos de `data/` são ignorados pelo Git. Eles ficam no disco local; backup externo ainda não está configurado. Não há agendamento automático nesta fase.

## Painel de coleta

Executor único das frentes de coleta, com uma página local que mostra o estado, as contagens do catálogo e o andamento de cada uma. O servidor atende só o endereço local (`127.0.0.1`) e roda uma rodada por vez.

```bash
python -m backend.crawler.painel                    # abre http://127.0.0.1:8765
python -m backend.crawler.painel --porta 9000 --sem-navegador
python -m backend.crawler.painel --sem-pagina --frentes cnae,mei --rodar-de-novo
python -m backend.crawler.painel --sem-pagina --finais estatisticas,sumarizacao
```

- **Pular:** uma frente selecionada que já tem dados é pulada, a menos que esteja marcada em "rodar de novo" ou que a última execução tenha terminado em erro ou interrompida. Dependências sem dados entram na rodada automaticamente; a prévia mostra o que roda e o que é pulado.
- **Rodar de novo não garante dado novo:** muitos coletores usam a cópia local ou marcas de período fixo, então a frente pode concluir sem criar versão. O conteúdo só muda se a fonte mudou.
- **Parcial:** frente coletada com pendências aparece como "parcial".
- **Parar em duas etapas:** "Parar" pede o fim cooperativo (nada novo inicia, o coletor atual termina e o catálogo ainda é atualizado). Passados 60 s, o coletor atual é encerrado à força e marcado como forçado. No terminal, o primeiro Ctrl+C faz a parada cooperativa e o segundo força o encerramento.
- **Falhas de uma parada:** as falhas que o coletor registra ao ser parado ficam no manifesto dele até a frente rodar de novo.
- **Dados do painel:** logs e histórico das execuções ficam em `backend/crawler/.painel/`, fora do Git.

## Testes

```bash
python -m pytest backend/crawler/tests -q
```

Usam respostas locais com `httpx.MockTransport`, sem consultar a rede: validam esquema, códigos, duplicação, rastreabilidade, Markdown, preservação de versões e falhas de gravação.

## Fontes e próximos passos

| Ordem | Fonte | Entrega | Situação |
|---|---|---|---|
| 1 | [Subclasses CNAE — IBGE](https://servicodados.ibge.gov.br/api/v2/cnae/subclasses) | Markdown estruturado e JSON original | Implementada |
| 2 | LC 123/2006 e Resolução CGSN 140/2018 | Markdown por dispositivo, originais e revisão de vigência pendente | Implementada; anexos extraídos com revisão pendente |
| 3 | Manuais do Simples e perguntas frequentes MEI | Cinco PDFs oficiais em Markdown e originais | Implementada; revisão pendente |
| 4 | Especificações NF-e/NFS-e | Documentação técnica e catálogo de campos | Implementada; recorte inicial com revisão pendente |
| 5 | Dados públicos de CNPJ | Leiaute, auxiliares e amostra de 100 empresas | Implementada; sem junções cadastrais |
| 6 | Agenda tributária e orientações de obrigações | Agenda mensal e serviços declaratórios em Markdown | Implementada; aplicabilidade não avaliada |
| 7 | LGPD — Lei 13.709/2018 | Texto atualizado oficial em Markdown por artigo | Implementada; revisão pendente |
| 8 | Contexto econômico — SGS/BCB | Meta Selic e IPCA em Markdown e JSON | Implementada; janela inicial de 2025 a 03/11/2026 |
| 9 | Normas contábeis simplificadas — CFC | ITG 1000 e NBC TG 1000 (R1), 1001 e 1002 | Implementada; revisão pendente |
| 10 | Reforma tributária | EC 132, LC 214 e cronograma de documentos fiscais | Implementada; recorte inicial com revisão pendente |
| 11 | Código Tributário Nacional | Lei 5.172/1966 atualizada, em Markdown por artigo | Implementada; revisão pendente |
| 12 | ISS — LC 116/2003 | Texto atualizado e lista de serviços anexa | Implementada; sem enquadramento municipal automático |

As datas indicam coleta, não vigência. CNAE sozinho não determina elegibilidade MEI, anexo ou tributação. As próximas fontes precisam de conectores e validações específicos. Integrações autenticadas de notas fiscais descritas no guia de APIs ficam em etapa própria.

## Referências do projeto

- [Base tributária e arquitetura](../../base_tributaria_ia_fontes_e_arquitetura.md)
- [Exploração de dados](../../docs/exploracao-dados.md)
- [Guia de APIs fiscais](../../docs/guia_de_apis_fiscais_e_documenta_o.md)
- [Arquitetura do crawler](../../docs/crawler-arquitetura.md)

## Coletar legislação (LC 123 e CGSN 140)

Com as dependências instaladas, a partir da raiz:

```bash
python -m backend.crawler.legislacao
```

O padrão coleta as duas fontes. Para selecionar uma:

```bash
python -m backend.crawler.legislacao --source lc123
python -m backend.crawler.legislacao --source cgsn140
python -m backend.crawler.legislacao --source lc123 --input caminho/texto-oficial.html
```

`--input` reprocessa um arquivo oficial local sem rede; exige uma fonte específica e passa pelas mesmas validações. `--output caminho` permite outro destino.

```text
data/legislacao/
├── lc123/<sha256>/
│   ├── original.html
│   └── legislacao.md
└── cgsn140/<sha256>/
    ├── original.json
    └── legislacao.md
```

- **LC 123/2006:** texto atualizado da [Câmara dos Deputados](https://www2.camara.leg.br/legin/fed/leicom/2006/leicomplementar-123-14-dezembro-2006-548099-normaatualizada-pl.html), alternativa oficial ao Planalto, que bloqueou a consulta web e expirou por HTTP na implementação. Cabeçalhos por artigo, texto dos parágrafos, anexos e tabelas HTML são preservados. Marcações tachadas permanecem como `~~texto~~`.
- **CGSN 140/2018:** [consulta pública da Receita](https://normasinternet2.receita.fazenda.gov.br/#/consulta/externa/92278/visao/multivigente), via endpoint JSON público utilizado pelo portal. Cada segmento recebe identificador e versão próprios. Textos marcados como tachados, agendados ou omitidos na fonte são sinalizados e preservados. O JSON original mantém histórico, anotações e outros metadados que não são todos exibidos no Markdown.
- **Anexos externos da resolução:** o coletor de legislação lista nomes e links. O comando separado `python -m backend.crawler.anexos` baixa os PDFs e extrai texto e tabelas (ver seção abaixo). A revisão dos valores e da vigência continua pendente; o Markdown não é uma base de regras pronta.

São mantidos URL de obtenção, URL de consulta, visão coletada, instante UTC e SHA-256. `vigencia: nao_verificada` e `revisao_humana: pendente` impedem interpretar a coleta como validação jurídica. Normas e redações históricas podem coexistir no mesmo documento.

Resposta sem identidade esperada ou sem artigos é rejeitada. Falha em uma fonte não impede tentar a outra; o processo retorna código 1 se alguma coleta falhar. Versões anteriores são preservadas e respostas idênticas reutilizam seus arquivos. Os arquivos locais continuam fora do Git, conforme `data/` no `.gitignore`.

Na primeira coleta de 03/11/2026, a LC 123 produziu 140 cabeçalhos de artigo e o original continha 10 tabelas HTML. A CGSN 140 forneceu 2.034 segmentos, incluindo a ementa, e 24 referências a anexos externos. Esses números descrevem a amostra coletada e não são garantias para versões futuras.

## Extrair os anexos da CGSN 140

Após a coleta da resolução:

```bash
python -m pip install -r backend/crawler/requirements.txt
python -m backend.crawler.anexos
```

O comando usa a coleta local quando existe exatamente um `original.json` da CGSN 140. Se houver múltiplas versões, selecione explicitamente:

```bash
python -m backend.crawler.anexos --input backend/crawler/data/legislacao/cgsn140/<hash>/original.json
```

`--output caminho` altera o diretório de destino. Cada execução consulta os endpoints públicos dos anexos; respostas idênticas reutilizam os arquivos previamente publicados. Falha de um download não impede os outros; o índice e o manifesto registram o resultado individual. O comando retorna código 1 se houver falha ou páginas com OCR pendente.

```text
data/anexos-cgsn140/<hash-do-json-fonte>/
├── fonte.json
├── indice.md
├── manifesto.json
└── <id-do-arquivo>/<hash-do-pdf>/
    ├── original.pdf
    ├── anexo.md
    └── metadados.json
```

`indice.md` reúne os links para todos os anexos e versões. `anexo.md` contém o texto por página e as tabelas detectadas. Os metadados registram URL, hash do PDF e da coleta-fonte, segmento/versão, indicadores históricos, instante UTC, número de páginas/tabelas e versão do extrator. O manifesto registra o resultado da execução; os diretórios dos PDFs preservam as versões anteriores.

A primeira extração, em 03/11/2026, baixou os 24 PDFs (versões dos anexos I a XII), totalizando 242 páginas e 283 blocos tabulares detectados. Doze referências estavam marcadas como tachadas na fonte. Todos os arquivos tiveram texto extraível, sem páginas vazias de texto. Os hashes e as contagens foram conferidos, e amostras dos anexos I, XI e XII foram renderizadas para comparação visual.

As tabelas usam `Coluna 1`, `Coluna 2` etc. para não inventar cabeçalhos em células mescladas. Células vazias não herdam valores automaticamente; tabelas podem estar fragmentadas por página ou por bloco. O texto integral extraído da página fica junto às tabelas para conferência. A extração não consolida as tabelas em regras fiscais nem valida todos os valores; revisão humana e de vigência continuam pendentes.

Páginas sem texto são marcadas `OCR PENDENTE` e o PDF é preservado. Não há OCR automático nesta etapa. Respostas HTML e PDFs inválidos são rejeitados. Os dados continuam locais e ignorados pelo Git.

## Coletar manuais e perguntas e respostas

A partir da raiz, após instalar `backend/crawler/requirements.txt`:

```bash
python -m backend.crawler.manuais
```

O comando coleta o conjunto inicial de cinco PDFs vinculados pelo catálogo oficial do Simples Nacional: manuais de PGDAS-D/DEFIS, PGMEI e DASN-SIMEI; perguntas e respostas do Simples Nacional e do MEI. O PDF de perguntas MEI é a fonte oficial inicial selecionada para essa frente; as categorias HTML do Portal do Empreendedor ainda não são percorridas.

Para selecionar um documento ou outro destino:

```bash
python -m backend.crawler.manuais --source perguntas-mei
python -m backend.crawler.manuais --source pgdas-defis --output ./dados/manuais
```

Fontes disponíveis: `pgdas-defis`, `pgmei`, `dasn-simei`, `perguntas-simples`, `perguntas-mei` e `all` (padrão). O catálogo é explícito no módulo; mudanças de URLs no portal exigem revisão e atualização do catálogo.

```text
data/manuais/
├── indice.md
├── manifesto.json
└── <source-id>/<sha256>/
    ├── original.pdf
    ├── documento.md
    └── metadados.json
```

São preservados o PDF original, URL de obtenção e do catálogo oficial, título, tipo, publicador, hash, instante UTC, contagens e versão do extrator. O conteúdo inicial do PDF é conferido contra termos que identificam a fonte esperada. Respostas HTML, PDFs inválidos e documentos com identidade divergente não são publicados como extrações válidas.

Estes materiais são **orientação oficial, camada B**, e complementam as normas da camada A. A data da coleta e o nome do PDF não provam sua atualização. Datas e versões declaradas pelo publicador permanecem no texto e no PDF, sem inferência automática de vigência. A extração ainda exige revisão antes do uso como fundamentação fiscal.

O Markdown preserva texto e tabelas por página. Imagens e capturas de tela permanecem no original e não são transcritas automaticamente. Os blocos tabulares podem corresponder a telas, fragmentos ou células mescladas; a contagem não representa tabelas fiscais prontas. Páginas sem texto geram estado `ocr_pendente`, sem OCR automático.

Falha individual não impede as demais fontes. O processo retorna código 1 se houver falha ou OCR pendente. Repetir bytes idênticos reutiliza a versão, preservando a data inicial. Novo conteúdo cria outro diretório. Índice e manifesto representam a última execução, inclusive se apenas uma fonte for selecionada; as versões anteriores ficam no disco.

Na coleta inicial de 03/11/2026: cinco PDFs, 355 páginas e 143 blocos tabulares detectados; nenhuma página sem texto extraível. Hashes e reexecução sem duplicação foram conferidos. A revisão visual foi amostral, sem auditoria fiscal de todos os valores.

## Coletar documentação técnica de NF-e/NFC-e e NFS-e

```bash
python -m pip install -r backend/crawler/requirements.txt
python -m backend.crawler.documentos_fiscais
```

O conjunto inicial tem quatro fontes verificadas nos portais oficiais:

- `nfe-moc`: MOC 7.00, Anexo I, leiaute e regras de validação NF-e/NFC-e, obtido na SVRS. O PDF declara novembro de 2020; notas técnicas posteriores precisam de revisão separada.
- `nfe-xsd`: pacote `PL_010c_NT2022_002v1.30.zip`, referenciado pelo portal SVRS; cinco XSDs.
- `nfse-manual`: manual de contribuintes da API do Emissor Público Nacional, v1.2, outubro/2025.
- `nfse-xsd`: pacote `NFSe-ESQUEMAS_XSD-v1.01-20260209`, referenciado na página de produção da NFS-e. Contém vinte XSDs, preservando os diretórios internos 1.00 e 1.01.

Fontes: [SVRS](https://dfe-portal.svrs.rs.gov.br/Nfe/Documentos) e [documentação atual NFS-e](https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual). O Portal Nacional da NF-e apresentou redirecionamento em loop na consulta web; a SVRS foi a alternativa oficial usada. Não presumir que este recorte contenha todas as notas técnicas ou que o MOC e os pacotes tenham vigência compatível entre si.

É possível selecionar uma fonte e alterar o destino:

```bash
python -m backend.crawler.documentos_fiscais --source nfse-xsd
python -m backend.crawler.documentos_fiscais --source nfe-moc --output ./dados/documentos-fiscais
```

```text
data/documentos-fiscais/
├── indice.md
├── manifesto.json
└── <source-id>/<sha256>/
    ├── original.pdf ou original.zip
    ├── documento.md ou esquemas.md
    ├── metadados.json
    └── catalogo.json          # apenas pacotes XSD
```

PDFs reutilizam o extrator dos manuais: texto e blocos tabulares por página, sem transcrever imagens automaticamente. As especificações técnicas oficiais são identificadas como camada A. Hash, instante UTC, fonte e revisão pendente acompanham os arquivos. Versões anteriores são preservadas.

Os pacotes XSD geram um inventário por caminho de arquivo, incluindo namespace, hash individual, declarações, nomes, tipos, referências, atributos, documentação, ocorrências e facetas (enumerações, padrões e limites declarados). O Markdown mostra os atributos principais; `catalogo.json` mantém todos os atributos de cada declaração inventariada. Os caminhos `xs:schema/...` apontam à árvore do schema, e não a campos de uma nota XML concreta.

Ocorrências ausentes não recebem valores inferidos; grupos, escolhas, herança e referências não são expandidos. Uma declaração `minOccurs` isolada não determina a obrigatoriedade final de um campo. Schemas de versões diferentes ficam separados, sem consolidação automática.

Includes/imports são listados com indicação de presença no pacote. Dependências ausentes geram `dependencias_pendentes`, sem download externo automático. Declarações DTD são omitidas apenas na leitura, sem expansão de entidades, sem atributos padrão da DTD e sem acesso externo. O catálogo indica `dtd_ignorada` quando isso ocorre; os bytes originais ficam no ZIP. Referências a entidades não resolvidas são rejeitadas. Os nomes das entradas e os limites de tamanho são verificados. O ZIP original é preservado e nenhum arquivo interno é extraído no sistema de arquivos.

Esta etapa não compila XSDs, não valida notas, não emite documentos nem integra serviços autenticados. Planilhas de leiaute da NFS-e, WSDL e a coleta integral das notas técnicas ainda não estão incluídos. O índice e o manifesto refletem a última execução, incluindo falhas; o comando retorna código 1 quando alguma fonte tem erro, OCR pendente ou dependências ausentes.

Na coleta inicial de 03/11/2026, as quatro fontes foram obtidas: dois PDFs (159 páginas, 260 blocos tabulares detectados) e dois pacotes com 25 XSDs (6.548 declarações, incluindo 1.957 declarações de elementos). As dependências referenciadas foram encontradas nos pacotes, sem download externo. Os hashes, as contagens e o reprocessamento dos catálogos foram conferidos. Isso não equivale a compilar os schemas ou validar compatibilidade entre versões.

## Coletar dados abertos CNPJ — recorte inicial

```bash
python -m backend.crawler.cnpj
```

O comando descobre a última pasta mensal disponível no compartilhamento público oficial da Receita (WebDAV somente de leitura), coleta o leiaute PDF, seis tabelas auxiliares e uma amostra de Empresas1.zip. Na execução inicial, a competência mais recente era **2026-10**.

```bash
python -m backend.crawler.cnpj --competencia 2026-10 --limit 100
python -m backend.crawler.cnpj --competencia 2026-10 --empresas-input caminho/Empresas1.zip
```

`--output caminho` altera o destino. O limite de amostra vai de 1 a 10.000, com padrão 100. O ZIP Empresas1 é baixado inteiro (77.901.368 bytes na primeira coleta), limitado a 120 MiB; a leitura do CSV para quando encontra a quantidade solicitada de empresas de porte declarado `01` ou `03`. Outros lotes e arquivos grandes não são baixados automaticamente. O limite de descompactação desse lote é 500 MiB. As tabelas auxiliares são lidas integralmente com limite menor.

`--empresas-input` exige `--competencia`; quem fornece o arquivo local deve garantir que corresponde a Empresas1 da competência declarada. A identidade temporal do arquivo local não é comprovada apenas pelo nome. A origem esperada e o hash do conteúdo ficam registrados nos metadados.

```text
data/cnpj/<competencia>/
├── indice.md
├── manifesto.json
└── <fonte>/<hash-e-parametros>/
    ├── original.zip           # original.pdf para o leiaute
    ├── dados.md               # documento.md para o leiaute
    ├── registros.json         # tabelas/amostra
    └── metadados.json
```

A primeira coleta produziu:

| Fonte | Conteúdo coletado |
|---|---:|
| Empresas1 — amostra de porte 01/03 | 100 empresas, após ler 315 linhas |
| CNAEs da Receita | 1.359 códigos |
| Naturezas jurídicas | 92 códigos |
| Qualificações | 68 códigos |
| Municípios da Receita | 5.572 códigos |
| Países | 255 códigos |
| Motivos de situação cadastral | 63 códigos |
| Leiaute oficial CNPJ | 6 páginas |

Fontes: [compartilhamento oficial](https://arquivos.receitafederal.gov.br/index.php/s/YggdBLfdninEJX9) e [leiaute](https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf). O antigo endereço de diretório `/dados/cnpj/dados_abertos_cnpj/` retornou 404 nesta inspeção; a coleta usa o compartilhamento atual.

A amostra contém as **primeiras correspondências na ordem de um único lote**, sem filtro por UF e sem representatividade estatística. O campo `cnpj_basico` tem oito caracteres; não é um CNPJ completo de estabelecimento. O parser aceita letras maiúsculas e números e preserva zeros à esquerda, sem validar dígitos verificadores ou inferir situação fiscal. As sete colunas de Empresas são preservadas, com códigos textuais e capital social declarado sem conversão numérica.

Empresas não informa CNAEs, município/UF, situação cadastral nem opção pelo MEI ou Simples. Esses dados dependem de outros arquivos e junções ainda não implementadas. Porte `01`/`03` é a classificação declarada na fonte e não comprova opção tributária. Sócios, CPF, contatos e arquivos Estabelecimentos/Simples não são coletados nesta etapa. O ZIP integral do lote Empresas1 fica preservado, embora apenas o trecho necessário ao recorte tenha suas linhas validadas.

O CSV é lido em latin-1, com `;`, aspas e sete campos de Empresas ou dois campos nas auxiliares. Códigos duplicados e leiautes incompatíveis são rejeitados. Códigos de municípios da Receita não equivalem automaticamente aos códigos IBGE. A tabela CNAE da Receita e a do IBGE são versões/fontes distintas; a reconciliação ainda não foi feita.

Índice e manifesto representam a última execução. Conteúdo idêntico e o mesmo limite reutilizam a versão; mudança no limite gera outro recorte. Mudança de conteúdo preserva os anteriores. Erros por fonte são registrados sem impedir as demais. Uma falha transitória na remoção dos temporários no Windows não invalida os dados já publicados. Os arquivos continuam locais e fora do Git.

## Coletar agenda tributária e orientações de obrigações

```bash
python -m backend.crawler.obrigacoes --periodo 2026-11
```

O padrão desta etapa é `2026-11`; ele é um recorte fixo, não muda automaticamente com a data do computador. Outros meses publicados podem ser selecionados com `--periodo AAAA-MM`. `--output caminho` permite escolher o destino.

A coleta começa no índice anual da Receita, localiza o mês publicado e acompanha somente links para dias, vencimentos diários e outros vencimentos dentro daquele mesmo mês. Preserva a grafia real das URLs. Também coleta as páginas públicas de orientação dos serviços PGDAS-D, DEFIS e DASN-SIMEI, sem acessar sistemas autenticados.

```text
data/obrigacoes/<periodo>/
├── indice.md
├── manifesto.json
├── referencias.json
└── <source-id>/<sha256>/
    ├── original.html
    ├── pagina.md
    ├── tabelas.json
    └── metadados.json
```

Na coleta inicial de novembro/2026 foram obtidas **16 páginas oficiais**: índice anual, página mensal, nove dias específicos, página de vencimentos diários, página de outros vencimentos e três orientações declaratórias. Foram preservadas 17 tabelas, 630 linhas e 2.215 células, incluindo a tabela de calendário da página mensal. As contagens não representam número de obrigações distintas.

As células das tabelas são mantidas com texto, posição, tipo de tag, `rowspan` e `colspan`. O Markdown mostra um inventário literal das células; não distribui valores entre linhas/colunas por inferência. Isso evita associar incorretamente tributo, documento de arrecadação, período e fundamento nas linhas mescladas da agenda.

`referencias.json` e o índice destacam dez linhas da amostra que contêm termos Simples Nacional, SIMEI, PGDAS, DASN ou DEFIS. Cada referência aponta à página, tabela e linha original, com `aplicabilidade: nao_avaliada`. A seleção é por palavras-chave, não é exaustiva, pode exigir contexto das linhas vizinhas e não cria obrigações ou alertas para uma empresa.

A data em `data_publicada_no_titulo` é a data explicitada no título de uma página diária. Ela não é inferida para páginas de vencimentos diários ou sem dia específico. O período de referência do tributo permanece como texto publicado. Não há cálculo de recorrência, vencimento ou ajuste por feriado.

As agendas são catalogadas como camada A; orientações de serviço como camada B. Os serviços gerais não são regras específicas do mês selecionado. A página de DEFIS efetivamente usada é `declarar-apuracoes-e-informacoes-anuais-do-simples-nacional`; o endereço anteriormente tentado retornou 404. O conteúdo editorial é preservado sem corrigir silenciosamente eventuais inconsistências do publicador.

O parser seleciona o conteúdo principal Gov.br ou o bloco específico do serviço, excluindo menus externos e scripts. URLs relativas viram links absolutos. A página mensal contém um link para declarações de 2024; ele permanece como link, sem ser percorrido. Links externos, anexos XLSX e o ato normativo relacionado não são coletados automaticamente nesta etapa. A extração não equivale a uma validação jurídica completa da agenda.

Falhas individuais entram no manifesto sem impedir os outros documentos. Índice e manifesto refletem a última execução. HTML idêntico reutiliza a versão; conteúdo alterado cria outra, preservando os anteriores. Os dados continuam locais e ignorados pelo Git.

## Coletar a LGPD (fonte P0)

```bash
python -m backend.crawler.legislacao --source lgpd
```

A fonte é o [texto atualizado oficial da Lei 13.709/2018 na Câmara dos Deputados](https://www2.camara.leg.br/legin/fed/lei/2018/lei-13709-14-agosto-2018-787077-normaatualizada-pl.html). É reutilizado o parser de textos da Câmara já empregado na LC 123, com identificação específica da LGPD. A opção `--source all` coleta todas as fontes do catálogo legislativo: LC 123, LGPD, CGSN 140, EC 132, LC 214, CTN e LC 116.

```text
data/legislacao/lgpd/<sha256>/
├── original.html
└── legislacao.md
```

O Markdown contém cabeçalhos por artigo, inclusive números com letras, parágrafos, incisos e anotações de alterações que constem do HTML. Texto tachado é preservado como tal. Metadados de origem, visão, camada A, instante UTC e SHA-256 acompanham a extração. O original é mantido sem alterações. `--input caminho/lgpd.html --source lgpd` permite reprocessar um arquivo local com as mesmas validações.

Na coleta inicial de 03/11/2026 foram reconhecidos 81 cabeçalhos de artigo, do art. 1º ao art. 65, incluindo os dispositivos com letras e as redações presentes no texto coletado. Hash, correspondência dos cabeçalhos e reexecução sem duplicação foram conferidos. A conversão da LC 123 anterior permaneceu equivalente após o compartilhamento do parser.

Esta etapa preenche a coleta do texto da LGPD prevista no levantamento. Não produz parecer jurídico, não determina base legal de tratamento e não comprova conformidade do projeto. Atos e orientações da ANPD e a avaliação da aplicabilidade ainda precisam de trabalho específico. Revisão humana e de vigência permanecem pendentes.

## Coletar contexto econômico — Selic e IPCA

```bash
python -m backend.crawler.economia
```

O recorte inicial consulta **01/01/2025 a 03/11/2026**. Esses limites são fixos desta etapa; não se atualizam automaticamente com o relógio do computador. É possível mudar o intervalo, selecionar uma série ou alterar o destino:

```bash
python -m backend.crawler.economia --inicio 2025-01-01 --fim 2026-11-03
python -m backend.crawler.economia --source ipca
python -m backend.crawler.economia --source selic-meta --output ./dados/economia
```

| Fonte | Código SGS | Unidade | Periodicidade | Produtor |
|---|---|---|---|---|
| Meta Selic definida pelo Copom | 432 | Percentual ao ano | Diária | Banco Central / Copom |
| IPCA | 433 | Variação percentual mensal | Mensal | IBGE, disseminado pelo BCB |

Fontes de referência: [metadados da meta Selic no BCB](https://dadosabertos.bcb.gov.br/dataset/432-taxa-de-juros---meta-selic-definida-pelo-copom) e [consulta SGS 433](https://www3.bcb.gov.br/sgspub/consultarvalores/consultarValoresSeries.do?method=consultarSeries&series=433). Dados obtidos pela API oficial SGS do Banco Central, com URL e parâmetros de datas registrados nos metadados.

```text
data/economia/
├── indice.md
├── manifesto.json
└── <serie>/<inicio>_<fim>/<sha256>/
    ├── original.json
    ├── serie.md
    ├── registros.json
    └── metadados.json
```

A primeira coleta retornou 672 observações diárias da meta Selic, de 01/01/2025 a 03/11/2026, e 21 observações mensais do IPCA, de janeiro/2025 a setembro/2026, somando 693 registros. O fim solicitado não garante que uma série já tenha dados publicados até essa data. A data retornada na série mensal é uma referência, não a data em que o índice foi divulgado.

O JSON original é preservado. Datas normalizadas ficam em ISO com a data original ao lado no JSON estruturado. Valores passam por validação com `Decimal` e permanecem como strings originais, sem arredondamento ou conversão para float. Valores negativos são aceitos, necessários para séries como inflação mensal.

São rejeitados JSON inválido, lista vazia, data inválida, observação fora da janela, data duplicada, mais de uma referência no mesmo mês do IPCA e valor não decimal/finito. As observações são ordenadas por data. O coletor limita a janela a 3.650 dias, abaixo do limite de dez anos indicado pelo BCB para consultas diárias. Não preenche lacunas, acumula inflação, transforma taxas ou estima dados ausentes.

A meta Selic de periodicidade diária é divulgada em percentual ao ano; ela não é a Selic efetiva diária. O IPCA desta série é variação mensal, e não o acumulado em doze meses. As séries não devem ser comparadas como se tivessem a mesma periodicidade ou unidade.

O hash identifica os bytes retornados; intervalo e série integram o caminho da versão. Conteúdo idêntico na mesma consulta reutiliza os arquivos. Mudança de janela ou conteúdo preserva os anteriores. Índice e manifesto refletem a última execução. Falha em uma série não impede a outra e o comando retorna código 1 quando há erro.

Esta etapa cobre as duas séries SGS priorizadas. PIB, outras tabelas SIDRA, expectativas Focus e indicadores de crédito ainda precisam de coletores específicos. Os arquivos continuam locais e ignorados pelo Git.

## Coletar normas contábeis simplificadas do CFC

```bash
python -m backend.crawler.contabilidade
```

O catálogo explícito desta etapa contém os PDFs oficiais de:

- ITG 1000, de 15/12/2022: normas aplicáveis e modelos de plano de contas e demonstrações contábeis para microentidade e pequena empresa.
- NBC TG 1000 (R1): Contabilidade para Pequenas e Médias Empresas.
- NBC TG 1001: Contabilidade para Pequenas Empresas.
- NBC TG 1002: Contabilidade para Microentidades.

Fonte de referência: [catálogo de normas simplificadas para PMEs do CFC](https://cfc.org.br/tecnica/normas-brasileiras-de-contabilidade/normas-simplificadas-para-pmes/). Na conferência de 03/11/2026, o catálogo apontava às páginas de detalhes SRE; os PDFs foram obtidos no domínio oficial `www1.cfc.org.br/sisweb/SRE/docs/`, e os títulos e a edição esperada foram conferidos no conteúdo inicial.

```bash
python -m backend.crawler.contabilidade --source itg1000
python -m backend.crawler.contabilidade --source nbctg1002 --output ./dados/contabilidade
```

Fontes disponíveis: `itg1000`, `nbctg1000r1`, `nbctg1001`, `nbctg1002` e `all` (padrão).

```text
data/contabilidade/
├── indice.md
├── manifesto.json
└── <source-id>/<sha256>/
    ├── original.pdf
    ├── documento.md
    └── metadados.json
```

O extrator PDF existente é reutilizado, preservando texto e blocos tabulares por página. Hash, instante UTC, fonte do PDF, catálogo, publicador, tipo e versão do extrator ficam nos metadados. A identidade da ITG 1000 exige a referência de dezembro de 2022, evitando aceitar silenciosamente a antiga edição de mesmo número.

As normas são identificadas como **camada C**, que corresponde à categoria referência técnica/profissional no levantamento do projeto. Essa classificação documental não é uma avaliação da força normativa do CFC. Datas, referências e notas de alterações permanecem no texto do PDF; a coleta não decide qual norma se aplica a uma empresa nem resolve a vigência de cada dispositivo.

Imagens permanecem no PDF e não são transcritas automaticamente. Tabelas extraídas podem ter células mescladas ou fragmentação por página; não se tornam planos de contas ou regras de escrituração automaticamente. Páginas sem texto ficam como OCR pendente. Revisão humana e de aplicabilidade continuam necessárias.

Conteúdo idêntico reutiliza a versão; alterações criam outro diretório e preservam os anteriores. Erros por documento não impedem as outras fontes e aparecem no manifesto. Índice e manifesto refletem a última execução; o comando retorna código 1 se houver falha ou OCR pendente.

Este recorte contém as quatro normas listadas. CTG 1000, versões próprias do CPC e artigos contábeis do Código Civil ainda exigem coleta específica. Os arquivos permanecem locais e fora do Git.

Na coleta inicial de 03/11/2026 foram obtidos os quatro PDFs: ITG 1000 com 43 páginas, NBC TG 1000 (R1) com 229, NBC TG 1001 com 44 e NBC TG 1002 com 17, totalizando 333 páginas e 59 blocos tabulares detectados. Nenhuma página ficou sem texto extraível. Hashes, contagens e reexecuções foram conferidos; a inspeção visual foi amostral.

## Coletar a reforma tributária — normas e cronograma

```bash
python -m backend.crawler.reforma
```

O conjunto inicial contém três fontes oficiais:

| Fonte | Visão coletada | Camada |
|---|---|---|
| EC 132/2023, Câmara dos Deputados | Publicação original | A |
| LC 214/2025, Câmara dos Deputados | Texto atualizado apresentado pelo publicador | A |
| Cronograma dos documentos fiscais eletrônicos, Receita Federal | Página de orientação e tabelas literais | B |

```bash
python -m backend.crawler.reforma --source ec132
python -m backend.crawler.reforma --source lc214
python -m backend.crawler.reforma --source cronograma --output ./dados/reforma
```

As normas também podem ser coletadas diretamente com `python -m backend.crawler.legislacao --source ec132` ou `--source lc214`. Nesse caso, o destino padrão é a pasta `data/legislacao/`; o comando `reforma` concentra seu conjunto em `data/reforma/`.

```text
data/reforma/
├── indice.md
├── manifesto.json
└── <source-id>/<sha256>/
    ├── original.html
    ├── legislacao.md ou pagina.md
    ├── metadados.json
    └── tabelas.json             # cronograma
```

A EC foi obtida na [publicação original da Câmara](https://www2.camara.leg.br/legin/fed/emecon/2023/emendaconstitucional-132-20-dezembro-2023-795084-publicacaooriginal-170513-pl.html), e a LC 214 no [texto atualizado da Câmara](https://www2.camara.leg.br/legin/fed/leicom/2025/leicomplementar-214-16-janeiro-2025-796905-normaatualizada-pl.html). O parser da EC seleciona somente o bloco normativo, excluindo a navegação do portal. A identificação da norma é validada antes da extração.

Textos que alteram outras normas podem incluir artigos citados da Constituição e de outras leis. Cabeçalhos reconhecidos no Markdown não equivalem à contagem dos artigos próprios da EC/LC e não reconstroem uma Constituição consolidada. Aspas, anotações de alterações, efeitos futuros e texto tachado são mantidos conforme a conversão da fonte, com revisão humana pendente.

O [cronograma da Receita](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/acoes-e-programas/reforma-tributaria-do-consumo/orientacoes-da-reforma-tributaria/cronograma) trata dos documentos fiscais eletrônicos. Seus cinco blocos tabulares são preservados como inventário de células, com posição e mesclagens no JSON. O texto distingue início de obrigatoriedade e publicação de leiautes; esses marcos não são convertidos em regras ou datas aplicáveis a uma empresa.

Hash, instante UTC, origem e visão coletada acompanham os documentos. A publicação original da EC não é rotulada como texto atualizado. A coleta da LC não determina a competência de aplicação de cada alteração. Vigência e compatibilidade entre normas e cronograma continuam pendentes de avaliação.

O recorte não percorre automaticamente o ato conjunto relacionado, outras leis complementares, notas técnicas ou links da página. Ele não representa toda a regulamentação da reforma, nem aplica mudanças no motor de cálculo ou no Simples Nacional. Erros por fonte são registrados sem impedir as demais. Índice e manifesto refletem a última execução e versões anteriores permanecem preservadas. Os dados continuam locais e ignorados pelo Git.

Na coleta inicial da reforma, as três fontes foram obtidas sem falhas. Os artigos próprios 1 a 23 da EC 132 foram conferidos na conversão; os 25 cabeçalhos reconhecidos incluem citações a artigos constitucionais. A LC 214 gerou 581 cabeçalhos reconhecidos e o cronograma preservou cinco tabelas, 35 linhas e 105 células. Hashes e conversões foram verificados; a vigência e a interpretação dos dispositivos continuam pendentes.


## Coletar o Código Tributário Nacional

```bash
python -m backend.crawler.legislacao --source ctn
```

Fonte: [texto atualizado da Lei 5.172/1966 na Câmara dos Deputados](https://www2.camara.leg.br/legin/fed/lei/1960-1969/lei-5172-25-outubro-1966-358971-normaatualizada-pl.html). A norma é identificada por número e data antes da conversão, utilizando o parser da Câmara já empregado nas demais leis.

```text
data/legislacao/ctn/<sha256>/
├── original.html
└── legislacao.md
```

O Markdown preserva o conteúdo por artigo, incluindo dispositivos com letras, notas de alterações e texto tachado presente na fonte. Origem, visão coletada, camada A, instante UTC, SHA-256 e revisão pendente acompanham a extração. Na primeira coleta foram reconhecidos 224 cabeçalhos, do art. 1º ao art. 218, incluindo dispositivos com letras e redações constantes do texto. Esse número não é uma contagem de dispositivos juridicamente vigentes.

Hash, correspondência dos cabeçalhos com os parágrafos do HTML e reexecução sem duplicação foram conferidos. O comando também aceita `--input caminho/ctn.html` para reprocessamento local e `--output caminho` para outro destino. A seleção `--source all` passa a incluir o CTN no catálogo legislativo.

Esta etapa coleta a fundamentação geral de direito tributário prevista no levantamento; não interpreta hipóteses de incidência, prescrição, decadência ou exigibilidade por empresa. A revisão de vigência e aplicação por competência continua pendente. Os dados permanecem locais e fora do Git.


## Coletar a LC 116/2003 — ISS e lista de serviços

```bash
python -m backend.crawler.legislacao --source lc116
```

Fonte: [texto atualizado oficial da LC 116/2003 na Câmara](https://www2.camara.leg.br/legin/fed/leicom/2003/leicomplementar-116-31-julho-2003-492028-normaatualizada-pl.html). O coletor valida a identidade da lei e a presença da lista de serviços antes de publicar a versão.

```text
data/legislacao/lc116/<sha256>/
├── original.html
└── legislacao.md
```

Na primeira coleta foram preservados 12 cabeçalhos de artigo, 40 grupos e 205 subitens publicados na lista anexa. Os 205 códigos de subitem são distintos nessa amostra e foram conferidos no Markdown. As contagens descrevem o texto coletado e não certificam vigência de cada item.

O texto, códigos e anotações de alterações permanecem conforme publicados. Não há deduplicação jurídica ou cruzamento automático entre CNAE e subitem. O HTML original é preservado, acompanhado no Markdown por origem, camada A, visão, instante UTC e hash SHA-256. O hash e a reexecução sem duplicação foram verificados.

`--input caminho/lc116.html` permite reprocessar um arquivo local; `--output caminho` altera o destino. A opção `--source all` inclui esta lei no catálogo legislativo.

A lista nacional não determina sozinha município competente, incidência, alíquota ou opção tributária da empresa. Legislação municipal, exceções, decisões aplicáveis e efeitos temporais ainda precisam de coleta e revisão próprias. Nenhuma regra de cálculo foi modificada nesta etapa. Os dados continuam locais e ignorados pelo Git.

## Fechamento das sete frentes de coleta — novembro de 2026

As sete entregas mantêm os resultados em Markdown, com originais e metadados locais em `data/` (ignorada pelo Git). Não exigem PostgreSQL.

| Frente | Comando (`python -m backend.crawler.…`) | Recorte |
|---|---|---|
| MEI | `mei` | Páginas oficiais de orientação; limitações de conteúdo dinâmico registradas no índice |
| CNPJ ampliado | `cnpj_ampliado` | 100 empresas de portes 01/03 com estabelecimento ativo, competência 2026-10; cruzamento Empresas, Estabelecimentos e Simples |
| Tabelas fiscais | `tabelas_fiscais` | NCM, CFOP, CEST, CST ICMS e CSOSN, com versões identificadas |
| Complemento contábil | `complemento_contabil` | Código Civil arts. 1179–1195 e CTG 1000 |
| Indicadores | `ibge_indicadores` | PIB 2021–2023 e CEMPRE 2022–2024, Brasil |
| Sebrae | `sebrae` | Sobrevivência e Pulso dos Pequenos Negócios, edições identificadas |
| Catálogo e integridade | `catalogo` | Inventário, hashes, proveniência, duplicações e pendências |

Consulte [o índice consolidado](data/catalogo/indice.md) e [as pendências de revisão](data/catalogo/revisao.md). Execute o catálogo novamente após novas coletas. Indicadores nacionais e amostras não substituem bases completas. Vigência jurídica, aplicabilidade e fidelidade semântica de tabelas extraídas exigem revisão; os hashes verificam integridade dos arquivos.

O CNPJ ampliado usa os primeiros 1.000 estabelecimentos ativos de raízes distintas do lote 1 e seleciona 100 cruzamentos elegíveis no lote Empresas2. Não é amostra estatística nem extensão automática das mesmas empresas da coleta anterior. Ausência no arquivo Simples permanece distinta da opção literal `N`. A extração derivada não inclui contatos, endereços ou QSA; os ZIPs públicos integrais são preservados localmente.

## Notas explicativas CNAE e interpretações administrativas da Receita

Estas frentes ampliam o corpus previsto nas seções 4 e 6 de `base_tributaria_ia_fontes_e_arquitetura.md`.

- `python -m backend.crawler.notas_cnae`: coleta publicação oficial identificada por versão, com notas explicativas da CNAE, PDF original e extração em Markdown. Consulte [o índice de notas CNAE](data/notas-cnae/indice.md) para a cobertura efetivamente extraída e a comparação com os códigos da API. Notas de inclusão/exclusão descrevem atividades; não estabelecem, isoladamente, anexo do Simples ou elegibilidade MEI.
- `python -m backend.crawler.consultas_rfb`: coleta interpretações administrativas da Receita no recorte temático do projeto. Consulte [o índice de consultas](data/consultas-rfb/indice.md) e seu manifesto para filtros de descoberta, páginas percorridas, documentos, falhas e distinção entre ementa e texto integral. Não corresponde, por definição, a todo o acervo de todos os tributos.
- `python -m backend.crawler.catalogo`: atualiza o inventário e a auditoria de integridade, incluindo as duas novas pastas e preservando as frentes anteriores.

Documentos de consulta/divergência são identificados como interpretações administrativas, com origem e revisão de aplicabilidade pendente. Nem a classificação temática nem a data de coleta certificam vigência ou alcance universal. Todos os originais e resultados permanecem em `data/`, fora do Git; os módulos, testes e instruções são versionáveis.

A coleta CNAE de 04/11/2026 preservou a publicação de 2020 da versão 2.3: 608 páginas físicas, 510 blocos de tabelas detectados e 1.332 títulos de subclasses na Parte 3 (páginas físicas 101–528). Os códigos coincidem integralmente com os 1.332 códigos da resposta da API desta execução. Títulos com continuação de linha são preservados no índice. Oito páginas brancas e uma contracapa gráfica sem texto extraível estão identificadas; não há lacuna textual no intervalo das notas. A reprodução reaproveita o PDF já extraído quando o hash coincide.

A coleta da Receita usa buscas textuais separadas para `"Simples Nacional"`, `"microempreendedor individual" OR MEI OR SIMEI`, `"fator R"`, `fator` e `segregação AND receita`, restringindo aos tipos oficiais SC e SD. A busca ampla `fator` também retorna assuntos diferentes de Fator R e exige seleção temática posterior. O snapshot de descoberta tem 1.781 IDs únicos em 2.025 ocorrências, com todas as páginas percorridas; o manifesto informa quantos atos/anexos foram efetivamente coletados. Esses números descrevem os filtros utilizados, sem certificar cobertura semântica universal.

Para retomar downloads e extrações, reexecute o comando no mesmo destino: o cache é validado por hash. Para uma nova fotografia da fonte, use `--output` apontando para um destino novo datado e preserve o anterior. A extração de texto dos PDFs de consultas usa PDFium, com versão registrada nos metadados; extrações anteriores em cache podem registrar pdfplumber. O PDF original prevalece para revisão de tabelas e disposição visual.

Resultado da coleta temática da Receita em 04/11/2026: 1.781 atos (1.743 SC e 38 SD), 1.259 PDFs em 1.258 atos e 13.053 páginas PDF. As 23 páginas de pesquisa cobrem integralmente os resultados dos cinco filtros declarados, com 244 ocorrências duplicadas entre temas. Foram recebidos 1.759 atos na visão multivigente e 22 na visão exclusiva oferecida pelo endpoint oficial de visão original; a visão efetiva consta nos metadados. Não houve falha remanescente de acesso nem de anexos. A auditoria conferiu 3.088 recibos de requisições e os hashes dos 1.781 arquivos Markdown. Páginas sem texto extraível permanecem identificadas para conferência, sem presumir completude do texto integral de todos os atos.

A única página sem texto na coleta de consultas (ato 67229, anexo 37307, página 15) foi conferida visualmente e está em branco. A evidência e os hashes do PDF e da imagem de conferência estão registrados em revisao-paginas.json; não restou OCR pendente neste recorte.

## Ampliação das etapas 3 a 8 — foco local Brasília/DF

O recorte local foi confirmado pelo usuário como Brasília/Distrito Federal. Não se aplica legislação de São Paulo ao perfil distrital. Os conectores preservam originais e Markdown locais, com revisão humana e vigência pendentes.

| Etapa | Comando a partir da raiz | Índice local e cobertura |
|---|---|---|
| 3 — Obrigações | `python -m backend.crawler.obrigacoes_avancadas` | [DCTFWeb, eSocial e EFD-Reinf](data/obrigacoes-avancadas/indice.md): orientações, manuais, MOS, leiautes e XSD identificados por versão |
| 4 — Normas | `python -m backend.crawler.legislacao_complementar` | [Legislação complementar](data/legislacao-complementar/indice.md): LC 128/147/155/188, LC 87, Decreto 6.022, Lei 12.741 e Ajustes SINIEF 7/2005 e 19/2016 |
| 5 — Distrito Federal | `python -m backend.crawler.distrital_df` | [ISS e NFS-e no DF](data/distrital-df/indice.md): Decretos 25.508/2005 e 43.982/2022, retenções, orientações, FAQ e manuais |
| 6 — Documentação fiscal | `python -m backend.crawler.notas_tecnicas_fiscais` | [Notas técnicas e classificações](data/notas-tecnicas-fiscais/indice.md): NT NF-e/NFS-e, NBS, cTribNac, indicadores e correlações publicadas |
| 7 — Regularização | `python -m backend.crawler.regularizacao_fiscal` | [Receita e PGFN](data/regularizacao-fiscal/indice.md): parcelamento MEI/Simples, dívida ativa, situação fiscal e certidões; apenas orientações públicas |
| 8 — Indicadores | `python -m backend.crawler.indicadores_empresariais` | [Indicadores empresariais](data/indicadores-empresariais/indice.md): publicações Mapa de Empresas, JUCIS-DF e cartões do Observatório Sebrae para Brasil e UFs |

Cada manifesto enumera fontes selecionadas, versões, cobertura efetiva e erros. Os comandos não consultam contas fiscais nem emitem notas ou declarações. Reexecuções reaproveitam snapshots válidos; falhas e dependências pendentes não são apresentadas como conteúdo completo. `python -m backend.crawler.catalogo` atualiza a auditoria de hashes e pendências, incluindo estas seis frentes.

Limites específicos: o pacote XSD Reinf publicado não inclui a dependência `xmldsig-core-schema.xsd`; o inventário registra os imports sem executar validação de eventos. Tabelas/imagens em PDFs dos manuais grandes permanecem no original, sem reconstrução automática. Tabelas XLSX preservam coordenadas, mesclagens, fórmulas e valores em cache, sem recalcular. O manual de integração NFS-e Nota Control é documentação do fornecedor vinculada pela Receita DF, e não texto normativo. Um caractere defeituoso já presente no HTML SINJ foi preservado e anotado.


Resultado das etapas 3 a 8 em 04/11/2026: 18 fontes de obrigações (1.850 páginas e 75 XSD), nove normas complementares, oito fontes distritais (165 páginas), 13 documentos técnicos (186 páginas e 6.964 linhas de tabelas), 13 fontes de regularização e 76 indicadores empresariais (oito do DF). Indicadores incluem dois boletins nacionais de 31 páginas cada e Panorama JUCIS-DF de 39 páginas. O catálogo do Mapa lista 27 publicações; os dois boletins foram obtidos pelo REST público oficial após indisponibilidade da rota HTML.

O acesso direto ao DataSebrae retornou HTTP 403; o Observatório Sebrae público foi coletado como alternativa, sem contornar restrições. A publicação JUCIS-DF exigiu uma exceção de verificação TLS em cliente isolado, registrada nos metadados; nenhuma configuração global foi alterada. Estas limitações e a dependência XSD Reinf pendente permanecem visíveis nos índices. Versões anteriores, respostas de erro e evidências de descoberta são preservadas. Reexecução de indicadores com falha de rede mantém os últimos dados válidos por fonte e registra separadamente a tentativa.

## Prioridades DF e expansão SPED / IRPJ

A execução de 04/11/2026 concluiu primeiro o recorte prioritário e depois os recortes complementar e de expansão. Resultados em Markdown, com originais e metadados:

| Coletor (`python -m backend.crawler.…`) | Resultado e índice |
|---|---|
| `cnpj_df` | [1.000 empresas ativas DF](data/cnpj-df/indice.md), competência 2026-10, portes 01/03; amostra de conveniência, não censo. As 193 ausências no arquivo Simples permanecem nulas. |
| `xmls_exemplo` | [Três exemplos oficiais municipais SP](data/xmls-exemplo/indice.md). Os pacotes nacionais examinados contêm schemas, sem instâncias XML. Não cobre NF-e 55, NFC-e 65, NFS-e nacional ou DF; não houve validação XSD, assinatura ou validade fiscal. |
| `calendario_df` | [Agendas e calendário 2026](data/calendario-df/indice.md): janeiro–novembro publicados; dezembro ausente do índice consultado. Há 66 registros documentais de datas, com sobreposições e versões superadas, não 66 feriados distintos. Pontos facultativos administrativos não deslocam automaticamente prazos fiscais. |
| `sped_complementar` | [ECD, ECF, EFD-Contribuições e EFD-ICMS/IPI](data/sped-complementar/indice.md): quatro manuais, 1.656 páginas e oito fontes de orientação/catálogo. Texto extraído; tabelas e imagens devem ser conferidas nos PDFs. |
| `tributacao_lucro` | [Quatro normas IRPJ/CSLL](data/tributacao-lucro/indice.md): Leis 9.249/1995 e 9.430/1996, IN RFB 1.700/2017 e Decreto 9.580/2018. Visões publicadas preservadas, incluindo versões e marcadores; vigência e aplicabilidade exigem revisão. |

Reexecute `python -m backend.crawler.catalogo` após novas coletas. A conclusão destes recortes não significa cobertura universal das fontes nem elimina as lacunas de exemplos XML nacionais/DF.

## Expansão ampla: oito frentes

A expansão mantém Brasília/DF como foco e resultados em Markdown. Os recortes são delimitados nos manifestos; disponibilidade documental não certifica vigência, obrigação empresarial ou força vinculante de decisões.

| Frentes | Comando a partir da raiz | Cobertura e limites |
|---|---|---|
| 1 e 3 — ICMS e consultas DF | `python -m backend.crawler.icms_consultas_df` | [159 documentos extraídos](data/icms-consultas-df/indice.md), incluindo RICMS e Lei 1.254, normas relacionadas, quatro páginas DODF contendo consultas tributárias e uma contendo jurisprudência do TARF. Descoberta de um salto a partir das normas sementes; duas páginas vazias recusadas. Não é todo o acervo de consultas do DF. |
| 2 e 4 — Reforma e histórico Simples/MEI | `python -m backend.crawler.reforma_historico` | [271 atos e cinco páginas oficiais](data/reforma-historico/indice.md), 542 respostas de visões da API, pesquisas paginadas CGSN/CBS/IBS. Inclui 213 atos CGSN no recorte 2007–2026 e quatro marcos normativos da reforma. Há 63 anexos Word antigos e duas imagens preservados, com conversão/OCR pendentes em seis atos. |
| 5 — CNPJ DF | `python -m backend.crawler.cnpj_df_censo` | [Recorte dos lotes completos](data/cnpj-df-censo/indice.md): dez lotes de estabelecimentos, dez de empresas e Simples; empresas de portes 01/03 com estabelecimento ativo no DF. Uma linha por raiz, não por filial. Resultado 2026-10: 413.539 empresas elegíveis, 469.456 raízes com estabelecimento ativo DF antes do filtro de porte e 195.132.919 linhas brutas percorridas. Há 20.220 ausências no arquivo Simples, preservadas como nulas. Totais e cobertura por lote no manifesto da competência. Downloads grandes são necessários; checkpoints reaproveitam leituras válidas. |
| 6 e 7 — Documentos fiscais e jurisprudência | `python -m backend.crawler.documentos_jurisprudencia` | [37 documentos obtidos](data/documentos-jurisprudencia/indice.md): 29 técnicos, sete consultas CARF e um panorama editorial STJ. São 409 páginas PDF, 91 XSD nos oito pacotes e 1.960 linhas de planilhas. Um pacote preservado tem a dependência `tiposBasico_v1.03.xsd` ausente; 36 documentos estão extraídos e um permanece com dependência pendente. Treze fontes falharam por restrição, timeout ou pacote inválido, conforme manifesto. Editorial e ementas não equivalem a inteiro teor judicial. |
| 8 — Casos oficiais | `python -m backend.crawler.casos_oficiais` | [766 candidatos em 24 arquivos de origem](data/casos-oficiais/indice.md), com trechos literais, linhas e página quando identificada. Enriquecimento do acervo existente, sem contar como documentos oficiais novos ou cálculos certificados. |
| Contagem geral | `python -m backend.crawler.estatisticas` | [Estimativa numérica reproduzível](data/estatisticas/indice.md) e [JSON detalhado](data/estatisticas/totais.json). Atualiza o catálogo, deduplica conteúdos por hash e empresas por raiz. Separa páginas, documentos, versões, schemas, registros e bytes. |

As lacunas de instâncias XML NF-e/NFC-e/NFS-e nacional/DF continuam identificadas. Os pacotes técnicos ampliados são schemas e documentação, sem validação fiscal de notas de terceiros. Originais dos anexos não convertidos estão preservados; a contagem de páginas PDF é física e não comprova extração de texto em todas as páginas. Os arquivos da coleta ficam em `data/`, fora do Git.

Fotografia consolidada após esta expansão: 2.664 snapshots/versões, 4.316 conteúdos originais distintos por hash, 2.791 arquivos Markdown, 18.745 páginas em 1.372 PDFs distintos e 183 conteúdos XSD distintos (inclui pacotes). Os derivados contêm 413.739 raízes empresariais distintas no acervo inteiro, das quais 413.539 no novo recorte completo DF. Volume físico contado: 8.087 GiB em 15.596 arquivos. Medidas não somáveis; índices, versões e trechos derivados estão incluídos nas unidades indicadas. Auditoria: zero divergências técnicas e zero originais sem metadados; 305 testes crawler e um teste API passaram.

## Nove frentes de enriquecimento e documento integral

A rodada de novembro de 2026 usa coleta multithread com limites por serviço e cache validado. Os conectores abaixo preservam originais, primeira data e hashes; nenhuma conta privada ou restrição de acesso é contornada.

| Frentes | Comando | Resultado e limites |
|---|---|---|
| 1 — Anexos pendentes | `python -m backend.crawler.recuperar_anexos` | [Conversão/OCR](data/anexos-recuperados/indice.md) dos anexos Word e imagens de reforma/histórico e retenções. Usa Word local invisível, macros desabilitadas e Windows OCR pt-BR. Originais permanecem intactos; OCR e tabelas exigem revisão. |
| 1 — Recuperação de fonte | `python -m backend.crawler.fontes_recuperadas` | [Tentativas oficiais](data/fontes-recuperadas/indice.md): Informativo STJ 872 recuperado por PDF público alternativo; seis PDFs CARF continuaram indisponíveis. |
| 2 e 3 — Súmulas e mercadorias | `python -m backend.crawler.sumulas_classificacao --workers 3` | [CARF e classificação](data/sumulas-classificacao/indice.md): 79 snapshots atuais, incluindo NESH, Ceclam, compêndios e NCM; 254 títulos de súmulas e 633 identificadores distintos de precedentes, sem presumir vigência ou íntegra. A NCM tem 15.157 nós, dos quais 10.516 são códigos de oito dígitos. |
| 4 — DF ampliado | `python -m backend.crawler.consultas_df_amplas` | [1.462 documentos](data/consultas-df-amplas/indice.md): 987 consultas integrais de 2010–2026 e 475 páginas TARF de ementa/decisão. ICMS e ISS limitados aos primeiros 200 resultados de cada busca; 89 resultados Simples percorridos e deduplicados. Não são votos integrais. |
| 5 a 8 — Retenções, defesa e setores | `python -m backend.crawler.retencoes_defesa_setores --max-pages 3 --max-docs 2000` | [1.798 atos](data/retencoes-defesa-setores/indice.md), obtidos por buscas literais sobre retenções/fora do DAS, penalidades/recursos, restituição/compensação e tecnologia, saúde, construção, alimentação e comércio. Totais da fonte, páginas lidas e truncamento constam no manifesto; pertinência e aplicabilidade não certificadas. |
| 9 — Histórico por competência | `python -m backend.crawler.historico_competencias --workers 3` | [823 documentos](data/historico-competencias/indice.md) de 2018–2025, incluindo 67 PDFs. Existem 25 recusas/ausências editoriais ou de identidade. A listagem de competências CNPJ é disponibilidade, não coleta de todos os cadastros antigos. |
| Documento e referências | `python -m backend.crawler.estatisticas` e depois `python -m backend.crawler.sumarizacao` | [Sumarização integral](../../docs/sumarizacao-acervo-tributario.md) por frente e [inventário de referências](../../docs/referencias-acervo/inventario-integral.json), incluindo todas as versões catalogadas e URLs de originais/recibos verificados. |

Os números dos manifestos descrevem o recorte da execução, não a totalidade universal das instituições. O documento distingue normas, interpretações, julgados, editoriais, tabelas e modelos sem força normativa. Referências em cache sem snapshot semântico não inflam a contagem de documentos. As estatísticas devem ser atualizadas antes de regenerar a sumarização.

Fotografia final de 05/11/2026: **7.213 entradas/versionadas**, **10.601 conteúdos originais distintos por hash**, **30.806 páginas em 2.010 PDFs distintos**, **413.739 raízes empresariais** e **10.429 GiB** de dados locais. A recuperação de anexos fechou **382/382** (378 Word e quatro imagens); OCR e fidelidade permanecem sujeitos a revisão. O documento integral tem **40 capítulos de referências e 10.760 URLs distintas**. Todos os 14.566 links locais do documento foram conferidos. Passaram 332 testes dos coletores e um da API; a auditoria não encontrou divergências técnicas nem originais sem metadados. Requisições em cache com recibo são distinguíveis de snapshots semânticos e não aumentam a contagem de documentos.
