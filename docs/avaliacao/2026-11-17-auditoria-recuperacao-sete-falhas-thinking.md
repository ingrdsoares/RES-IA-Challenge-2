# Auditoria das sete falhas — 16K com thinking

Investigação das sete operações `failed` do lote interrompido: A03, A04, A05, A07, A09, A12 e A13. Não são os 13 casos ainda em fila nem todas as respostas de qualidade discutível.

Método: leitura dos payloads efetivamente enviados, inspeção dos 348 pontos indexados, repetição somente da busca densa com o embedding atual e validação das saídas registradas usando o código existente. Nenhuma geração nova, treinamento, alteração de produto ou retomada da bateria. As âncoras relevantes foram identificadas manualmente; não houve comparação entre modelos de embedding.

## Achados por caso

| Caso | Evidência no índice e posição na busca repetida | O que chegou ao jurídico | Falha posterior observada |
| --- | --- | --- | --- |
| A03 — componentes do MEI | `s76-550615e03730`, posição 3, score 0,617 | O trecho correto foi reduzido de 3.000 para 2.141 caracteres. A alínea sobre ISS ficou fora do payload. Dois trechos anteriores consumiram 6.000 caracteres. | Conclusão parcial; síntese escreveu `[1]` mas declarou `legal:3`. |
| A04 — participação societária | `s77-a2fd117a767c`, posição 12, score 0,460, contém vedação de participação como titular/sócio/administrador | A regra relevante não estava nos cinco primeiros; somente três fontes couberam no payload. Jurídico se absteve. | Síntese criou conclusão e citou fontes apesar de o jurídico não fornecer claims; rejeitada como sem suporte dos especialistas. |
| A05 — filial | `s77-a2fd117a767c`, posição 2, score 0,504 | Trecho completo de 3.000 caracteres, incluindo vedação a mais de um estabelecimento. Jurídico produziu conclusão pertinente. | Síntese inseriu art. 11 da Lei 13.109/2015, ausente da conclusão sustentada, e escreveu `[1]` para `legal:2`. |
| A07 — qualquer atividade | `s77-a2fd117a767c`, posição 8, score 0,489, contém restrições de atividade | Fontes sobre natureza do MEI, conselhos e empregado; a passagem com restrições ficou fora dos cinco primeiros. Não se identificou uma lista exaustiva de atividades permitidas. | Jurídico extrapolou; síntese declarou `legal:1`/`legal:3` mas escreveu `[1]`/`[2]`. |
| A09 — desenquadramento e baixa | `s79-9bb1cb6cd988` posição 2; `s78-a1b65f361226` posição 3; `s32-0257f59e4306` posição 13, score 0,483 | Passagens de desenquadramento chegaram; trecho geral sobre extinção/baixa ficou fora dos cinco primeiros. Fonte sobre baixa por fraude foi recuperada em primeiro. | Conclusão distinguiu procedimentos, com terminologia imprecisa e fundamentação parcial; síntese citou `[1]` declarando duas fontes. |
| A12 — CNPJ e opção pelo Simples | `s53-561759725db8` (art. 16), posição 3, score 0,652 | Os 3.000 caracteres da fonte relevante chegaram. Jurídico negou opção automática. | Síntese escreveu `[1]`, mas declarou `legal:3` e `legal:5`. |
| A13 — porte e regime | `s53-561759725db8` (art. 16), posição 4, score 0,720 | Os primeiros 1.315 caracteres chegaram, incluindo caput que trata de opção. A primeira fonte falava de opção por contabilidade simplificada, diferente da opção pelo regime. | Jurídico chegou à distinção correta, mas incluiu também essa referência inadequada; síntese escreveu `[1]` declarando `legal:1` e `legal:4`. |

Os scores são similaridade vetorial, não probabilidades de relevância ou correção. Todas as âncoras relevantes listadas superaram o limiar 0,3; nesses casos baixar o limiar não as colocaria automaticamente entre as cinco primeiras.

## Causas separadas

- **Recuperação/ranking contribui em A04, A07 e parcialmente A09:** há passagens relevantes no índice, porém fora do top 5. Isso confirma problema de seleção nessa configuração, sem provar que trocar o embedding seja a única ou melhor solução.
- **Montagem/truncamento contribui diretamente em A03:** a busca encontrou o trecho, mas o orçamento conservador de contexto o cortou antes da parte do ISS. O aumento da geração para 4.096 também reduz o orçamento de entrada. A janela nominal não equivale ao texto efetivamente entregue; o cálculo usa o tamanho em bytes como limite conservador de tokens.
- **Evidência pertinente já chegou em A05, A12 e A13:** melhorar recuperação não é requisito para corrigir o bloqueio observado nesses casos. Ainda é desejável melhorar a ordem, excluir ruído e sustentar corretamente cada claim.
- **Contrato de saída falha nos sete casos:** a validação reproduziu seis erros `Citações inline inconsistentes` e um `Síntese sem suporte dos especialistas`. Esses são os motivos imediatos da ausência de resposta publicada; não medem, por si só, incapacidade do embedding.
- **Interpretação e fidelidade ainda falham:** A07 extrapola fontes incompletas; A05 introduz referência sem suporte na síntese; A13 mistura fontes sobre opções diferentes. Corrigir apenas os marcadores publicaria algumas respostas ainda problemáticas.

## O que isso permite concluir sobre fine-tuning + embedding

É plausível que melhorar a recuperação e treinar interpretação/fidelidade gere ganhos, mas os sete casos não demonstram que essa combinação resolva o sistema. Fine-tuning do gerador não corrige diretamente ranking, truncamento ou gestão de operações. Melhor embedding não garante contrato de saída nem elimina extrapolação.

A comparação causal ainda ausente é: manter pergunta, fontes e formato iguais para comparar geradores; e manter índice, recortes e gabarito de passagens iguais para comparar recuperadores. Treinar e medir nos mesmos sete casos não demonstraria generalização.

Não foi realizada nova checagem de vigência. Os trechos foram analisados apenas como evidências recebidas pelo experimento, conforme a autorização anterior para ignorar vigência no fluxo.

[Dados da auditoria, rankings e textos recebidos](2026-11-17-auditoria-recuperacao-sete-falhas-thinking.json).
