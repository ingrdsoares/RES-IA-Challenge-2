# Backend inicial de RAG — Sócio Digital

Status: aprovado pelo usuário em 2026-11-05. Trabalho na branch `feat/backend-rag-qwen-qdrant`.

## Intenção e escopo acordado

Preparar o monorepo para backend e frontend e entregar uma API de RAG integrada ao Qdrant. O trabalho atual se concentra no backend. O usuário alimentará o banco posteriormente; esta entrega não inclui ingestão, documentos de exemplo, carga inicial nem endpoints de escrita de documentos.

O repositório contém uma API FastAPI em `api/`, com `/health`, Dockerfile e um teste. A solicitação é colocar essa API dentro de `backend/`, preservando a estrutura interna em `backend/api/`.

O usuário escolheu Qwen3 Embedding e Qwen3 para geração. A máquina alvo é um MacBook M4 com 24 GB de memória. A proposta técnica é `qwen3-embedding:0.6b` e `qwen3:8b`, servidos pelo Ollama instalado diretamente no macOS, aproveitando a GPU. Qdrant e API serão executados por Docker Compose.

## Abordagens consideradas

1. Embeddings e geração via OpenAI: simplifica a execução local dos modelos, mas depende de API externa, créditos e internet.
2. Embeddings locais e geração por API: reduz a dependência externa para indexação, mas exige operar os dois tipos de integração.
3. Embeddings e geração com Qwen via Ollama: escolha do usuário para as famílias de modelos; execução local via Ollama é a proposta técnica. Exige memória e download inicial, mas permite consultas sem API paga.

## Organização proposta

- `backend/api/`: aplicação FastAPI, Dockerfile, dependências e testes existentes, acrescidos dos componentes do RAG.
- `backend/compose.yaml`: serviços API e Qdrant, com volume nomeado para dados vetoriais e portas vinculadas ao localhost para uso local.
- `backend/.env.example`: configuração documentada sem segredos.
- `backend/README.md`: execução, configuração, contrato de indexação futura e exemplos de consulta.
- README principal atualizado para indicar o backend. A documentação Docsify existente continua na raiz; o desenvolvimento do frontend fica para outra entrega.

Dentro da aplicação, separar rotas e schemas, configuração, orquestração do RAG, integração com Ollama e integração com Qdrant. Usar SDKs oficiais, sem framework de agentes neste fluxo inicial.

## Consulta e contrato HTTP propostos

- `GET /health`: preserva `{"status": "ok"}` como verificação do processo.
- `GET /ready`: verifica conectividade com Qdrant, compatibilidade da coleção e disponibilidade dos dois modelos no Ollama. Coleção vazia é um estado válido. Dependências indisponíveis ou coleção incompatível retornam 503.
- `POST /rag/query`: recebe `question`, texto não vazio com limite documentado; retorna `status`, `answer` e `sources`. Consulta sem histórico de conversa e sem streaming nesta entrega.

Fluxo:

1. Verificar se a coleção possui documentos. Se estiver vazia, responder HTTP 200 com `status: "empty_knowledge_base"`, mensagem explicativa e fontes vazias, sem chamar os modelos.
2. Gerar o embedding da pergunta com a instrução de recuperação recomendada para Qwen3 Embedding.
3. Recuperar até cinco trechos no Qdrant por similaridade de cosseno, com limite configurável e máximo imposto pela API.
4. Aplicar limiar de similaridade configurável. Não havendo trechos elegíveis, retornar `status: "insufficient_context"`, mensagem explicativa e fontes vazias, sem geração.
5. Enviar os trechos elegíveis ao Qwen3 com instruções para responder em português a partir desse contexto e citar os identificadores fornecidos. Tratar o conteúdo recuperado como dados, sem executar instruções presentes nos documentos.
6. Retornar `status: "answered"`, resposta e referências dos trechos usados como contexto. A lista identifica o contexto enviado e não constitui verificação automática de todas as afirmações do modelo.

O prompt exige indicação de insuficiência quando o contexto não sustentar uma resposta. Isso é uma instrução ao modelo, sem promessa de eliminar alucinações. Começar com contexto de 8.192 tokens, geração sem thinking e orçamento limitado para a resposta; truncar ou selecionar os trechos antes da geração para respeitar esse orçamento.

Qdrant/Ollama indisponíveis, modelo ausente e timeout devem produzir erros claros e limitados, sem expor detalhes internos. Não substituir falhas por respostas inventadas. A API poderá iniciar com dependências indisponíveis, mantendo `/health` acessível; readiness e consulta refletirão a falha.

## Coleção e alimentação futura

Criar, de forma idempotente, uma coleção vazia configurável, com nome padrão `knowledge_base`, vetores densos sem nome, 1.024 dimensões e distância de cosseno. Não apagar nem recriar coleções existentes. Se uma coleção existente tiver configuração incompatível, reportar o erro. Inicialização pode ser tentada novamente após recuperação do Qdrant.

Contrato dos pontos que o usuário inserirá posteriormente:

- ID aceito pelo Qdrant: inteiro sem sinal ou UUID.
- Vetor gerado por `qwen3-embedding:0.6b`, com 1.024 dimensões, usando o texto do trecho sem o prefixo de instrução reservado às perguntas.
- Payload obrigatório: `text` (trecho não vazio) e `source` (URL ou referência documental não vazia).
- Payload opcional: `title`, `document_id`, `chunk_id`, `reference_date` e `effective_date`, datas em ISO 8601 quando conhecidas.

A resposta inclui ID do ponto, texto, referência, score e metadados presentes. Pontos com payload inválido não serão usados como contexto; registrar a ocorrência e tratar a ausência de pontos utilizáveis como contexto insuficiente. O README explicará que trocar modelo de embedding exige reindexar os documentos, mesmo quando a dimensão for a mesma. Nenhuma rotina de indexação será implementada agora.

## Execução local

Instalar Ollama no macOS e baixar explicitamente os dois modelos como preparação manual documentada. Não realizar downloads de modelos no startup da API. O Compose executa Qdrant com persistência e a API; a API acessa Ollama pelo endereço configurável `http://host.docker.internal:11434` e Qdrant pela rede do Compose. Documentar configuração de acesso do Ollama a partir do Docker Desktop e alternativa de execução da API diretamente no host.

Fixar uma versão explícita da imagem Qdrant e versões compatíveis das dependências na implementação, após consulta à documentação oficial. Configurar modelos, URLs, coleção, dimensão, top-k, limiar e timeouts por ambiente, validando limites. Recursos do macOS são compartilhados com Docker; latência será medida quando os modelos estiverem disponíveis.

## Fora desta entrega

Frontend, crawler, chunking e ingestão, carga demonstrativa ou definitiva, autenticação, multitenancy, histórico persistido, motor de cálculo tributário e deploy público. A API inicial opera sobre uma base documental compartilhada para demonstração local.

## Verificação e limites da entrega

- Preservar o teste de `/health` após a mudança de diretório.
- Testar validação de entrada, base vazia, contexto insuficiente, erros de dependências e consulta completa com clientes substituídos por doubles controlados.
- Verificar persistência e consulta contra Qdrant real, usando uma coleção temporária de teste com limpeza restrita a ela; não inserir nada na coleção da aplicação.
- Validar o Compose e, quando Docker estiver disponível, a inicialização dos serviços.
- Testar geração real apenas se Ollama e os modelos já estiverem disponíveis; registrar explicitamente o que foi executado. Sem documentos na coleção da aplicação, a entrega comprova a integração e o comportamento de base vazia; respostas reais fundamentadas dependem da alimentação posterior pelo usuário.

## Decisões deixadas à implementação

Nomes de módulos, limites exatos de texto e orçamento de tokens, valor inicial do limiar (documentado como provisório, sujeito a avaliação com o corpus), política limitada de retries, versões fixadas e organização dos testes. Os contratos e escolhas acima são propostas do assistente quando não expressamente atribuídos ao usuário e aguardam aprovação deste documento.
