# Motor Fiscal e Ingestão Estruturada — Sócio Digital

> **Frente:** Engenharia de Dados & Dev  
> **Responsável:** Lucas  
> **Diretrizes de Arquitetura:** Clara e Nasser  
> **Projeto:** Sócio Digital — Copiloto de Gestão Fiscal para Pequenos Negócios (Challenge 2)

---

## 1. Visão Geral

Este módulo é responsável pela ingestão, saneamento e cálculo das bases fiscais determinísticas do projeto **Sócio Digital**, cumprindo a separação arquitetural estrita:
- **Lógica Determinística:** Cálculos matemáticos de alíquotas efetivas, deduções, Fator R e regras de enquadramento são executados por código determinístico auditável, sem alucinações.
- **Lógica Generativa:** O modelo de linguagem (LLM) consome as saídas deste motor para redigir diagnósticos claros, empáticos e acessíveis ao empreendedor.

---

## 2. Bases de Dados Brutas (`data/raw/`)

1. **[`data/raw/tabelas_simples_nacional.json`](../../data/raw/tabelas_simples_nacional.json):**
   - As tabelas oficiais completas dos **Anexos I a V** da LC 123/2006 (atualizadas pela LC 155/2016 e Resolução CGSN 140/2018).
   - Contém as 6 faixas de receita bruta anual (RBT12 até R$ 4.800.000,00), alíquotas nominais, parcelas a deduzir e repartição percentual dos tributos (IRPJ, CSLL, Cofins, PIS/Pasep, CPP, ICMS, ISS e IPI).
   - Parâmetros do MEI: teto de faturamento (R$ 81.000,00), margem de tolerância (20% = R$ 97.200,00) e alíquotas do DAS-MEI (5% INSS + R$ 1,00 ICMS + R$ 5,00 ISS).

2. **[`data/raw/cnaes_base.json`](../../data/raw/cnaes_base.json):**
   - Base catalogada de CNAEs voltados para MEI, Microempresas e Empresas de Pequeno Porte (Comércio, Serviços Gerais, Tecnologia/Fator R, Indústria, Saúde e Jurídico).
   - Mapeamento direto de enquadramento, anexo padrão, sujeição ao Fator R e ocupação permitida no MEI.

---

## 3. Estrutura de Arquivos

```
src/fiscal/
├── __init__.py           # Exportação das classes e modelos principais
├── models.py             # Dataclasses (CNAEItem, FaixaSimples, CalculoSimplesResultado, etc.)
├── ingest.py             # Pipeline de carga para SQLite com índices e FTS5
├── repository.py         # Repositório de consultas e busca textual rápida
├── calculator.py         # Motor determinístico de cálculo de alíquotas, Fator R e MEI
└── README.md             # Esta documentação
```

---

## 4. Fórmulas e Regras Fiscais Implementadas

### 4.1 Alíquota Efetiva do Simples Nacional (Art. 18, § 1º da LC 123/2006)
$$\text{Alíquota Efetiva} = \frac{(\text{RBT12} \times \text{Alíquota Nominal}) - \text{Parcela a Deduzir}}{\text{RBT12}}$$

### 4.2 Regra do Fator R (Art. 18, §§ 5º-J e 5º-M da LC 123/2006)
$$\text{Fator R} = \frac{\text{Folha de Salários nos últimos 12 meses}}{\text{Receita Bruta nos últimos 12 meses}}$$
- **Fator R $\ge$ 28%:** Atividade intelectual migra para o **Anexo III** (alíquotas a partir de 6%).
- **Fator R $<$ 28%:** Atividade permanece no **Anexo V** (alíquotas a partir de 15,5%).

### 4.3 Regra de Desenquadramento do MEI (Art. 18-A, § 7º da LC 123/2006)
- **Até R$ 81.000,00:** Enquadrado normalmente no MEI (guia fixa DAS-MEI).
- **Entre R$ 81.000,01 e R$ 97.200,00 (excesso $\le 20\%$):** Desenquadramento vigora a partir de 1º de janeiro do ano-calendário subsequente.
- **Acima de R$ 97.200,00 (excesso $> 20\%$):** Desenquadramento retroativo ao dia 1º de janeiro do ano em curso, com recolhimento das diferenças pelo Simples Nacional com acréscimos legais.

---

## 5. Como Executar os Testes

```bash
python test_fiscal.py
```

Valida:
1. Ingestão e integridade do banco SQLite (`data/processed/fiscal.db`) e manifesto (`fiscal_manifest.json`).
2. Resolução e busca full-text (FTS5) de CNAEs.
3. Simulação determinística do Anexo I (Comércio).
4. Aplicação do Fator R e migração do Anexo V para Anexo III (Tecnologia/Software).
5. Cálculo da guia DAS-MEI (Salão de Beleza).
6. Regra de desenquadramento do MEI por excesso de faturamento.

