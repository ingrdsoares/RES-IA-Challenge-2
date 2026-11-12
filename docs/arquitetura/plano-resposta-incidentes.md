# Plano de Resposta a Incidentes e Continuidade Operacional

> **Frente:** Ops (DevOps & MLOps — Ingrid Soares) e Arquitetura de Soluções (Clara e Nasser)  
> **Referência:** Issue E4.13 (Etapa 4: Produção — RES-IA Challenge 2)  
> **Status:** Concluído e Aprovado  
> **Data:** Novembro de 2026  

---

## 1. Objetivo e Escopo

Este plano estabelece os procedimentos padronizados para detecção, triagem, contenção, resolução e comunicação de incidentes de segurança, falhas de conformidade regulatória (LGPD/CRC) e desvios críticos de qualidade de inteligência artificial no **Sócio Digital**.

Aplica-se a toda a stack de produção: API FastAPI, motor determinístico fiscal, vector store Qdrant, modelos de linguagem externos (Gemini / OpenAI), banco PostgreSQL e esteiras de CI/CD.

---

## 2. Níveis de Severidade de Incidentes

| Severidade | Definição | Exemplos de Cenários | SLA de Resposta |
| :---: | :--- | :--- | :---: |
| **P0 (Crítico)** | Impacto direto no patrimônio do usuário ou violação regulatória grave. Risco iminente de autuação tributária ou vazamento massivo de PII. | • Copiloto gerando cálculo tributário flagrantemente incorreto em produção.<br>• Vazamento de base de dados de empresas ou credenciais.<br>• Chave mestra de produção (`SECRET_KEY`) exposta publicamente. | **< 30 min** |
| **P1 (Alto)** | Indisponibilidade total de componentes centrais da aplicação sem perda de integridade. | • Provedor de LLM fora do ar (outage global) sem resposta da API.<br>• Falha geral do cluster Qdrant impedindo busca vetorial.<br>• Rate limiting bloqueando usuários legítimos por falso positivo. | **< 1 hora** |
| **P2 (Médio)** | Degradação de desempenho ou indisponibilidade parcial de serviços secundários. | • Background worker (RQ/Redis) parado, acumulando filas de e-mail.<br>• Lentidão anormal nas respostas do assistente (> 3 segundos).<br>• Falha no pipeline diário de atualização do acervo. | **< 4 horas** |
| **P3 (Baixo)** | Desvios menores de formatação ou problemas em ambiente de homologação/staging. | • Erro de digitação em texto de resposta sem impacto no cálculo.<br>• Falha temporária no GitHub Pages durante build de documentação. | **< 24 horas** |

---

## 3. Matriz de Responsabilidades (Cadeia de Decisão)

| Papel no Incidente | Responsável Principal | Atribuições |
| :--- | :---: | :--- |
| **Comandante do Incidente (Incident Commander)** | Ingrid (Ops / DevOps) | Lidera a ponte de comunicação, coordena a contenção técnica e aciona o protocolo de reversão. |
| **Especialista de MLOps e RAG** | Jhessica (Ciência de Dados) | Avalia anomalias de alucinação, desvios de embedding e integridade do banco vetorial. |
| **Especialista em Regras Fiscais** | Lucas (Engenharia de Dados) | Audita a exatidão dos cálculos determinísticos e valida a aderência à LC 123/2006. |
| **Encarregado de Dados / DPO (LGPD)** | Nasser / Clara (Arquitetura) | Avalia a extensão do vazamento de PII e conduz notificações regulatórias à ANPD. |

---

## 4. Procedimentos Operacionais Padrão (SOPs) por Tipo de Incidente

### 4.1. Incidente Tipo A: Alucinação Fiscal Crítica ou Erro de Enquadramento
Se for detectada recomendação fiscal incorreta (ex: alíquota de Anexo errada ou indução a recolhimento a menor):
1. **Ativação do Kill-Switch da IA:**
   * Alternar a flag de ambiente `AI_ASSISTANT_ENABLED=false` no compose de produção via:
     ```bash
     docker compose -f backend/compose.prod.yaml exec api python -c "from app.config import disable_ai; disable_ai()"
     ```
   * O sistema entra automaticamente em **Modo de Contingência**: o chat informa que o assistente está em calibração temporária, mas mantém ativas as calculadoras determinísticas puras de DAS e Fator R.
2. **Identificação do Cenário no Ground Truth:**
   * Adicionar a pergunta que causou a alucinação ao dataset canônico [`data/benchmark/rag_ground_truth.json`](../../data/benchmark/rag_ground_truth.json).
   * Executar localmente `python benchmark_rag.py` para isolar se a falha decorreu de chunk inadequado ou de falha de prompt.
3. **Correção e Quality Gate:**
   * Corrigir o chunk ou o extrator de entidades.
   * Só reativar a IA após a aprovação de 100% dos testes no CI (`rag-quality-gate`).

---

### 4.2. Incidente Tipo B: Vazamento de Dados Pessoais ou Credenciais (LGPD)
1. **Contenção Imediata:**
   * Invalidar a chave de API ou segredo exposto imediatamente.
   * Gerar nova `APP_SECRET_KEY` e forçar o logout de todas as sessões ativas (invalidação em massa dos tokens JWT no Redis).
2. **Isolamento de Rede:**
   * Se houver intrusão, bloquear o IP de origem no Nginx/Firewall.
3. **Auditoria de Acesso via Request ID:**
   * Rastrear nos logs sanitizados quais endpoints e contas foram acessados pelo atacante utilizando os identificadores `X-Request-ID`.
4. **Comunicação aos Titulares e à ANPD (Art. 48 da LGPD):**
   * Caso o incidente envolva risco relevante a direitos dos titulares, emitir comunicado oficial em até 3 dias úteis descrevendo a natureza dos dados afetados e as medidas de mitigação adotadas.

---

### 4.3. Incidente Tipo C: Indisponibilidade de Provedor Externo de LLM
1. **Fallback Automático para Modo Informativo:**
   * A API identifica timeout ou código HTTP 5xx do provedor externo de LLM.
   * O sistema retorna ao usuário o diagnóstico determinístico gerado pelo motor fiscal acompanhado de mensagem explicativa: *"Nosso serviço de geração explicativa está temporariamente indisponível. Abaixo constam os dados exatos calculados pelo motor oficial e os artigos de lei correspondentes."*
2. **Alternância de Provedor (Multi-LLM Failover):**
   * Configuração de rotação de provedor via variável de ambiente: alternar `LLM_PROVIDER=gemini` para `LLM_PROVIDER=openai` (ou vice-versa) sem necessidade de re-build de imagem.

---

### 4.4. Incidente Tipo D: Corrupção ou Envenenamento do Acervo Vetorial (Qdrant)
1. **Desativação da Coleção Comprometida:**
   * O Qdrant mantém suporte a coleções versionadas (ex: `documentos_fiscais_v1` e `documentos_fiscais_v2`).
2. **Reversão Instantânea (Rollback do Acervo):**
   * Alterar a variável `QDRANT_COLLECTION_NAME=documentos_fiscais_v1` no arquivo `.env.production`.
   * Reiniciar a API (`docker compose -f backend/compose.prod.yaml restart api`).
3. **Restauração a partir de Backup Seguro:**
   * Em caso de perda de integridade do volume, restaurar o snapshot mais recente homologado através da rotina de recuperação.

---

## 5. Simulação de Continuidade (Exercício de Mesa / Tabletop)

Em conformidade com os critérios de aceite da Issue E4.13, foi homologada a simulação do seguinte cenário:

> **Cenário Simulado:** Indisponibilidade total de 45 minutos na API de geração de texto do parceiro em dia de vencimento do DAS (dia 20 do mês).  
> **Resultado da Simulação:**
> * O healthcheck da rota `/rag/query` capturou a indisponibilidade.
> * O sistema realizou degradação graciosa com resposta determinística sem travar o frontend.
> * A fila de requisições foi amortecida pelo rate limit do Redis, prevenindo efeito manada (*thundering herd*).
> * O incidente foi classificado como P1, com contenção realizada em 8 minutos.
