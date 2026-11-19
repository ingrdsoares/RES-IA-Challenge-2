# Auditoria de UI/UX do Sócio Digital

18 de novembro de 2026 · Frontend local · Tema original

## Resultado após a implementação

As 11 telas avaliadas receberam os ajustes abaixo. Foram acrescentadas as telas de solicitação de link e de redefinição de senha. No ambiente local, o Mailpit captura o e-mail de recuperação. O procedimento para configurar o envio em produção está no [README do backend](../../backend/README.md#recuperação-de-senha).

- Tarefas e evidências abrem pelo identificador do link. No celular, o retorno restaura a posição e o foco no item selecionado.
- A autenticação recupera o destino interno e o assistente preserva o rascunho por conta, empresa e conversa. O perfil confirma o salvamento na própria página.
- Na biblioteca, o título dos resultados passou de 870 para 589 px do topo em 390 × 844. Os seis alvos de toque revisados mediram pelo menos 44 px em ambos os temas.
- As 13 telas renderizaram no Edge em 390 × 844 e 1440 × 900 com os temas Original e Azul e Areia, sem rolagem horizontal no conjunto de dados exercitado. Os 12 testes Playwright, os cinco testes unitários do frontend e os 43 testes de acesso e configuração do backend passaram.
- A redefinição também foi exercitada pelo navegador com a caixa de e-mail local, incluindo o novo login e a revogação da sessão anterior.

## Achados da auditoria inicial

| Prioridade | Como reproduzir | Impacto | Critério de aceite |
| --- | --- | --- | --- |
| Alta · tarefa incorreta | Com tarefas cadastradas, abrir `#tarefas?task=inexistente`. O detalhe exibe a primeira tarefa da lista e permite concluí-la. | Uma pessoa pode alterar a tarefa errada a partir de um link antigo. | Quando a URL indicar um ID indisponível, mostrar “Tarefa não encontrada”, oferecer “Ver todas as tarefas” e ocultar ações sobre outros registros. Abrir a lista sem ID pode continuar selecionando a primeira. |
| Alta · retorno após autenticação | Abrir um link direto de tarefa sem sessão e entrar. O destino muda para `#assistente`. A expiração da sessão também substitui a rota por `#entrar`. | Quem segue uma referência perde a tela e os parâmetros que a identificam. | Guardar o destino interno e restaurá-lo após autenticar, validando o acesso da empresa ativa. O acesso comum pela landing continua abrindo o assistente. |
| Alta · rascunho da conversa | Escrever uma pergunta, usar “Consultar minhas tarefas” e voltar pelo navegador. O campo fica vazio. | Consultar o contexto da própria pergunta exige redigitá-la. | Recuperar o texto por empresa e conversa durante a sessão. Limpar o rascunho após envio bem-sucedido ou saída da conta. |
| Alta · detalhe de tarefa no celular | Em 390 × 844, com 12 tarefas, tocar na segunda. O detalhe atualizado começa a cerca de 1.560 px do topo da janela. | A seleção parece não ter funcionado e a ação de conclusão fica distante. | No celular, colocar o detalhe em foco e à vista após a seleção. Voltar deve recuperar filtro, posição e item da lista. Preservar a leitura lado a lado no desktop. |
| Média · alternância entre entrar e criar conta | Em `#entrar`, clicar em “Criar conta” e recarregar. A URL continua em `#entrar` e o login reaparece. As duas telas abertas diretamente têm o título de aba “Painel da empresa”. | Recarregar, favoritar e usar Voltar produzem resultados diferentes da tela exibida. | Usar as rotas públicas existentes para alternar e definir um título de aba próprio para cada tela. |

## Revisão por página

| Página | Observação | Melhoria proposta |
| --- | --- | --- |
| Landing | A prévia responde ao mouse, tem controle de pausa e respeita movimento reduzido. Em 390 px, a área do link “Conhecer os recursos” mede 20 px de altura. | Ampliar a área de toque mantendo o peso visual de ação secundária. |
| Entrar | A senha tem controle de visibilidade. A tela não oferece recuperação de acesso. | Depois de corrigir o retorno ao destino, planejar “Esqueci minha senha” com solicitação, confirmação e redefinição completas. |
| Criar conta | A exigência de 12 caracteres aparece no placeholder e desaparece durante a digitação. | Exibir a regra como ajuda persistente associada ao campo. |
| Cadastro da empresa | CNPJ e CNAE têm máscaras e o município depende da UF. Porte e regime usam texto livre. | Oferecer sugestões para porte e regime, preservando valores aceitos pela API e dados antigos. |
| Perfil da empresa | “Salvar alterações” leva ao assistente inclusive quando nenhum campo foi alterado. | Manter a pessoa no perfil após editar, confirmar o salvamento e desabilitar a ação enquanto não houver alteração. Reservar o salto ao assistente para o primeiro cadastro. |
| Assistente fiscal | O fluxo retoma conversas enviadas. O texto ainda em edição se perde ao consultar tarefas. | Preservar o rascunho. Ampliar a área de toque de “Simular cálculo fiscal”, que mediu 20 px de altura no celular. |
| Visão geral | Os indicadores abrem o escopo fiscal correspondente. O CNPJ aparece sem máscara no resumo e formatado no seletor de empresa. | Reutilizar a formatação do seletor. Ampliar “Ver detalhes” e “Ver todas as tarefas”, medidos em 28 e 20 px de altura. |
| Situação fiscal | O escopo fica na URL. A evidência selecionada fica apenas no estado da tela, e seu detalhe vem depois da lista na ordem de leitura. | Permitir retomar a evidência por link. No celular, levar o foco ao detalhe e oferecer retorno ao item selecionado. |
| Tarefas | Filtros e seleção têm URL própria. Há dois problemas reproduzidos com detalhe móvel e ID indisponível. | Corrigir ambos antes de acrescentar filtros ou novos comandos. |
| Biblioteca de normas | Os filtros sobrevivem à ida ao leitor e à volta. No celular, o título “Normas encontradas” começa a 870 px do topo, abaixo da primeira tela de 844 px. | Deixar a busca visível e recolher os quatro filtros complementares em “Filtros”, indicando a quantidade aplicada. |
| Leitor da norma | A citação destaca a passagem e oferece retorno à resposta. A volta à biblioteca recuperou a busca “MEI”. O link de retorno mediu 20 px de altura no celular. | Ampliar o alvo de retorno e reutilizar esse padrão de preservação de contexto em tarefas e evidências. |

## Consistência visual

A cor de ação, a navegação e as superfícies já têm tokens compartilhados. A biblioteca, o leitor e o painel também usam cores fixas da escala Slate para textos, bordas e fundos. Na próxima revisão de componentes, começar por links secundários, campos com ajuda e cartões de detalhe. Conferir cada componente nos temas Original e Azul e Areia. Para links isolados de uso frequente no celular, adotar 44 px de altura como meta de conforto e medir a área clicável completa.

## Cobertura e limites

- Foram percorridas as 11 telas em Edge com janelas de 1440 × 900 e 390 × 844. Nenhuma apresentou rolagem horizontal com o conteúdo exercitado. A amostragem comparativa usou conta, empresa, tarefas e norma ilustrativas com respostas controladas.
- Os seis testes Playwright do projeto passaram. O cenário integrado usou o backend local para cadastro, tarefa, evidência, conversa, edição de perfil e reentrada. O destaque de uma citação no leitor foi verificado pelo teste com dados simulados.
- As prioridades refletem comportamentos reproduzidos e inspeção do frontend. A revisão não incluiu aparelhos físicos, leitor de tela, ensaio com usuários ou comparação visual completa dos dois temas.
