# Painel de coleta — desenho

## Por que existe

A coleta do acervo tributário é feita por cerca de 40 comandos separados em `backend/crawler/`, executados um a um no terminal. Eles imprimem pouco, a maioria só no fim. Quem roda não sabe o que está sendo coletado, desde quando, quanto falta, de qual fonte e quantos dados cada grupo tem.

O painel junta esses comandos em um único executor e mostra o processo em uma página local.

## Objetivos

- Um comando único para executar qualquer conjunto de frentes de coleta.
- Página local que mostra, por frente: o que está sendo coletado, quando começou e terminou, tempo restante, fonte e quantos dados a frente tem.
- Escolher frentes, iniciar e parar pela página.
- Servir de panorama do acervo mesmo sem nenhuma coleta rodando.

## Fora do escopo

- Agendamento automático, acesso remoto, login e múltiplos usuários.
- Etapa de refino (`backend/refino/`).
- Validação de conteúdo fiscal. O painel relata execução, não correção nem vigência.
- Buscar dados realmente novos nas frentes que usam cópia local ou período fixo. Isso exige alterar coletores e fica como trabalho separado.
- Reparar arquivos de cache ou resolver pendências existentes.

## O que não pode acontecer

- Alterar qualquer módulo existente. `python -m backend.crawler.<modulo>` continua igual.
- O painel apagar ou alterar snapshots por conta própria. O acervo tem 21 GB e os originais são imutáveis. Efeitos dos próprios coletores ao rodar de novo são avisados na tela (ver Rodar de novo).
- Sobrecarregar sites oficiais rodando frentes em paralelo.
- Mostrar número inventado. Sem base para um total ou estimativa, a tela diz que é desconhecido.
- Permitir que outro site aberto no navegador dispare coleta pela porta local.

## Estado atual (verificado no código)

- 45 módulos em `ferramentas.json`: 43 executáveis e 2 bibliotecas (`esquemas`, `paginas`). Nenhum executável tem argumento obrigatório.
- `catalogo.py` define `FRONTES`: 41 frentes, nome legível → pasta em `data/`. O grupo mapeado que o painel exibe é a frente.
- `data/catalogo/catalogo.json` traz `snapshots` (com `diretorio` e `origem`) e `cobertura_frentes` (com `snapshots`, `problemas_integridade`, `erros_manifesto_mais_recente`, `status_execucao`, `pendencias_extracao`, `situacao`). Hoje são 7.213 snapshots. 40 frentes têm dados; a 41ª, Auditoria (`catalogo`), tem zero snapshots porque é a própria auditoria.
- 11 frentes têm `situacao = coletada_com_pendencias`, como `reforma-historico` (130 erros, 6 pendências, a maioria Word legado aguardando conversão), `retencoes-defesa-setores` (98 pendências) e `historico-competencias` (25 erros). Rodar de novo não resolve boa parte disso.
- Códigos de saída não indicam pendência de forma uniforme: `notas_cnae` e `obrigacoes_avancadas` saem com 1 quando há pendência; `reforma_historico`, `retencoes_defesa_setores` e `historico_competencias` saem com 0 mesmo com falhas.
- 38 módulos usam `httpx`. Não usam rede: `casos_oficiais`, `catalogo`, `estatisticas`, `recuperar_anexos` (que abre PowerShell), `sumarizacao`.
- 10 módulos usam threads internas, com limites próprios de requisições.
- Em geral, rodar de novo não duplica: conteúdo com o mesmo hash reaproveita a versão.
- Cópia local: módulos sobre `consultas_rfb.cached` (`consultas_rfb`, `reforma_historico`, `retencoes_defesa_setores`, `historico_competencias`, `sumulas_classificacao`) devolvem o arquivo local sem consultar o site. `sped_complementar` só consulta com `--refresh`, e `xmls_exemplo` também reaproveita resultado.
- Período fixo: `cnpj_ampliado`, `cnpj_df` e `cnpj_df_censo` usam 2026-10 por padrão e pulam arquivos brutos presentes; `obrigacoes` usa 2026-11; `economia` termina em 2026-11-03.
- `cached` grava arquivo e recibo sem atomicidade. Encerrar à força entre as duas gravações deixa arquivo sem recibo, e a próxima execução falha nesse caminho.
- `cnpj_ampliado`, ao rodar de novo, reescreve `metadados.json`, `registros.json` e `dados.md` em pasta de snapshot existente.
- Volume alto: `cnpj-ampliado` 6,6 GB, `retencoes-defesa-setores` 5,9 GB, `consultas-rfb` 2,9 GB. `cnpj_df_censo` percorre 195 milhões de linhas.
- Não há histórico de duração das coletas.

## Decidido com o usuário

- **Grupo = frente** de `FRONTES`.
- **Layout A, lista de frentes:** frentes com marcação à esquerda, botão iniciar/parar, indicadores gerais no topo (tempo restante, frentes concluídas, itens coletados) e uma linha por frente à direita.
- **Frente com dados é pulada.** Hoje as 40 coletadas seriam puladas, então rodar qualquer uma delas depende da opção "rodar de novo".
- **"Rodar de novo" reexecuta o módulo como ele é**, sem prometer dados novos. Frentes com cópia local ou período fixo trazem marca na tela.
- **Novo estado "parcial"**, com número de pendências visível. Frente parcial é pulada, a menos que seja marcada.

Aprovado pelo usuário a partir de proposta:

- Cada linha de frente mostra nome e estado (na fila, coletando, concluída, parcial, pulada, com erro, interrompida), barra, contagem "X de Y", site de origem, item atual, horários e tempo restante.
- Sem base para o total, a tela mostra "total desconhecido".
- Comando único, por exemplo `python -m backend.crawler.painel`, que abre a página em endereço local.
- Coletores continuam funcionando sozinhos e não são reescritos.
- Frentes rodam uma por vez. Falha em uma não interrompe as outras, e o erro fica visível.
- Modo sem página, pelo terminal.
- "Rodar de novo" por frente, desligado por padrão. Antes de iniciar, a tela mostra o que roda e o que será pulado. Frentes pesadas trazem aviso.
- Frente pulada aparece como "já coletada", com quantidade de itens e data da última coleta.
- "Já tem dados" significa ao menos uma coleta registrada. Só coleta interrompida ou que quebrou roda de novo sem precisar marcar.
- Parar encerra o script em andamento e não inicia os seguintes. Ao iniciar de novo, o que terminou é pulado.
- Ao fim de cada rodada, o catálogo é atualizado automaticamente.
- Duração e resultado de cada frente ficam salvos fora do Git e alimentam as estimativas.

## Como funciona (decisões do desenho)

### Execução

Cada módulo roda em um processo próprio, como já roda hoje. O executor inicia uma sonda que aplica a instrumentação e chama o módulo com `runpy.run_module('backend.crawler.<modulo>', run_name='__main__')`, com argumentos vazios.

A sonda envolve `httpx.Client.send` (e `AsyncClient.send`, se algum módulo usar). Esse é o ponto por onde passam `get`, `post` e `stream`, incluindo as chamadas feitas por threads. Para cada requisição, registra instante, frente, URL, código de resposta, bytes e duração. Eventos são gravados em JSONL com trava, um arquivo por rodada. Falha da sonda ao gravar não pode derrubar a coleta.

Saída padrão e de erro do módulo vão para um log por frente, mostrado na página ao abrir uma frente com erro. Módulos sem rede só mostram estado e tempo decorrido.

### Ordem

Lista fixa em código, com módulo → frente → dependências → aviso de pesado. Um teste garante que todo módulo executável de `ferramentas.json` e toda frente de `FRONTES` estão nela.

Dependências de dados conhecidas: `cnpj_df` e `cnpj_df_censo` dependem de `cnpj-ampliado`; `fontes_recuperadas` de `documentos-jurisprudencia`; `sumarizacao` do catálogo. O construtor confere o restante lendo o código, incluindo `recuperar_anexos`. Se uma dependência não tem dados, ela entra na seleção e a tela mostra isso antes de iniciar.

`catalogo` não é selecionável e a Auditoria não conta como frente nos indicadores: roda sozinho no fim de cada rodada que executou algo, mesmo depois de Parar, antes das etapas finais. `estatisticas` e `sumarizacao` aparecem como "etapas finais", separadas das frentes e desmarcadas por padrão.

### Resultado de uma execução

A sonda distingue exceção não tratada de saída normal. Depois da rodada, o resultado de cada frente sai do processo e do catálogo atualizado:

- **Interrompida:** Parar, Ctrl+C ou queda, sem linha final no histórico.
- **Com erro:** exceção não tratada, ou saída diferente de zero sem pendência no catálogo.
- **Parcial:** terminou sozinha e a frente tem `situacao = coletada_com_pendencias`, mesmo com saída 1 ou 0. A tela mostra `erros_manifesto_mais_recente + pendencias_extracao`.
- **Concluída:** saída zero, sem pendência.

No modo terminal, o código de saída é 1 só com erro ou interrupção. Parcial é relatada na linha da frente.

### Pular

Uma frente é pulada quando tem `snapshots > 0` em `cobertura_frentes` e sua última execução registrada pelo painel, se houver, não terminou com erro nem interrompida. Pendência não dispara nova execução: a frente aparece como parcial. "Rodar de novo" sobrepõe tudo isso.

### Rodar de novo

Reexecuta o módulo com argumentos vazios. O rótulo não promete dado novo. Na lista fixa, cada módulo tem marca opcional, mostrada na tela:

- "usa cópia local": módulos sobre `cached`, `sped_complementar`, `xmls_exemplo`.
- "período fixo: AAAA-MM": `cnpj_ampliado`, `cnpj_df`, `cnpj_df_censo`, `obrigacoes`, `economia`.
- "reescreve metadados da coleta existente": `cnpj_ampliado`. Exibida no resumo antes de iniciar.

O construtor confere essas marcas lendo cada módulo. O aviso de pesado descreve o que acontece de fato: frente que usa cópia local avisa sobre tempo de leitura, não sobre download.

### Contagem e barra

"Itens" na tela são snapshots do catálogo, a mesma unidade do grupo. A barra usa a melhor base disponível, nesta ordem:

1. Requisições concluídas ÷ requisições da última execução registrada da frente.
2. URLs distintas solicitadas que batem com `origem` dos snapshots da frente (considerando redirecionamento) ÷ total de origens da frente.
3. Sem base: barra indeterminada, com a contagem de requisições e bytes, e o texto "total desconhecido".

Execução sem nenhuma requisição, comum em cópia local, não serve de base 1. A base 1 pode exceder 100% se a fonte cresceu. A tela limita a barra em 99% até o término. Uma frente que termina cedo por usar cache vai direto a concluída. Em downloads grandes, com `Content-Length`, a linha também mostra bytes do arquivo atual.

"Item atual" é a última URL solicitada. A fonte é o domínio dessa URL. Parada, a frente mostra o domínio predominante no catálogo.

### Tempo restante

Soma de cada frente que falta:

- Com histórico: última duração registrada.
- Em andamento, com barra na base 1 ou 2: extrapola do progresso atual.
- Sem histórico: média de segundos por item observada nesta rodada × itens no catálogo, exibida com "~".
- Sem nenhuma base: a frente é excluída da soma e o indicador do topo informa isso, por exemplo "~42 min + 2 frentes sem estimativa".

### Servidor e página

Biblioteca padrão do Python: `http.server` com `ThreadingHTTPServer`, atualização por Server-Sent Events e uma página HTML única sem etapa de build. O crawler não ganha dependência nova. FastAPI existe só em `backend/api`.

- Escuta apenas em `127.0.0.1`.
- Requisições que alteram estado validam `Host` e `Origin`, para bloquear chamadas vindas de outros sites.
- Só uma rodada por vez. Um segundo início recebe recusa.
- Fechar a página não interrompe a coleta. Reabrir retoma a visão atual.
- Encerrar o servidor (Ctrl+C) segue o mesmo fluxo de Parar e marca a frente como interrompida.

### Parar

Em duas etapas, para não cortar uma gravação ao meio:

1. **Parada suave:** o executor sinaliza a sonda, que passa a recusar novas requisições com uma exceção de transporte do `httpx`. A gravação em andamento termina e o módulo encerra por falha de rede, que ele já sabe tratar. A linha mostra "parando".
2. **Parada forçada:** se o processo seguir vivo após o tempo limite (padrão 60 s, constante no código), encerra a árvore de processos, com `taskkill /T` no Windows, porque `recuperar_anexos` abre PowerShell. Em outros sistemas, usa grupo de processos. Módulos sem rede só param assim.

Parada forçada fica registrada na linha da frente e no histórico, com aviso de que pode ter sobrado arquivo de cache sem recibo. O painel não repara nem apaga esse arquivo.

Ao abrir sem coleta em andamento, a página mostra o catálogo existente: 41 frentes com itens, data e estado.

### Dados do painel

Pasta `backend/crawler/.painel/`, adicionada a `backend/crawler/.gitignore`: `historico.jsonl` (uma linha por execução de frente: módulo, início, fim, resultado, requisições, bytes) e `rodadas/<id>/` (eventos e logs). Fica fora de `data/` para não entrar em catálogo nem estatísticas, sem alterar esses módulos.

Rodada interrompida por queda da máquina é reconhecida ao iniciar: sem linha final no histórico, conta como interrompida.

### Terminal

`python -m backend.crawler.painel` inicia o servidor e abre o navegador. Em modo terminal, por exemplo `--sem-pagina --frentes cnae,mei --rodar-de-novo`, usa o mesmo executor, com uma linha por frente.

## Testes

Seguem `backend/crawler/tests`, com `pytest` e `httpx.MockTransport`, sem rede:

- Decisão de pular em cada caso: com dados, sem dados, com pendência, interrompida, com erro, rodar de novo.
- Classificação do resultado: saídas 0 e 1 com e sem pendência, exceção não tratada, interrupção.
- Cobertura da lista fixa contra `ferramentas.json` e `FRONTES`.
- Cálculo da barra nas três bases e o limite de 99%.
- Estimativa de tempo com e sem histórico.
- Sonda: registra eventos, propaga exceções do módulo, não derruba o módulo se a gravação falhar.
- Parar: sonda recusa novas requisições; módulo falso que ignora o sinal é encerrado com seu processo filho após o tempo limite e registrado como parada forçada.
- Bloqueio de `Origin` externa.

## A cargo do construtor

- Organização de arquivos e rotas. Preferir poucos arquivos.
- Visual da página dentro do layout A, em português, usável por teclado e com bom contraste.
- Quais frentes levam o aviso de pesado: no mínimo `cnpj-ampliado`, `cnpj-df`, `cnpj-df-censo`, `retencoes-defesa-setores`, `consultas-rfb`, `historico-competencias` e `consultas-df-amplas`.
- Documentar o comando em `backend/crawler/README.md` e registrar o painel em `ferramentas.json` e `FERRAMENTAS.md`.
