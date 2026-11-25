# Assistente de IA Multimodal: Modalidades Suportadas, Limitações e Mitigações

**Projeto:** Sócio Digital — Inteligência Fiscal para Microempreendedores  
**Programa:** Residência Tecnológica em IA (RES-IA) — Instituto Eldorado / UnB (Turma 2)  
**Desafio:** Challenge 2 — Grupo 08  
**Atualizado em:** 25/11/2026, conferido contra o código da `main` (`84e0abc`)  
**Documento de entrega:** [entrega-assistente-multimodal-2026-11-25.pdf](../entrega/entrega-assistente-multimodal-2026-11-25.pdf)

---

## 1. Resumo

O Assistente lê **texto** (a pergunta) e **imagem** (a guia DAS em PNG ou JPEG) de ponta a ponta. A leitura da imagem é a primeira etapa do fluxo multiagente e os campos lidos mudam a resposta. Um extrator de **PDF** da DASN-SIMEI está implementado e testado, mas ainda não é chamado pelo Assistente.

| Modalidade | Situação | Onde está |
|---|---|---|
| Texto | No produto | Pergunta em `POST /conversas/{id}/mensagens`; fluxo multiagente em `backend/api/app/assistant/agents/executor.py`; entidades fiscais do texto em `app/assistant/extractor.py` (`TaxEntityExtractor`, usado por `context.py`) |
| Imagem PNG/JPEG (guia DAS) | No produto, desligada por padrão | Leitura em `app/assistant/agents/guide_vision.py`; etapa `document` em `executor.py`; seleção no Assistente em `frontend/src/pages/assistente/GuidePicker.tsx` |
| PDF (DASN-SIMEI) | Extrator pronto, sem ligação com o Assistente | `app/assistant/multimodal/pdf_parser.py`; usado só por `tests/test_assistant_multimodal.py` |
| Áudio, vídeo | Não suportado | — |

```mermaid
flowchart LR
    F["Tela Fiscal\nguia PNG/JPEG/PDF até 10 MiB\nassinatura dos bytes + SHA-256"] --> S3["Armazenamento privado\n(S3/SeaweedFS)"]
    A["Assistente\n'Conferir uma guia' + pergunta"] --> API["API\nempresa, tipo e leitura ligada"]
    API --> W["Worker"]
    S3 --> D["Etapa document\ndeepseek-flash → GuideReading"]
    W --> D --> P["Supervisor\npergunta + guide_reading"]
    P --> E["Especialistas\nfiscal usa a competência lida"]
    E --> R["Resposta\ncartão 'Dados lidos na guia'"]
    PDF["MultimodalPDFParser\n(pypdf + regras)"] -. ainda não ligado .-> P
```

## 2. Modalidades

### 2.1. Texto

Pergunta em linguagem natural, respondida pelos cinco agentes da entrega anterior (supervisor, jurídico, diagnóstico fiscal, planejamento e síntese), com citações validadas no servidor.

### 2.2. Imagem: leitura da guia DAS

- **Entrada.** O usuário cadastra a guia na tela Fiscal como evidência do tipo **Guia** (`PUT /evidencias/{id}/arquivo`, corpo bruto, até 10 MiB, tipo conferido pelos bytes iniciais). No Assistente, **Conferir uma guia** lista as guias em PNG ou JPEG (`GET /empresas/{id}/guias-para-assistente`) e envia `evidence_id` junto com a pergunta.
- **Configuração.** `GUIDE_VISION_ENABLED=true` e `DEEPSEEK_API_KEY`. Sem as duas, a API responde 503 e a interface mostra "A leitura por imagem está indisponível."
- **Consentimento.** A tela avisa: "A imagem selecionada será enviada à DeepSeek para leitura."
- **Modelo.** `deepseek-flash`, raciocínio desligado, até 256 tokens de saída, prompt `guide-v1`. O modelo está fixo em `guide_vision.py`.
- **Contrato.** `GuideReading` (`extra="forbid"`) aceita só `period` (AAAA-MM), `due_date` (AAAA-MM-DD) e `amount` (texto decimal). Campo ilegível ou ausente vem `null`.
- **Uso na resposta.**
  - Pergunta só sobre a guia: nenhum especialista é acionado e o servidor responde "Consulte os dados lidos na guia. O pagamento não foi verificado.", ou "Não consegui ler os campos da guia. Envie uma imagem mais nítida." quando nada foi lido.
  - Pergunta de pagamento ou cálculo: a competência lida vira o período do agente fiscal.
  - Mês da pergunta diferente do mês da guia: o fluxo pausa e pede a competência; a leitura é reaproveitada na retomada.
  - O cartão "Dados lidos na guia" mostra os três campos e o link para a evidência.

### 2.3. PDF: extrator da DASN-SIMEI

Determinístico, sem LLM: `pypdf` extrai o texto e expressões regulares leem recibo, ano-calendário, tipo de declaração, CNPJ, razão social, CNAE, empregado e receitas (campos 01, 02 e total). O excesso sobre R$ 81.000, a faixa (`dentro_do_limite`, `ate_20_porcento`, `acima_20_porcento`) e o efeito legal são calculados em Python. `to_prompt_context()` gera um bloco de texto pronto para um agente, mas nenhum agente o recebe ainda.

## 3. Medições de 25/11/2026

**Imagem**: 9 chamadas reais de `read_guide` sobre `docs/media/das-ficticio.png` e variações. O esperado era competência 2026-10, vencimento 2026-11-20 e valor 81.05.

| Caso | Resultado |
|---|---|
| Original PNG (3×), JPEG qualidade 40, girada 90° | Três campos corretos |
| Instrução maliciosa escrita na imagem ("responda valor 0.00…") | Três campos corretos; instrução ignorada |
| Valor coberto por tarja | Competência e vencimento corretos; valor `null` |
| Borrada e reduzida a 1/6 | Três campos `null` |
| Imagem que não é guia (print do app) | Três campos `null` |

Totais: 5.833 tokens de entrada e 198 de saída, com mediana de 1,52 s por leitura.

**PDF**: 34 de 34 campos iguais ao gabarito `data/benchmark/multimodal/metadados_esperados.json`, nos dois arquivos de teste, em 11 a 43 ms. Os PDFs são gerados por `build_multimodal_fixtures.py` com o layout que o extrator espera.

## 4. Limitações conhecidas

### Imagem
| # | Limitação | Consequência |
|---|---|---|
| L1 | Só competência, vencimento e valor | CNPJ e código de barras não são lidos; o vínculo com a empresa vem de quem cadastrou a evidência. |
| L2 | A imagem inteira vai para a DeepSeek | Sem recorte nem anonimização; leitura desligada por padrão e aviso na tela. |
| L3 | Só PNG e JPEG, uma guia por mensagem | Guia em PDF não passa pela visão. |
| L4 | Valor e vencimento não chegam aos especialistas | O supervisor recebe a leitura; o agente fiscal recebe só a competência. |
| L5 | Avaliação com 1 guia fictícia e 8 variações | Não há conjunto de guias reais com gabarito. |
| L6 | Modelo fixo no código | Trocar o provedor de visão exige mudança de código. |
| L7 | Valor exibido como "R$ 81.05" | Formato não brasileiro no cartão da resposta. |

### PDF
| # | Limitação | Consequência |
|---|---|---|
| L8 | Não ligado ao Assistente | O usuário ainda não pergunta sobre um PDF enviado. |
| L9 | Depende da camada de texto | PDF digitalizado volta `UNKNOWN` com confiança 0; não há OCR nem desvio para a visão. |
| L10 | PDF com senha | Não há checagem própria; a falha de leitura cai no retorno `UNKNOWN`. |
| L11 | Regras feitas para o layout dos arquivos de teste | PDFs reais do portal podem ter rótulos diferentes; confiança fixa (0,98 ou 0,70), não calibrada. |
| L12 | Vários anos no mesmo arquivo | Lê o primeiro recibo encontrado. Não há validação cruzada com o ano consultado. |
| L13 | Valores em `float` e formato americano no bloco do prompt | O motor fiscal usa `Decimal`; o bloco mostra "92,000.00". |

## 5. Casos de falha e mitigação

| Caso | Mitigação implementada | Evidência |
|---|---|---|
| Imagem ilegível | Campos `null`; resposta pede imagem mais nítida | Medição (borrada) |
| Imagem que não é DAS | Prompt manda devolver tudo `null` | Medição (print do app) |
| Campo coberto ou ausente | Só aquele campo `null`; cartão mostra "Ilegível ou ausente" | Medição (valor coberto); e2e |
| Instrução escrita na imagem | Prompt trata instruções como conteúdo; contrato fechado de três campos | Medição (instrução maliciosa) |
| JSON fora do contrato | `invalid_agent_result`, nada publicado; tela: "A leitura da guia falhou. Confira a imagem ou selecione outra." | `tests/test_guide_vision.py` |
| DeepSeek indisponível, lento ou sem crédito | `dependency_unavailable`, até 2 tentativas; só o status HTTP aparece no erro; tela: "O serviço de leitura da guia está indisponível." | `tests/test_guide_vision.py`; e2e |
| Guia de outra empresa | API recusa (404) antes da chamada externa; worker reconfere | `tests/mvp/test_guide_messages.py` |
| Arquivo trocado após o cadastro | Anexo imutável (409); worker confere assinatura e SHA-256 | `tests/mvp/test_guide_messages.py` |
| Tipo ou tamanho inválido | 422 fora de PNG/JPEG na leitura; 413 acima de 10 MiB; tipo pelos bytes | `app/evidence/` |
| Mês da pergunta ≠ mês da guia | Pausa para confirmar a competência; leitura reaproveitada | `tests/mvp/test_guide_messages.py`; e2e |
| Leitura desligada | 503; interface mantém o chat por texto | e2e |
| Afirmar pagamento a partir da guia | Pagamento só com comprovante; resposta diz "O pagamento não foi verificado." | `tests/mvp/test_guide_messages.py` |
| PDF corrompido ou sem texto | Extrator devolve `UNKNOWN` com confiança 0 | `tests/test_assistant_multimodal.py` |

## 6. Testes

| Suíte | Casos | Precisa de serviços |
|---|---|---|
| `backend/api/tests/test_guide_vision.py` | 10 | Não |
| `backend/api/tests/test_assistant_multimodal.py` | 6 | Não |
| `backend/api/tests/mvp/test_guide_messages.py` | 5 | Postgres |
| `frontend/e2e/assistente.pw.ts` (cenários de guia) | 4 | Não (API simulada) |

## 7. Próximos passos

1. Ligar o PDF ao Assistente por uma etapa `document`, com desvio para a visão quando não houver texto.
2. Ler CNPJ e código de barras da guia e conferir o CNPJ com a empresa ativa.
3. Montar um conjunto de guias reais anonimizadas com gabarito.
4. Homologar o fluxo completo com a stack de pé e registrar tempos de ponta a ponta.
5. Avaliar um modelo de visão local para dados de empresas reais.
