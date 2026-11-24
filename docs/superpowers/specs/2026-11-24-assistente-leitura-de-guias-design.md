# Leitura de guias no Assistente Fiscal

O usuário pode fazer uma pergunta sobre uma imagem de DAS já enviada na tela Fiscal. A primeira entrega cobre um PNG ou JPEG por mensagem no fluxo **Conferir uma guia**. Na apresentação, uma guia fictícia basta para demonstrar texto e imagem na mesma consulta.

## Abordagens

- **DeepSeek Flash pela API, abordagem escolhida.** O modelo recebe texto e imagem juntos. O Sócio Digital reaproveita a integração com a DeepSeek e o armazenamento privado das evidências. A imagem selecionada vai ao provedor na chamada de leitura. [Documentação de visão da DeepSeek](https://api-docs.deepseek.com/guides/vision/)
- **Modelo com visão no Ollama.** A leitura roda na máquina que hospeda o modelo, com instalação e avaliação de desempenho próprias.
- **OCR local.** Serve como referência de qualidade para leitura de campos. A etapa de interpretação recebe o texto extraído.

## Fluxo

1. Em **Conferir uma guia**, o usuário seleciona uma evidência do tipo guia com uma imagem já enviada e escreve a pergunta. A interface informa que a imagem selecionada será analisada pela DeepSeek. O envio usa o identificador da evidência no contrato da mensagem.
2. A API valida que a evidência pertence à mesma empresa da conversa, está acessível à conta e tem uma imagem compatível. O worker confere o vínculo antes de ler os bytes no bucket privado existente. A API da DeepSeek recebe os bytes codificados na requisição.
3. O worker chama `deepseek-flash` apenas para a leitura. Guarda o resultado estruturado com o identificador da evidência e disponibiliza à resposta os campos legíveis de competência, vencimento e valor. O conteúdo da imagem entra como dado. A pergunta original e as fontes jurídicas continuam acessíveis ao fluxo do Assistente.
4. O Assistente mostra de qual guia vieram os dados. Quando um campo estiver ilegível, indica qual está faltando ou pede uma imagem melhor. Se uma consulta fiscal depender de uma competência ausente ou divergente, pede confirmação ao usuário antes de aplicá-la. Uma leitura da guia mantém a situação de pagamento como não verificada.

A leitura por imagem é habilitada pela configuração da funcionalidade e pela chave da DeepSeek. O assistente por texto continua disponível com o provedor já configurado. O escopo da primeira entrega termina em PNG e JPEG de DAS.

## Critérios de aceite

- Uma imagem legível de DAS e a pergunta “Qual a competência e o valor desta guia?” produzem dados compatíveis com a imagem e identificam a evidência usada.
- Uma imagem ilegível gera orientação para esclarecer o campo ou trocar a imagem. Uma evidência de outra empresa é recusada antes da chamada externa.
- Se a competência for necessária para a consulta, o fluxo dá à leitura a oportunidade de ajudar antes de solicitar confirmação. O reprocessamento após confirmação reutiliza a leitura da mesma imagem.
- A suíte verifica o formato texto + imagem enviado à API, o fluxo de resposta e uma pergunta comum por texto. O teste com o provedor usa uma guia fictícia.
