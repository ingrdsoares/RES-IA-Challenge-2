# Diagnóstico de causas comuns — 2026-11-17

Objetivo: orientar uma correção generalizada, evitando regras de produto por pergunta, artigo ou caso de teste. Nenhum código do produto ou prompt em produção foi alterado nestes experimentos.

## Controle 1: instruções gerais simplificadas

Seleção uniforme: todos os 22 casos da bateria nos quais o jurídico concluiu a etapa com afirmações. Foram preservados pergunta, payload das fontes, modelo, schema LegalResult, seed, temperatura, contexto e orçamento de saída. Apenas o prompt de sistema foi substituído. A saída jurídica original já estava registrada no lote, portanto não se repetiu a orquestração completa para construir a referência.

Resultados do prompt alternativo: oito saídas answered e 14 insufficient_context. Todas passaram pelo schema e pela checagem de IDs; isso não implica correção semântica.

Observações de conteúdo:

- A06 deixou de publicar a afirmação de contratação ilimitada, mas absteve-se e justificou de forma contraditória que a fonte dizia um único empregado sem definir um máximo.
- A07 absteve-se de generalizar elegibilidade de atividades: melhora de prudência, sem resposta completa sobre atividades permitidas.
- A23 continuou descrevendo PD como multiplicação, alterando a fórmula fornecida.
- A13 passou a afirmar que microempresa obrigatoriamente implica Simples, ao contrário da própria afirmação jurídica original. Simplificar instruções não melhorou uniformemente os resultados.
- A17 devolveu a própria pergunta como afirmação, embora o JSON tenha sido aceito.
- A40 e A48, que haviam entregue respostas pertinentes, passaram a se abster.

Não é uma comparação estatística de acurácia: o conjunto foi selecionado pelo comportamento anterior, a execução ocorreu uma vez por entrada e o julgamento qualitativo não foi independente.

Evidência completa: `2026-11-17-experimento-prompt-juridico.json`.

## Controle 2: raciocínio solicitado e maior orçamento

Nos três casos que haviam publicado respostas incorretas (A06, A07 e A23), utilizou-se o prompt jurídico original e o mesmo payload de evidências. A requisição passou a usar think=True e num_predict=4096, em vez de think=False e 1024. As duas configurações mudaram juntas; não é possível atribuir causalidade a apenas uma delas. O raciocínio interno do modelo não foi salvo, somente a resposta estruturada e métricas.

| Caso | Saída original | Saída nessa configuração | Revisão |
| --- | --- | --- | --- |
| A06 | Contratação sem limite | Um empregado, com exceção de substituição por afastamento | Melhorou a leitura do trecho fornecido |
| A07 | Qualquer atividade permitida | Ausência de restrições à prática de profissão, desde que atenda a critérios de microempresa | Continua confundindo liberdade de exercício com elegibilidade ao enquadramento |
| A23 | Multiplica também pela PD | Continua multiplicando pela PD | Erro de interpretação da fórmula persistiu |

Tempos de chamada: aproximadamente 36,8 s, 30,4 s e 48,9 s. Não se testou a latência de um fluxo completo nessa configuração nem se demonstrou melhora nos outros 47 casos.

Evidência completa: `2026-11-17-experimento-raciocinio-juridico.json`.

## Implicações para o brainstorm

1. A interpretação incorreta já aparece na saída isolada do especialista; a síntese final e a orquestração não são a única origem dos erros.
2. Prompt simples e a configuração de raciocínio ensaiada não foram suficientes para resolver as três respostas incorretas de modo uniforme.
3. O resultado não separa completamente limitações do modelo, representação do texto e qualidade do contexto: as fontes originais continuam recortadas, contêm remissões e fórmulas com estrutura textual degradada.
4. As falhas de numeração, contrato e seleção de intenção são classes distintas de erro. Uma refatoração comum pode tratá-las de forma uniforme, mas os ensaios não sustentam prometer que uma única flag resolve todas.
5. Antes de substituir a arquitetura, cabe comparar outro modelo/configuração de interpretação com as mesmas entradas e medir preservação de negações, exceções, fórmulas e limites de evidência.

## Restrições propostas para a correção

- Nenhuma condição de produto baseada em A06/A23, palavras de uma pergunta específica, limite de empregado ou fórmula de um caso particular.
- Um protocolo comum para especialistas e uma responsabilidade explícita por interpretação, composição de resposta e validação.
- Casos específicos permanecem apenas nos dados de avaliação e regressão.
- Medir efeito no conjunto inteiro e em perguntas novas, incluindo regressões de utilidade por excesso de abstenção.
- Preservar evidências originais e diferenciar falha de contrato, contexto insuficiente e resposta sem suporte.

A escolha da correção ainda está em brainstorm. Estes arquivos são probes diagnósticos, não uma implementação de correção aprovada.
