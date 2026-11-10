# Comparativo do RAG: versão antiga e nova (07/11/2026)

## Conclusão

A versão nova melhorou de forma clara no teste mais recente, mas ainda não tem aprovação fiscal. Em 20 perguntas novas, ela teve 17 respostas corretas ou recusas adequadas, contra 9 da versão antiga, e nenhuma resposta classificada como errada. Essa classificação é preliminar: foi feita pela mesma equipe que escreveu as perguntas, sem revisão independente.

Nas perguntas usadas nos ajustes, a nova ainda erra em casos importantes, como q07, q13 e q20. Por isso, recomenda-se apresentá-la como uma melhora medida, não como pronta para orientação fiscal sem revisão. A API local já usa a versão nova, e a coleção antiga segue intacta para voltar atrás.

## Correção importante

Parte das referências anteriores não vinha de fontes oficiais. Os arquivos de `data/raw/recorte_demo` foram escritos à mão para uma demonstração, e alguns não correspondem à norma citada:

- **Decreto DF 43.982/2022:** o texto de demonstração o apresenta como Regulamento do ICMS, com alíquota de 18%. O texto oficial institui o sistema de gestão do ISS.
- **Alíquota geral do ICMS-DF:** é de 20% a partir de 22/01/2024, segundo a Solução de Consulta 31/2024 da SEFAZ-DF. Os 18% eram a regra anterior.
- **CARF e STJ (q11 e q12):** não foi possível verificar os acórdãos citados. Essas perguntas agora esperam que o sistema diga que não tem base.

As referências de q06, q07, q11 e q12 foram corrigidas, e os textos de demonstração não entraram no acervo. A versão anterior deste relatório pedia a inclusão do Decreto 43.982 como fonte de ICMS: esse pedido estava errado.

## Teste novo

Vinte perguntas escritas e conferidas no texto oficial antes de rodar. O teste foi executado uma vez nas três versões, com ajustes congelados no commit `2b4d8f9`.

| Leitura preliminar | Antiga | Intermediária | Atual |
|---|---:|---:|---:|
| Correta | 6 | 12 | 13 |
| Recusa adequada | 3 | 3 | 4 |
| Parcial | 3 | 5 | 3 |
| Errada | 3 | 0 | 0 |
| Recusa indevida | 5 | 0 | 0 |

A versão intermediária é a do commit `09c38b9`, já com o acervo novo.

Cinco perguntas (n05 a n09) dependem de documentos que a coleção antiga não tem. Sem elas, restam 15 perguntas, e o total de corretas ou recusas adequadas vai de 9 para 14.

### Métricas

Diferença pareada entre atual e antiga, com intervalo de confiança de 95% por bootstrap.

| Conjunto | Métrica | Antiga | Atual | Diferença | IC 95% |
|---|---|---:|---:|---:|---:|
| Teste novo (n=20) | ROUGE-L | 0,188 | 0,335 | +0,147 | +0,047 a +0,249 |
| Teste novo (n=20) | BERTScore | 0,521 | 0,623 | +0,102 | +0,050 a +0,154 |
| Sem n05 a n09 (n=15) | ROUGE-L | 0,223 | 0,289 | +0,066 | −0,030 a +0,161 |
| Sem n05 a n09 (n=15) | BERTScore | 0,543 | 0,600 | +0,057 | +0,012 a +0,104 |

Essas métricas medem semelhança de texto, não acerto fiscal. A diferença entre atual e intermediária não é clara: BERTScore +0,031, com intervalo de −0,002 a +0,069.

### Tempo por pergunta

| Versão | Mediana | Máximo |
|---|---:|---:|
| Antiga | 1,9 s | 4,9 s |
| Intermediária | 2,6 s | 7,8 s |
| Atual | 2,7 s | 6,7 s |

## Perguntas de desenvolvimento

Nas 25 perguntas usadas nos ajustes, com referências corrigidas, 6 melhoraram, 3 pioraram e 16 ficaram iguais. As corretas ou recusas adequadas foram de 11 para 14. Esse resultado é contexto, não prova.

- **Piores:** q13 não cita o efeito retroativo do desenquadramento; q20 abre negando a continuidade do tratamento simplificado; q21 explica pior a não cumulatividade.
- **Ainda erradas:** q07 afirma que o MEI não pode emitir NFS-e, e q25 não pede RBT12 e folha.
- **Sem conclusão:** q16 diz não haver base para afirmar se o CNAE 6201-5/01 é permitido ao MEI.

A resposta muda com pequenos ajustes no prompt: q07 e q13 pioraram entre rodadas, enquanto q08 e q23 melhoraram. Novos ajustes por pergunta tendem a trocar um erro por outro.

## Busca

Vinte perguntas de desenvolvimento com fonte esperada no acervo atual, na coleção nova.

| Camada | Recall@5 | MRR@5 | Recall@8 | MRR@8 |
|---|---:|---:|---:|---:|
| Densa | 0,375 | 0,279 | 0,450 | 0,288 |
| Híbrida | 0,325 | 0,223 | 0,400 | 0,241 |
| Híbrida com norma citada | 0,375 | 0,323 | 0,400 | 0,331 |
| Reranker com norma citada (em uso) | 0,400 | 0,473 | 0,475 | 0,473 |

A híbrida sozinha é pior que a densa neste conjunto; o ganho vem da norma citada e do reranker. Combinar a ordem da busca com a do reranker não compensou, então não foi adotado. Esses números não são comparáveis aos da rodada antiga, porque as referências mudaram.

## O que mudou

- **Acervo:** coleção `knowledge_base_v2`, com 155.781 pontos. Sai ruído repetido, saem 11 páginas de login do CARF e entram 4 documentos antes barrados e 7 oficiais do DF e do STJ.
- **Busca:** vetores densos e BM25, vaga garantida para a norma citada e reranker `BAAI/bge-reranker-v2-m3` em contêiner próprio. Se ele falhar, a busca mantém a ordem híbrida.
- **Contexto:** até 12.000 caracteres e 8 fontes. Antes, uma estimativa contava cada byte como um token e cortava em cerca de 5.000.
- **Prompt:** ausência de menção não é negação, regra de caso específico não vira regra geral, faltando dados do caso o sistema pede esses dados, e pedido de sonegação recebe recusa fixa.

## Limitação de hardware

A RTX 3080 Ti tem 12 GB. Com contexto de 16.384 tokens, a memória de vídeo estourava, a leitura do prompt caía de 1.289 para 54 tokens/s e surgiam timeouts. A configuração estável usa 8.192 tokens e gera o embedding da pergunta na CPU, em cerca de 0,1 s, com cosseno de pelo menos 0,999 em relação ao da GPU. A VRAM fica perto de 10,8 GB.

## Limites desta avaliação

- **Sem independência:** as perguntas, as referências, as mudanças e a leitura preliminar foram feitas pela mesma equipe.
- **Vantagem de acervo:** as perguntas foram escritas a partir de documentos conhecidos, e cinco só têm resposta na coleção nova.
- **Perguntas diretas:** o teste novo tem muitas perguntas objetivas; casos que exigem raciocínio aparecem mais no desenvolvimento, onde a nova ainda erra.
- **Amostra pequena:** 20 perguntas não cobrem o domínio fiscal.
- **Fontes em falta:** não há fonte oficial sobre pejotização no CARF nem sobre a prescrição discutida em q12. O Informativo 872 do STJ respondeu 403, e a coleta não foi forçada. Fontes do Senado não foram usadas, por falta de aprovação.
- **Referência a conferir:** q20 cita o art. 156-A, § 5º, e precisa de checagem fiscal.
- **Referências antigas:** `data/benchmark/ground_truth_25_perguntas.json` ainda tem os textos anteriores; a versão corrigida está em `backend/evaluation/data/ground_truth_avaliacao.jsonl`.

## Experimentos depois do teste novo

Quatro mudanças foram testadas depois do teste novo, seguindo `docs/arquitetura/tool-calling-busca-rag.md` quando aplicável. Um terceiro conjunto, com 20 perguntas, tem 8 que citam norma e artigo, 5 que citam só a norma, 4 compostas e 3 que pedem dados ou recusa.

| Experimento | Resultado | Decisão |
|---|---|---|
| Raciocínio do modelo ligado | Em 65 perguntas: ROUGE-L −0,067 e BERTScore −0,028, ambos com intervalo abaixo de zero; tempo 2,5 vezes maior; surgem novas invenções | Não adotado |
| Busca direta pelo artigo citado | No terceiro conjunto: BERTScore +0,023 (+0,003 a +0,049); a03, a04 e a05 deixam de recusar sem motivo | Adotada |
| Tool calling | Em cerca de 80 pares: ROUGE-L −0,004 e BERTScore −0,008, com intervalos que incluem zero; cerca de 2 s a mais; 17 de 170 chamadas rejeitadas; corrige c02, mas piora b05 | Não adotado; código em branch local |
| Temperatura 0 e semente fixa | Em duas rodadas iguais: fontes iguais em 20 de 20 e respostas iguais em 15 de 20; as outras 5 mudam a redação | Adotada |

### Perguntas compostas

A pergunta é dividida por regra, sem o modelo, quando a segunda parte começa com palavra interrogativa ou há duas frases com interrogação. Cada parte busca os próprios trechos, e parte sem sigla ou norma herda as das partes anteriores. Os dois melhores trechos da pergunta inteira continuam no topo.

| Conjunto | Resultado |
|---|---|
| 20 perguntas usadas nos ajustes (14 compostas) | Compostas totalmente corretas de 5 para 7; erradas ou recusadas sem motivo de 2 para 1; simples sem mudança |
| Outros 85 pares já usados | Métricas iguais; melhoram c02, c03, q01, q03, q07 e q21, sem piora clara |
| 10 compostas novas, rodadas uma vez | 1 melhora (f04 deixa de afirmar R$ 85 mil para o MEI) e nenhuma piora; métricas iguais |

O custo é cerca de 1,3 s a mais por pergunta composta. A divisão não aciona quando a segunda parte não tem palavra interrogativa, como em "e ele pode emitir".

### Trecho cortado

Cerca de 5% dos trechos do acervo terminam em dois-pontos, como "nos seguintes termos:", e a continuação fica no trecho seguinte. Cada ponto passou a guardar sua posição no documento (campo `ordem`, preenchido sem gerar embedding de novo). Quando um trecho entregue termina em dois-pontos, recebe o corpo do trecho seguinte do mesmo documento.

Nos testes, 44 de 843 trechos entregues terminavam assim, em 33 perguntas. Em 115 pares, as métricas ficaram iguais. Na leitura, cerca de 5 respostas melhoraram (b02 passa a dizer qual é o fato gerador do ISS; t06, t07, k11 e q09 também melhoram) e 1 piorou (f07 afirma que o ICMS incide sobre jornais e depois cita a regra contrária, um erro de interpretação do modelo).

**Variação entre rodadas:** com a temperatura anterior, 17 de 25 e 10 de 20 respostas mudavam sem nenhuma mudança de código. Por isso, diferenças de uma única rodada entre versões, inclusive neste relatório, podem ser em parte acaso. Isso vale para casos como n02, q07 e q13.

**Terceiro conjunto com a configuração final, em leitura preliminar:** 16 corretas ou recusas adequadas, 1 parcial e 3 erradas (b02, c02 e c04). Perguntas compostas seguem sendo o principal ponto fraco.

A API local recebeu essas duas mudanças no commit `27b8335`, por decisão do responsável, antes da revisão humana prevista no plano de tool calling.

## Próximos passos

1. **Revisão fiscal:** pedir a um especialista que confira as respostas classificadas nesta avaliação.
2. **Perguntas independentes:** pedir a quem não conhece o acervo que escreva um novo conjunto, com casos que exijam raciocínio.
3. **Fontes:** obter por canal oficial a jurisprudência de q11 e q12.
4. **Modelo:** se q07, q13 e q20 forem confirmados, avaliar um modelo de geração maior em vez de novos ajustes de prompt.

## Como reproduzir

- Rodadas locais, fora do Git, em `backend/evaluation/runs/`: `novo20-antiga`, `novo20-ontem`, `novo20-atual`, `all25-2026-11-07` e `dev25-v5`.
- Teste novo: `backend/evaluation/data/teste_final_v2_2026-11-07.jsonl`.
- Antiga: commit `a7299bc`, coleção `knowledge_base`, 5 fontes. Intermediária: `09c38b9`. Atual: `2b4d8f9`; ambas com `knowledge_base_v2` e 8 fontes.
- O complemento oficial fica fora do repositório, em `handoff/rtx3080ti/complemento-oficial.csv.gz`.
