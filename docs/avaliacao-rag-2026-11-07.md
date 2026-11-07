# Comparativo do RAG: versão antiga e nova (07/11/2026)

## Conclusão

A versão nova erra menos, mas ainda não tem aprovação fiscal. No teste final de 20 perguntas, as respostas erradas ou recusadas sem motivo caíram de 5 para 2. Essa contagem é uma leitura preliminar, feita pelo Claude, e a amostra é pequena.

A API local já usa a versão nova, porque a anterior segue intacta e a troca é reversível. Recomenda-se não apresentar o ganho como comprovado antes da revisão fiscal: as métricas de similaridade não mostram diferença clara, e seis respostas seguem erradas ou recusadas sem motivo, como q08, q20 e t09.

## Resultado do teste final

Vinte perguntas novas, rodadas uma vez nas duas versões, depois de congelar os ajustes no commit `09c38b9`.

| Leitura preliminar | Antiga | Nova |
|---|---:|---:|
| Correta | 12 | 14 |
| Recusa adequada | 2 | 2 |
| Parcial | 1 | 2 |
| Errada | 4 | 1 |
| Recusa indevida | 1 | 1 |

- **Melhoraram (4):** t01 (base de cálculo do ISS), t06 (efeito da certidão, antes negado), t14 (art. 26 da LC 123, antes recusado) e t19 (passou a pedir os dados).
- **Piorou (1):** t09. A nova recusou porque não recebeu o art. 23 da LC 87/1996.
- **Seguem com problema:** t20 não pede os dados necessários; t01 e t08 são parciais.

## Métricas

Diferença pareada (nova menos antiga), com intervalo de confiança de 95% por bootstrap.

| Conjunto | Métrica | Antiga | Nova | Diferença | IC 95% |
|---|---|---:|---:|---:|---:|
| Teste final (n=20) | ROUGE-L | 0,271 | 0,296 | +0,025 | −0,014 a +0,060 |
| Teste final (n=20) | BERTScore | 0,597 | 0,618 | +0,021 | −0,019 a +0,057 |
| Desenvolvimento (n=25) | ROUGE-L | 0,202 | 0,214 | +0,012 | −0,013 a +0,040 |
| Desenvolvimento (n=22) | BERTScore | 0,617 | 0,617 | 0,000 | −0,021 a +0,020 |

Todos os intervalos incluem zero. Essas métricas medem semelhança de texto, não acerto fiscal: uma resposta errada pode pontuar bem. No BERTScore do desenvolvimento, três perguntas ficaram fora por não terem nota nas duas rodadas.

### Busca

Vinte e duas perguntas de desenvolvimento, na leitura estrita, em que fonte fora do acervo conta como não recuperada.

| Top-k | Medida | Antiga | Nova |
|---:|---|---:|---:|
| 5 | Recall | 0,250 | 0,318 |
| 5 | MRR | 0,224 | 0,384 |
| 8 | Recall | 0,295 | 0,386 |
| 8 | MRR | 0,246 | 0,384 |

O maior ganho é de ordem: o documento certo aparece mais cedo. Essas perguntas guiaram os ajustes, e oito fontes esperadas continuam fora do acervo.

### Tempo

| Conjunto | Antiga: mediana / máximo | Nova: mediana / máximo |
|---|---:|---:|
| Teste final | 1,7 s / 4,0 s | 2,7 s / 6,8 s |
| Desenvolvimento | 2,4 s / 17,0 s | 2,9 s / 8,9 s |

## Desenvolvimento: leitura preliminar

Nas 25 perguntas usadas nos ajustes, 8 melhoraram, 2 pioraram e 15 ficaram iguais. Esse resultado é contexto, não prova.

- **Piores:** q08 generaliza 8% e 12% para prestadoras de serviços, e a referência indica 32%. q20 abre negando que a EC 132/2023 assegure o tratamento simplificado, e a referência diz que sim.
- **Ainda erradas:** q07 não cita o Emissor Nacional, e q25 não pede RBT12 e folha.
- **Conclusão frágil:** q16 chega ao "não pode", mas por uma lista de impedimentos ao Simples, não pelo Anexo XI.

## O que mudou

- **Coleção `knowledge_base_v2`:** 155.575 pontos, contra 176.529. Sai ruído repetido do acervo e entram quatro documentos antes barrados, sendo dois mascarados.
- **Busca híbrida:** vetores densos e BM25, com vaga garantida para a norma citada na pergunta.
- **Reranker:** `BAAI/bge-reranker-v2-m3`, em contêiner próprio com GPU. Se falhar, a busca mantém a ordem híbrida.
- **Contexto:** agora chega a 12.000 caracteres e 8 fontes. Antes, uma estimativa contava cada byte como um token e cortava em cerca de 5.000 caracteres mesmo com limite maior.
- **Prompt:** ausência de menção não é negação; pedido de sonegação é recusado de imediato.

## Limitação de hardware

A RTX 3080 Ti tem 12 GB. Com contexto de 16.384 tokens, o modelo estourava a memória de vídeo, e a leitura do prompt caiu de 1.289 para 54 tokens/s, gerando 14 e 7 timeouts em duas rodadas de 25 perguntas. Essas rodadas foram descartadas.

A configuração final usa 8.192 tokens e gera o embedding da pergunta na CPU, em cerca de 0,1 s e com cosseno de pelo menos 0,999 em relação ao da GPU. O uso de VRAM caiu para cerca de 10,4 GB. Uma rodada com embedding ainda na GPU teve 4 timeouts e também foi descartada.

## Limites desta avaliação

- **Sem independência:** o Claude escreveu as 20 perguntas e referências do teste final, implementou as mudanças e fez a leitura preliminar. As referências constam como `pendente_humana`.
- **Amostra pequena:** 4 melhoras contra 1 piora em 20 perguntas não bastam para afirmar ganho.
- **Perguntas diretas:** o teste final tem muitas perguntas simples, em que as duas versões acertam igual.
- **Referência a conferir:** em q06, a referência indica 18% e a versão antiga citou 20%. O decreto citado não está no acervo, e a vigência não foi inferida.
- **Teste único de contexto real:** a pergunta sobre a LC 87 agora traz a própria lei em primeiro lugar, mas a resposta ainda precisa de conferência.

## Próximos passos

1. **Revisão fiscal:** preencher `handoff/revisao-fiscal-rag-2026-11-07.xlsx`, começando pela aba Teste final.
2. **Acervo:** incluir as fontes que faltam, com destaque para o Decreto DF 43.982 e a jurisprudência de q11 e q12.
3. **Geração:** depois da revisão, tratar conclusões sem base, como q08, q16 e q20. Elas pedem um conjunto novo de perguntas, porque as 20 atuais já foram gastas.

## Como reproduzir

- Rodadas locais, fora do Git, em `backend/evaluation/runs/`: `all25-2026-11-07`, `dev25-congelado`, `final20-base` e `final20-novo`.
- Versão antiga: commit `a7299bc`, coleção `knowledge_base`, 5 fontes.
- Versão nova: commit `09c38b9`, coleção `knowledge_base_v2`, 8 fontes.
- Busca: `data/benchmark/recuperacao_qdrant.json` e `data/benchmark/recuperacao_v2.json`.
