# ADR 001: Estratégia de Hospedagem de Inferência e Projeção de Custos de IA em Produção

> **Status:** Aprovado  
> **Data:** 11 de Novembro de 2026  
> **Frente:** Ops (DevOps & MLOps — Ingrid Soares) e Ciência de Dados (Jhessica)  
> **Referência:** Issue E4.1 (Etapa 4: Produção — RES-IA Challenge 2)  
> **Decisores:** Clara, Ingrid Soares, Jhessica, Lucas, Nasser  

---

## 1. Contexto e Problema de Negócio

O **Sócio Digital** é um copiloto de orientação tributária voltado para microempreendedores individuais (MEIs) e microempresas (MEs). O sistema realiza duas operações intensivas de Inteligência Artificial a cada interação:

1. **Recuperação Vetorial Densa e Esparsa (RAG):** Conversão da consulta do usuário em embeddings de 1024 dimensões e busca sobre acervo normativo (LC 123/2006, Resoluções CGSN, Receita Federal).
2. **Geração Estruturada e Raciocínio Normativo (LLM):** Síntese contextualizada de plano em 3 passos (Diagnóstico, Ação e Documento comprobatório), com injeção obrigatória do disclaimer ético de não substituição do contador (CRC) e zero alucinação.

### Requisitos e Restrições do Sistema
* **Latência (RNF08):** Tempo total de resposta ponta a ponta $\le 500$ ms sob carga normal.
* **Modelo Econômico:** O produto visa atender um público de baixa renda empresarial; o custo unitário por usuário ativo mensal deve ser inferior a R$ 0,20 para viabilizar modelo gratuito/freemium.
* **Complexidade Operacional:** A equipe de desenvolvimento é enxuta; a manutenção contínua de clusters de GPU com drivers CUDA, orquestração de vLLM e cold starts adiciona alto overhead de sustentação.

---

## 2. Alternativas Avaliadas

### Alternativa A: Auto-hospedagem em GPU Cloud Dedicada (Self-Hosted vLLM / Ollama)
Hospedagem de instâncias com GPU dedicada na nuvem (ex.: AWS EC2 `g5.xlarge` com NVIDIA A10G 24GB ou GCP `n1-standard-4 + NVIDIA T4 16GB`):
* **Modelo:** Qwen 2.5 / 3 8B (quantizado em FP16 ou AWQ) + BGE-M3 Embeddings servidos via vLLM.
* **Custo Fixo Mensal:**
  * Instância AWS `g5.xlarge` (On-Demand): \$1.006/hora $\approx$ **\$724,32 / mês**.
  * Instância GCP `n1-standard-4 + T4`: $\approx$ **\$450,00 / mês**.
* **Vantagens:** Soberania total sobre os dados empresariais; sem cobrança variável por token; latência local previsível.
* **Desvantagens:** Custo fixo proibitivo para fase inicial/piloto (paga \$450-\$700 mesmo com 50 usuários); incapacidade de auto-scaling sem provisionar novas instâncias caras; necessidade de equipe dedicada para monitorar drivers, OOM (out of memory) e degradação de GPU.

---

### Alternativa B: APIs Externas Proprietárias de Grande Porte (OpenAI GPT-4o / Claude 3.5 Sonnet)
Uso de modelos de fronteira comerciais via API gerenciada:
* **Preço Médio de Mercado (2026):**
  * Input: \$2.50 / 1 milhão de tokens.
  * Output: \$10.00 / 1 milhão de tokens.
* **Consumo por Consulta RAG Típica:**
  * Input (Prompt + Top-3 Chunks de Legislação): 1.500 tokens $\rightarrow$ \$0.00375.
  * Output (Plano em 3 passos + Citações): 350 tokens $\rightarrow$ \$0.00350.
  * Custo por Consulta: **\$0.00725** (aprox. R$ 0,042 por pergunta).
* **Vantagens:** Raciocínio avançado e capacidade analítica máxima.
* **Desvantagens:** Custo 10x a 20x superior às alternativas otimizadas; latência de rede superior (frequentemente > 1.200 ms em modelos grandes, violando o RNF08).

---

### Alternativa C: APIs Externas Gerenciadas de Alta Eficiência (Google Gemini 1.5 Flash / OpenAI GPT-4o-mini)
Utilização de modelos ultra-rápidos e otimizados para tarefas de RAG e sumarização estruturada:
* **Preço Médio de Mercado:**
  * **Gemini 1.5 Flash:** \$0.075 / 1 milhão de tokens (input) e \$0.30 / 1 milhão de tokens (output).
  * **GPT-4o-mini:** \$0.15 / 1 milhão de tokens (input) e \$0.60 / 1 milhão de tokens (output).
  * **Embeddings (Gemini / OpenAI Small):** \$0.02 / 1 milhão de tokens.
* **Consumo por Consulta RAG:**
  * Input (1.500 tokens): \$0.00011.
  * Output (350 tokens): \$0.00010.
  * Custo Total por Pergunta: **\$0.00021** (aprox. **R$ 0,0012 por consulta**).
* **Vantagens:**
  * Custo marginal irrisório: 1.000 consultas custam apenas \$0,21 (aprox. R$ 1,20).
  * Latência de inferência extremamente baixa (180 ms a 320 ms), atendendo plenamente ao requisito RNF08 ($\le 500$ ms).
  * Auto-scaling infinito gerenciado pelo provedor de nuvem (zero infraestrutura de GPU para gerenciar).
* **Desvantagens:** Dependência de conectividade externa e necessidade de conformidade com termos de uso de dados (LGPD).

---

## 3. Decisão Arquitetural

A equipe deliberou e **APROVOU a Alternativa D: Arquitetura Híbrida de Transição com Gemini 1.5 Flash / GPT-4o-mini em Produção e Ollama em Desenvolvimento/Staging**.

```
                ┌────────────────────────────────────────────────────────┐
                │             ESTRATÉGIA HÍBRIDA DE INFERÊNCIA           │
                └────────────────────────────────────────────────────────┘
                                             │
                     ┌───────────────────────┴───────────────────────┐
                     ▼                                               ▼
         [Ambientes Locais & Staging]                    [Ambiente de Produção Cloud]
          • Engine: Ollama / vLLM local                   • Engine: API Gerenciada Eficiente
          • Modelo LLM: Qwen 3 8B                         • Modelo LLM: Gemini 1.5 Flash (ou GPT-4o-mini)
          • Embeddings: Qwen3-Embedding (1024d)           • Embeddings: Gemini Embeddings / OpenAI Small
          • Custo: $0 adicional (hardware existente)     • Custo: Pay-as-you-go ($0.00021 / consulta)
          • Objetivo: Validação e CI determinístico       • Objetivo: Alta escala, latência < 350ms, zero ops
```

### Justificativas da Escolha
1. **Sustentabilidade Financeira Imediata:** Elimina o gasto fixo de \$450 a \$700/mês com servidores de GPU dedicados enquanto o produto ainda está na fase de tração e MVP.
2. **Latência Compatível com RNF08:** APIs otimizadas respondem em média em ~250 ms, enquanto GPUs compartilhadas ou instâncias pequenas sofrem com fila e gargalos de decodificação.
3. **Desacoplamento e Portabilidade:** O motor de RAG e o serviço de orquestração (`backend/api/app/rag.py` e `LocalModels`) utilizam contratos abstratos, permitindo chaveamento instantâneo via variáveis de ambiente (`INFERENCE_PROVIDER=gemini|openai|ollama`) sem refatoração de código.

---

## 4. Projeção Financeira Detalhada por Volume de Usuários

Considerando o padrão médio de uso de um microempreendedor (20 consultas fiscais/mês, com 1.500 tokens de contexto recuperado e 350 tokens de resposta gerada):

| Escala de Adoção | Usuários Ativos Mensais (MAU) | Consultas Mensais | Custo Mensal Estimado (API Eficiente) | Custo Fixo de GPU Dedicada (vLLM) | Economia Mensal | Custo por Usuário Ativo (R$) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Piloto / Validação** | 100 | 2.000 | **\$0,42** (R$ 2,40) | \$450,00 (R$ 2.610) | **99,9%** | R$ 0,024 / mês |
| **Lançamento MVP** | 1.000 | 20.000 | **\$4,20** (R$ 24,36) | \$450,00 (R$ 2.610) | **99,1%** | R$ 0,024 / mês |
| **Fase de Crescimento**| 5.000 | 100.000 | **\$21,00** (R$ 121,80) | \$724,00 (R$ 4.200) | **97,1%** | R$ 0,024 / mês |
| **Tração Consolidada** | 20.000 | 400.000 | **\$84,00** (R$ 487,20) | \$1.448,00 (R$ 8.400) | **94,2%** | R$ 0,024 / mês |
| **Ponto de Equilíbrio** | ~100.000 | 2.000.000 | **\$420,00** (R$ 2.436) | \$450,00 (R$ 2.610) | *Break-even* | R$ 0,024 / mês |

> **Conclusão Econômica:** A auto-hospedagem em GPU dedicada só se justifica financeiramente quando a base ultrapassar **100.000 usuários ativos mensais**. Até essa marca, a API gerenciada de alta eficiência economiza mais de 90% do orçamento do projeto.

---

## 5. Mitigações de Riscos e Governança

1. **Privacidade e LGPD:** Nenhuma informação pessoal identificável (PII), senhas ou faturamentos brutos sensíveis são injetados nas consultas de RAG; o prompt contextualiza apenas o enquadramento tributário, CNAEs e termos da dúvida.
2. **Resiliência a Indisponibilidade de Provedor (Fallback):** O pipeline de inferência implementa circuit breaker com fallback configurado: se o provedor primário falhar ou sofrer timeout (> 5s), a requisição é automaticamente reencaminhada para o provedor secundário.
3. **Prevenção de Abuso:** Proteção obrigatória via **Rate Limiting** no nível da API (Issue E4.5) para impedir que requisições automatizadas ou bots gerem custos imprevistos na fatura da API.
