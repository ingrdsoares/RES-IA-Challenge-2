# Contexto máximo do Qwen local

Alteração solicitada pelo usuário: usar o máximo da instalação atual, incluindo o contexto entregue ao jurídico.

- `/api/show` do Ollama informa `qwen3.context_length=40960` para o modelo instalado `qwen3:8b`.
- Padrão do backend e Compose: `NUM_CTX=40960`, `MAX_CONTEXT_CHARS=40960`.
- Saída permanece `NUM_PREDICT=1024`; os 40.960 tokens são a janela total, não uma reserva exclusiva para documentos.
- O jurídico deixou de cortar as fontes em 2.200 caracteres. A seleção agora considera pergunta, prompt, schema, metadados, saída e margem de 256 tokens, com limite conservador por bytes UTF-8.
- Os trechos recuperados são preservados integralmente quando cabem; trechos maiores são limitados ao orçamento restante. O limite de caracteres e a janela de tokens têm unidades diferentes.
- O orçamento total de reservas dos agentes foi ajustado para 1.228.800 (30 chamadas × 40.960), preservando limites de tentativas e chamadas.
- Não houve reindexação, mudança de modelo, de prompts, de thinking ou de vigência.

## Evidências

- Testes novos observados falhando antes da alteração: configuração de 40.960 recusada e ausência do seletor de contexto.
- Testes de contexto validam oito fontes completas de 3.000 caracteres e preservação do orçamento UTF-8 numa configuração menor de 8K.
- Testes anteriores que dependiam do padrão de 8K foram ajustados para o novo padrão e mantêm casos de rejeição/truncamento de entradas grandes.
- Suíte completa: 377 aprovados, dez opcionais pulados, em 33,55 segundos.
- Compose resolvido confirma os mesmos três valores na API, worker e dispatcher.
- Teste real com as fontes indexadas da aplicação: oito trechos, 11.972 caracteres de evidência, 6.895 tokens de entrada medidos; saída de 53 tokens, em aproximadamente 55,5 segundos de geração.
- O modelo respondeu ao caso de contratação de empregados com a condição de um único empregado e citação do trecho recebido.
- `/api/ps` confirmou `context_length=40960`, com aproximadamente 11 GB ocupados pelo modelo.

A chamada real não ocupou a janela inteira: os oito trechos recuperados somam menos texto que seu limite. A evidência confirma a configuração máxima e a entrega de mais contexto, não uma melhoria geral de qualidade. A bateria de 50 não foi repetida nesta alteração.
