# Entrada pelo assistente fiscal

## Experiência aprovada

A landing continua pública. Após entrar ou cadastrar a primeira empresa, o usuário encontra o assistente com o contexto cadastral visível. Pode escrever, iniciar uma consulta guiada, retomar a conversa anterior ou abrir suas tarefas. A citação abre ao lado da conversa no desktop e ocupa a área de leitura no celular.

## Implementação

1. Atualizar os destinos em App, Landing e Empresas e ordenar a navegação em Sidebar.
2. Reorganizar Assistente com histórico recolhido, sugestões, confirmação de competência e ações por orientação. Preservar polling, confirmação e criação idempotente das tarefas.
3. Compor Assistente e Leitor pela URL de citação, mantendo o link direto ao leitor e o retorno à mensagem de origem.
4. Validar cadastro, login, acesso ao histórico, citação e tarefas nos dois tamanhos de tela com Playwright. Executar o build e os testes do frontend.
