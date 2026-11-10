# Guia de APIs para Dados e Documentos Fiscais no Brasil

Este guia reúne os principais conceitos, fornecedores, arquiteturas e links de documentação oficiais para integração de Notas Fiscais (NF-e, NFC-e, NFS-e) e dados tributários no ecossistema de software brasileiro.

---

## 1. Desafios do Ecossistema Fiscal Brasileiro (Por que usar APIs?)

A integração direta com os servidores do governo (SEFAZ estaduais e sistemas municipais) apresenta complexidades críticas:

1. **Heterogeneidade de Padrões:**
   * **NF-e e NFC-e:** Padronizadas nacionalmente via SEFAZ estadual, usando protocolos SOAP/WSDL e payloads XML.
   * **NFS-e:** Cada município adota seu próprio provedor (ex.: Ginfes, Betha, Thema, WebISS, DSF) com regras, schemas XML e autenticações distintas, embora o padrão NFS-e Nacional venha sendo expandido progressivamente.
2. **Segurança e Certificação:** Exigência de assinatura digital de arquivos XML via Certificado Digital ICP-Brasil (geralmente modelo A1 em formato `.pfx` ou `.p12`).
3. **Contingência e Disponibilidade:** SEFAZ e prefeituras sofrem instabilidades frequentes, exigindo lógica de contingência (ex.: SVC-AN, SVC-RS, emissão offline de NFC-e).
4. **Complexidade Tributária:** Regras e cálculos de ICMS, PIS, COFINS, IPI, ISS e a transição para a Reforma Tributária (IBS e CBS).

---

## 2. Principais Gateways de Emissão e Gestão Fiscal (APIs REST)

Os gateways fiscais abstraem a camada SOAP/XML. A sua aplicação envia um JSON estruturado via REST API e o gateway assina, valida, transmite e retorna o PDF (DANFE) e o XML autorizado.

| Provedor | Modelos Atendidos | Principais Características | Documentação / Link Oficial |
| :--- | :--- | :--- | :--- |
| **Focus NFe** | NF-e, NFC-e, NFS-e, CT-e, MDF-e, NFCom | Uma das mais maduras; ampla cobertura municipal; suporte a webhooks; rotas de empresas (multi-tenant). | [Doc Focus NFe](https://doc.focusnfe.com.br/) |
| **Nuvem Fiscal** | NF-e, NFC-e, NFS-e, CT-e, MDF-e | Desenvolvida com foco em DX (OpenAPI/Swagger); arquitetura em nuvem escalável; SDKs em várias linguagens. | [Site / Docs Nuvem Fiscal](https://www.nuvemfiscal.com.br/) |
| **PlugNotas (TecnoSpeed)** | NF-e, NFC-e, NFS-e (Nacional/Municipal), MDF-e | Braço SaaS da TecnoSpeed; grande suporte para Software Houses e ERPs complexos; painel web e API robusta. | [Doc PlugNotas](https://atendimento.tecnospeed.com.br/hc/pt-br/articles/23715383551767-Primeiros-Passos-com-o-Plugnotas) |
| **Webmania®** | NF-e, NFC-e, NFS-e, CT-e, MDF-e | Motor de cálculo de impostos automático; muito utilizada em e-commerce e startups; recursos de monitor fiscal. | [Doc REST API Webmania](https://webmania.com.br/docs/) |
| **NFE.io** | NF-e, NFC-e, NFS-e | Focada em plataformas SaaS, assinaturas, pagamentos recorrentes e simplificação de notas de serviço. | [Produtos & Docs NFE.io](https://nfe.io/produtos/) |

---

## 3. APIs para Consulta e Monitoramento de Dados Fiscais

Usadas para consultar notas emitidas contra o CNPJ (entradas/compras), validar cadastros fiscais antes da emissão ou auditar XMLs.

### Captura de Notas Recebidas (MDe e Prefeituras)
* **Qive (antigo Arquivei):** Plataforma de consulta e download em lote de NF-e, NFS-e e CT-e emitidas contra um CNPJ direto da SEFAZ, com conciliação contábil e compliance.
  * Link: [qive.com.br](https://qive.com.br/)
* **Focus NFe / Webmania (Monitor Fiscal):** Ambos possuem endpoints específicos para Manifestação do Destinatário (MDe) e download automático de notas de compra.

### Consulta de Cadastros e Dados Complementares (CNPJ, Inscrição Estadual, CEP)
* **BrasilAPI (Open Source / Gratuita):** Consulta de dados de CNPJ na base pública da Receita Federal, CEP, IBGE, feriados bancários e taxas.
  * Documentação: [brasilapi.com.br/docs](https://brasilapi.com.br/docs)
* **ReceitaWS:** API de consulta de CNPJ com dados cadastrais e CNAEs atualizados.
  * Documentação: [receitaws.com.br](https://receitaws.com.br/)
* **Hub do Desenvolvedor:** APIs para consulta de Sintegra/Inscrição Estadual por UF, validação de situação fiscal e cadastros públicos.
  * Link: [hubdodesenvolvedor.com.br](https://hubdodesenvolvedor.com.br/)

---

## 4. Soluções Open Source e Autohospedadas

Para projetos que não pretendem pagar custos por documento/transação a gateways terceiros e preferem manter a assinatura e transmissão internamente:

* **Projeto ACBr (ACBrLib / ACBrMonitor):**
  * Solução pioneira no Brasil com suporte completo a todos os documentos fiscais eletrônicos, impressoras fiscais e periféricos de PDV.
  * Disponibiliza bibliotecas em C/C++ (ACBrLib) compatíveis com C#, Java, Python, Node.js e PHP.
  * Repositório / Comunidade: [projetoacbr.com.br](https://www.projetoacbr.com.br/)
* **NFePHP (SPED-NFe):**
  * Conjunto de bibliotecas em PHP para montagem de XML, assinatura digital com certificado A1 e transmissão via SOAP para a SEFAZ.
  * Repositório: [github.com/nfephp-org/sped-nfe](https://github.com/nfephp-org/sped-nfe)

---

## 5. Portais Governamentais e Especificações Oficiais

Documentação original dos layouts oficiais, manuais de orientação do contribuinte (MOC) e esquemas XML (XSD):

* **Portal da Nota Fiscal Eletrônica (SEFAZ / Receita Federal):**
  * [nfe.fazenda.gov.br](https://www.nfe.fazenda.gov.br/)
* **Portal Nacional da NFS-e (Padrão Nacional de Serviços):**
  * [gov.br/nfse](https://www.gov.br/nfse/pt-br)
* **Portal do Conhecimento de Transporte Eletrônico (CT-e):**
  * [cte.fazenda.gov.br](https://www.cte.fazenda.gov.br/)

---

## 6. Checklist de Avaliação para Escolha da API

Antes de escolher o fornecedor para o seu projeto, valide:

1. **Escopo de Documentos:** A solução atende todos os modelos necessários (NF-e, NFC-e, NFS-e, CT-e, etc.)?
2. **Cobertura de NFS-e:** Caso precise de emissão de serviços, os municípios dos seus clientes são homologados pela API?
3. **Multi-Tenancy:** A API permite cadastrar múltiplos CNPJs e fazer upload de certificados digitais A1 programaticamente?
4. **Webhooks e Retentativas:** O gateway notifica via webhook quando uma nota é autorizada/rejeitada, evitando polling contínuo?
5. **Cálculo Tributário:** O motor de cálculo precisa ser fornecido pela API ou o seu sistema já calcula as tags de ICMS/PIS/COFINS?
6. **Modelo de Precificação:** É cobrado por documento emitido (pay-per-use), mensalidade fixa ou por número de CNPJs cadastrados?