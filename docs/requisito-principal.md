# Análise Técnica: Qual é o Principal Requisito do Projeto?

> **Projeto:** Sócio Digital — Copiloto de Gestão Fiscal para Pequenos Negócios  
> **Programa:** Residência em Inteligência Artificial (RES-IA) — Challenge 2 (Grupo 08)  
> **Integrantes:** Clara, Ingrid, Jhessica, Lucas, Nasser  
> **Download do PDF Consolidado:** [requisito-principal-socio-digital.pdf](requisito-principal-socio-digital.pdf)

---

## A Pergunta Central do Avaliador / Stakeholder

> *"Qual o principal requisito do meu projeto? Aquele que, se faltar, o projeto simplesmente não funcionaria?"*

### Resposta Executiva
O **Sócio Digital** não é apenas um assistente de conversação comum (chatbot descartável); ele é um copiloto de conformidade e tomada de decisão tributária. Por consequência, seu funcionamento apoia-se em um **trinômio de requisitos vitais**:

1. **Entrada de Negócio ([RF01](definicao-projeto.md#requisitos-funcionais)):** Contexto Empresarial (CNAE / Faturamento / Folha). Sem ele, inexiste base matemática e legal.
2. **Núcleo Arquitetural ([RF03](definicao-projeto.md#requisitos-funcionais) / [RNF05](definicao-projeto.md#requisitos-nao-funcionais)):** RAG Factual + Motor Determinístico. Sem ele, a IA alucina e gera multas ao usuário.
3. **Entrega de Valor ([RF07](definicao-projeto.md#requisitos-funcionais)):** Planos de Ação Estruturados em 3 Etapas. Sem ele, o sistema vira um chat descartável sem utilidade.

---

## 1. O Requisito Vital de Entrada: Cadastro do Contexto Empresarial (RF01)

No sistema tributário nacional regido pela **Lei Complementar nº 123/2006**, é impossível emitir qualquer orientação ou apuração contábil no vácuo. Toda regra fiscal depende estritamente do cruzamento simultâneo de quatro variáveis cadastradas no perfil da empresa:

* **CNAE (Classificação Nacional de Atividades):** Determina de forma taxativa se o negócio pode ser MEI ou se obrigatoriamente deve migrar para o Simples Nacional. Além disso, vincula a atividade aos Anexos de I a V da LC 123/2006.
* **Faturamento Bruto Acumulado (RBT12):** A apuração do Simples Nacional não usa alíquota fixa. Exige a fórmula oficial:  
  $$\text{Alíquota Efetiva} = \frac{(\text{RBT12} \times \text{Alíquota Nominal}) - \text{Parcela a Deduzir}}{\text{RBT12}}$$  
  Sem o RBT12, a alíquota não existe.
* **Folha de Pagamento e Pró-Labore (Fator R):** Para empresas de serviços (tecnologia, engenharia, saúde), se a razão entre folha e faturamento for $\ge 28\%$, a empresa tributa no Anexo III (6%); se for menor, cai no Anexo V (15,5%).
* **Localização Municipal e Estadual:** Define a incidência de ISS ou ICMS e a aplicação de sublimites fiscais estaduais.

### O que acontece se faltar o Contexto Empresarial (RF01)?
* Qualquer orientação contábil torna-se puro palpite genérico e juridicamente perigoso.
* O usuário pode pagar 15,5% de imposto em vez de 6% por desconhecer a aplicação do Fator R.
* O empreendedor corre o risco de desenquadramento retroativo do MEI com multa de 20% e juros SELIC.

---

## 2. O Requisito Arquitetural Inegociável: RAG Factual + Motor Determinístico (RF03 / RNF05)

O maior risco mapeado pelo Grupo 08 na concepção do Sócio Digital é a **alucinação do LLM**. Modelos fundacionais são motores probabilísticos de texto: eles tendem a inventar alíquotas plausíveis, errar contas com decimais e citar artigos revogados. Na contabilidade, um erro de R$ 0,01 invalida o Documento de Arrecadação do Simples Nacional (DAS).

### A Solução Arquitetural de Clara, Nasser, Lucas e Jhessica
1. **Ingestão e Vector Store Factual (`src/rag/`):** A legislação oficial (LC 123/2006, CGSN 140/2018) é indexada por dispositivos jurídicos canônicos. Cada chunk preserva o artigo, parágrafo, órgão emissor e período de vigência.
2. **Motor Determinístico em Python (`src/fiscal/`):** As regras matemáticas de dedução, alíquotas efetivas e enquadramento do MEI são 100% determinísticas em código Python (`FiscalCalculator`). O LLM é expressamente proibido de calcular impostos.
3. **Papel do LLM na Solução:** O modelo generativo apenas recebe os números calculados pelo motor determinístico e o texto oficial resgatado pelo RAG para sintetizar uma explicação acolhedora, didática e livre de jargões técnicos.

---

## 3. O Requisito de Entrega de Valor: Planos de Ação em até 3 Passos (RF07)

Pequenos empresários vivem sobrecarregados de tarefas operacionais e sob constante terror fiscal. Um chat tradicional que responde longas explicações teóricas gera paralisia por análise. O diferencial do projeto é o requisito RF07, que converte toda resposta em no máximo 3 etapas acionáveis:

* **Passo 1 (Diagnóstico):** Identificar a pendência exata na base oficial (ex.: Notificação de Débito no Portal e-CAC).
* **Passo 2 (Execução):** Instrução objetiva do que fazer (ex.: Como aderir ao Programa de Parcelamento do Simples Nacional).
* **Passo 3 (Comprovação):** Como obter a Certidão Positiva com Efeito de Negativa (CPEN) para manter o negócio apto a emitir notas.

---

## 4. A Fronteira Regulatória e Ética: Não Exercício Ilegal da Contabilidade (RNF04)

O Decreto-Lei nº 9.295/1946 reserva privativamente a contadores registrados no CRC a emissão de balanços e pareceres fiscais. O Sócio Digital foi desenhado sob o requisito RNF04 (Abstenção e Disclaimers): atua no letramento e organização fiscal prévia, e se abstém proativamente, recomendando a validação presencial com o contador em operações societárias complexas.

---

## 5. Matriz Comparativa: O Impacto da Ausência de Cada Requisito

| Requisito | Tipo / Camada | Objetivo no Projeto | Impacto se Inexistir |
| :--- | :--- | :--- | :--- |
| **RF01: Contexto** | Funcional (Entrada) | Capturar CNAE, RBT12, porte e folha salarial. | Cálculos impossíveis; respostas genéricas inválidas. |
| **RF03: RAG Factual** | Funcional (IA/Dados) | Ancorar respostas em normas oficiais vigentes. | Alucinação jurídica com normas revogadas. |
| **RNF05: Motor Python** | Arquitetura / Regras | Executar Fator R e alíquotas com exatidão matemática. | Erros de centavos que invalidam guias DAS oficiais. |
| **RF07: Planos 3 Passos** | Funcional (UX/Entrega) | Converter dúvidas em tarefas acionáveis e claras. | Usuário perdido em textos longos; abandono do app. |
| **RF06: Painel Semáforo** | Funcional (Gestão) | Acompanhar conformidade e alertar vencimentos. | Usuário perde prazos e acumula multas moratórias. |
| **RNF04: Abstenção CRC** | Não-Funcional (Ético) | Respeitar prerrogativas do profissional contábil. | Processos judiciais por exercício ilegal da profissão. |

---

## 6. Conclusão e Resumo para Defesa Técnica

> *"Se fôssemos forçados a eleger um único requisito sem o qual o projeto sequer existiria, a resposta é o **DESACOPLAMENTO ENTRE O CONTEXTO EMPRESARIAL (RF01) E O MOTOR DETERMINÍSTICO ANCORADO EM RAG (RF03/RNF05)**.*  
> 
> *Um modelo generativo isolado destrói a confiança do empreendedor porque não sabe calcular tributos. Uma calculadora fria de impostos sem IA não ajuda o leigo que tem pavor de guias e termos contábeis.*  
> 
> *A essência do Sócio Digital é unir o rigor matemático da LC 123/2006 à capacidade do LLM de traduzir a burocracia em um plano acolhedor de 3 passos, libertando o microempreendedor do terror fiscal e devolvendo sua qualidade de vida."*
