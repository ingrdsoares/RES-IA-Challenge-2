"""Gera os PDFs "Planejamento de Etapas" (um por etapa), com o conteudo dividido em issues.

Uso (na raiz do repositorio):
    python scripts/generate_planejamento_etapas_pdf.py
Saida: docs/projeto/planejamento-etapas/planejamento-de-etapas-<n>-<slug>.pdf
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "projeto" / "planejamento-etapas"
AZUL = colors.HexColor("#1d4ed8")
CINZA = colors.HexColor("#475569")
FUNDO = colors.HexColor("#eff6ff")

ETAPAS = [
    {
        "n": 1,
        "slug": "unificar-o-nucleo",
        "titulo": "Unificar o núcleo",
        "objetivo": (
            "Ligar o RAG (backend/api) ao motor fiscal determinístico (src/fiscal) e criar o modelo "
            "de dados da empresa. Ao final, a API responde com base na lei e no cálculo, a partir do "
            "perfil da empresa, em um plano de 3 passos (RF01, RF03, RF07)."
        ),
        "contexto": (
            "Hoje o repositório tem duas pilhas paralelas: src/ (RAG antigo em SQLite e motor fiscal) e "
            "backend/api/ (RAG novo com Qdrant e Ollama). O motor fiscal tem testes, mas não é "
            "exposto pela API, e não existe cadastro de empresa."
        ),
        "saida": "API única com endpoints fiscais, perfil da empresa persistido e assistente que combina norma e cálculo.",
        "issues": [
            {
                "t": "Migrar o motor fiscal de src/fiscal para backend",
                "l": "etapa-1, backend, refactor",
                "p": "Alta",
                "d": "Mover calculator, models, repository e ingest de src/fiscal para um pacote dentro de backend/, mantendo as tabelas do Simples (30 faixas) e a base de CNAEs. Ajustar imports, o CI e os testes de raiz (test_fiscal.py).",
                "c": [
                    "Código fiscal fica em backend/, sem importar de src/",
                    "Testes do cálculo migrados e passando no CI",
                    "Dados de tabelas e CNAEs carregáveis por comando documentado",
                ],
                "dep": "Nenhuma",
            },
            {
                "t": "Endpoint POST /fiscal/simular",
                "l": "etapa-1, backend, feature",
                "p": "Alta",
                "d": "Expor o cálculo do Simples Nacional: recebe RBT12, CNAE e folha (opcional) e devolve alíquota efetiva, anexo aplicado, Fator R, tributos segregados e alerta de desenquadramento do MEI (limite de faturamento).",
                "c": [
                    "Schemas de entrada e saída validados (422 em dados inválidos)",
                    "Resultado idêntico ao do calculator nos casos de teste existentes",
                    "Documentado no Swagger com exemplos",
                    "Testes de API cobrindo MEI, Fator R acima e abaixo de 28% e CNAE inexistente",
                ],
                "dep": "Migrar o motor fiscal",
            },
            {
                "t": "Modelo de dados do perfil da empresa (PostgreSQL)",
                "l": "etapa-1, backend, dados",
                "p": "Alta",
                "d": "Criar o esquema da empresa: CNPJ, CNAE principal, município/UF, porte, regime e enquadramento, faturamento e folha. Cada campo registra a origem (informado pelo usuário ou consultado) e a data. Reaproveitar o que for útil do contrato SQL do refino.",
                "c": [
                    "Migrações versionadas (ex.: Alembic)",
                    "Campo de origem por dado, como no wireframe da tela 02",
                    "Compose com o serviço de banco para desenvolvimento",
                ],
                "dep": "Nenhuma",
            },
            {
                "t": "API de cadastro e consulta da empresa",
                "l": "etapa-1, backend, feature",
                "p": "Alta",
                "d": "Endpoints para criar, ler e atualizar o perfil da empresa, com validação de CNPJ e de CNAE contra a base. Preparar o vínculo com o usuário para a etapa 3.",
                "c": [
                    "CRUD funcional com validação de CNPJ (dígitos verificadores)",
                    "Erros por campo, como previsto no wireframe",
                    "Testes automatizados",
                ],
                "dep": "Modelo de dados do perfil",
            },
            {
                "t": "Consulta de CNPJ com preenchimento manual como alternativa",
                "l": "etapa-1, backend, integração",
                "p": "Média",
                "d": "Integrar uma fonte pública de consulta de CNPJ para pré-preencher o cadastro. Se a consulta estiver indisponível ou falhar, o fluxo manual continua funcionando. Verificar termos de uso e limites da fonte escolhida antes de integrar.",
                "c": [
                    "Retorno exibido para conferência, com origem marcada",
                    "Timeout e erro tratados sem bloquear o cadastro",
                    "Fonte e limites documentados",
                ],
                "dep": "API de cadastro da empresa",
            },
            {
                "t": "Orquestrar RAG e cálculo no assistente (plano em 3 passos)",
                "l": "etapa-1, backend, ia",
                "p": "Alta",
                "d": "Estender /rag/query (ou criar /assistente/consultar) para receber o perfil da empresa, detectar quando há cálculo a fazer, chamar o motor fiscal e montar a resposta com norma citada, resultado do cálculo e plano em 3 etapas (RF07). Reaproveitar o extrator de entidades de src/rag.",
                "c": [
                    "Resposta separa claramente o que vem da norma e o que vem do cálculo",
                    "Números nunca são gerados pelo modelo: vêm do motor fiscal",
                    "Plano em 3 passos presente quando aplicável",
                    "Casos com e sem perfil de empresa testados",
                ],
                "dep": "Endpoint /fiscal/simular; API de cadastro da empresa",
            },
            {
                "t": "Aposentar src/rag e consolidar os testes da raiz",
                "l": "etapa-1, refactor, dívida-técnica",
                "p": "Média",
                "d": "Portar para backend/ o que ainda vale do RAG antigo (extrator de entidades, prompts e testes de governança) e remover src/rag, o SQLite vetorial e os test_*.py soltos na raiz. Atualizar a documentação em docs/projeto/status-entregas-equipe.md.",
                "c": [
                    "Nenhum código ativo depende de src/rag",
                    "Cenários de governança e abstenção preservados como testes do backend",
                    "README e documentação atualizados",
                ],
                "dep": "Orquestração do assistente",
            },
            {
                "t": "Contrato de API versionado (OpenAPI) e padrão de erros",
                "l": "etapa-1, backend, arquitetura",
                "p": "Alta",
                "d": "Definir o contrato dos serviços antes que o frontend dependa deles: prefixo e versionamento (/v1), formato único de erro, códigos HTTP, paginação e campos comuns. O contrato dos endpoints fiscais, de empresa e do assistente deve ser revisado por ele antes da implementação e mantido no OpenAPI.",
                "c": [
                    "Guia de contrato publicado no repositório",
                    "Formato de erro único adotado pelos endpoints novos",
                    "Mudança incompatível exige nova versão, com regra registrada",
                    "Revisão do contrato dos endpoints da etapa 1 concluída",
                ],
                "dep": "Nenhuma (deve ser feita antes ou junto de E1.2 e E1.4)",
            },
        ],
    },
    {
        "n": 2,
        "slug": "confiabilidade-do-rag",
        "titulo": "Confiabilidade do RAG",
        "objetivo": (
            "Tornar a qualidade das respostas verificável por terceiros e adequada para uso real: "
            "gabarito revisado, casos críticos corrigidos, proteções em produção e suporte a vários "
            "usuários ao mesmo tempo."
        ),
        "contexto": (
            "A avaliação de 07/11/2026 mostra 17 de 20 perguntas novas corretas ou com recusa adequada. "
            "A classificação é preliminar: foi feita pela equipe que escreveu as perguntas, e q07, q13 e "
            "q20 ainda erram. A API atende uma consulta por vez por processo e não tem streaming."
        ),
        "saida": "Resultado de qualidade validado de forma independente, guardrails ativos e API pronta para uso simultâneo.",
        "issues": [
            {
                "t": "Revisão independente do gabarito de avaliação",
                "l": "etapa-2, avaliação, qualidade",
                "p": "Alta",
                "d": "Obter a revisão de uma pessoa que não escreveu as perguntas, preferencialmente com formação contábil/fiscal, sobre as perguntas, as referências e a classificação das respostas (correta, parcial, errada, recusa). Registrar divergências e quem revisou.",
                "c": [
                    "Todas as perguntas do teste novo revisadas",
                    "Divergências registradas e resolvidas no gabarito",
                    "Relatório atualizado indicando que a classificação foi revisada e por quem",
                ],
                "dep": "Nenhuma",
            },
            {
                "t": "Congelar um conjunto de teste separado dos ajustes",
                "l": "etapa-2, avaliação",
                "p": "Alta",
                "d": "Separar um conjunto de validação que não será usado para ajustar prompts e parâmetros, versionado com hash. As 25 perguntas de desenvolvimento ficam só para ajuste.",
                "c": [
                    "Conjunto congelado versionado e documentado",
                    "Regra no README de avaliação: não ajustar olhando este conjunto",
                    "Comando único que reproduz a medição",
                ],
                "dep": "Revisão independente do gabarito",
            },
            {
                "t": "Corrigir as respostas de q07, q13 e q20",
                "l": "etapa-2, ia, bug",
                "p": "Alta",
                "d": "q13 não cita o efeito retroativo do desenquadramento; q20 abre negando a continuidade do tratamento simplificado; q21 explica pior a não cumulatividade. Investigar recuperação, prompt e acervo e corrigir sem regredir as demais.",
                "c": [
                    "Causa de cada erro identificada e registrada",
                    "As três respostas corrigidas ou a lacuna do acervo documentada",
                    "Nenhuma pergunta do conjunto de desenvolvimento piora",
                ],
                "dep": "Nenhuma",
            },
            {
                "t": "Guardrails em produção: aviso do CRC, fraude e abstenção",
                "l": "etapa-2, ia, segurança",
                "p": "Alta",
                "d": "Garantir que toda resposta traga o aviso de que o produto não substitui contador, que pedidos de evasão ou fraude sejam recusados e que a falta de base resulte em abstenção. Portar os cenários de governança de src/rag para o backend atual.",
                "c": [
                    "Aviso presente em toda resposta fiscal",
                    "Casos de fraude e de falta de base cobertos por testes",
                    "Texto do aviso validado por quem responde pela fronteira ética (CRC/LGPD)",
                ],
                "dep": "Nenhuma",
            },
            {
                "t": "Streaming da resposta",
                "l": "etapa-2, backend, feature",
                "p": "Média",
                "d": "Entregar a resposta em fluxo (SSE ou equivalente) para reduzir a espera percebida. As fontes e o status devem chegar de forma consistente com a resposta completa.",
                "c": [
                    "Endpoint de streaming documentado",
                    "Fontes enviadas ao final ou no início, de forma definida",
                    "Erros no meio do fluxo tratados e sinalizados ao cliente",
                ],
                "dep": "Nenhuma",
            },
            {
                "t": "Atender consultas simultâneas",
                "l": "etapa-2, backend, desempenho",
                "p": "Alta",
                "d": "Hoje pedidos simultâneos recebem 503 e a execução exige um único worker. Introduzir fila ou limite de concorrência controlado e medir o impacto no Ollama ou no serviço de LLM escolhido.",
                "c": [
                    "Duas ou mais consultas simultâneas concluem sem 503 dentro do limite definido",
                    "Limite e comportamento de fila documentados",
                    "Teste de concorrência automatizado",
                ],
                "dep": "Decisão de hospedagem do LLM (etapa 4) influencia o limite",
            },
            {
                "t": "Rodar a medição de qualidade no CI",
                "l": "etapa-2, ci, avaliação",
                "p": "Média",
                "d": "Executar uma verificação de qualidade (conjunto reduzido e determinístico) a cada mudança em prompts, recuperação ou acervo, falhando o CI se houver queda além de um limite acordado.",
                "c": [
                    "Job de qualidade no workflow",
                    "Limite de regressão definido e documentado",
                    "Relatório anexado à execução",
                ],
                "dep": "Conjunto de teste congelado",
            },
            {
                "t": "Testes adversariais: injeção de prompt e vazamento de contexto",
                "l": "etapa-2, segurança, ia",
                "p": "Alta",
                "d": "Criar um conjunto de ataques ao assistente: instruções escondidas em perguntas, pedidos para ignorar regras, tentativa de obter o prompt do sistema ou dados de outra empresa, e conteúdo malicioso vindo de documentos do acervo. Medir e corrigir as falhas.",
                "c": [
                    "Conjunto de ataques versionado, com resultado esperado por caso",
                    "Falhas encontradas registradas e corrigidas ou aceitas com justificativa",
                    "Execução automatizada, de preferência no CI",
                ],
                "dep": "Guardrails em produção",
            },
        ],
    },
    {
        "n": 3,
        "slug": "aplicacao-frontend",
        "titulo": "Aplicação (frontend e conta de usuário)",
        "objetivo": (
            "Construir a interface do MVP seguindo o mapa de telas, de modo que a empresa se cadastre, "
            "converse com o assistente fiscal, acompanhe tarefas e consulte as normas."
        ),
        "contexto": (
            "Não existe frontend além do protótipo HTML. O diagrama do MVP define 8 telas: Acesso, "
            "Cadastro da empresa, Visão geral, Assistente fiscal, Situação fiscal, Tarefas, Perfil da "
            "empresa e Biblioteca de normas. O método de autenticação ainda está em aberto."
        ),
        "saida": "Aplicação web navegável de ponta a ponta, consumindo a API, com acesso por conta.",
        "issues": [
            {
                "t": "Decidir stack do frontend e método de autenticação (ADR)",
                "l": "etapa-3, decisão, arquitetura",
                "p": "Alta",
                "d": "Registrar em um documento de decisão a stack (sugestão a avaliar: React ou Next.js), o método de autenticação (e-mail e senha, login social ou provedor externo) e como o token chega à API. Definir também quem será responsável pelo frontend.",
                "c": [
                    "Decisão registrada com alternativas e justificativa",
                    "Responsável do frontend nomeado",
                    "Impacto na API (CORS, sessão, tokens) listado",
                ],
                "dep": "Nenhuma",
            },
            {
                "t": "Estrutura inicial do frontend e cliente da API",
                "l": "etapa-3, frontend, infra",
                "p": "Alta",
                "d": "Criar o projeto do frontend, rotas das 8 telas, navegação, tema e um cliente tipado gerado a partir do OpenAPI da API. Incluir lint, testes e build no CI.",
                "c": [
                    "Aplicação sobe localmente com um comando",
                    "Cliente da API gerado do OpenAPI",
                    "Pipeline de lint, teste e build no CI",
                ],
                "dep": "ADR de stack",
            },
            {
                "t": "Autenticação e tela de Acesso (01)",
                "l": "etapa-3, frontend, backend, segurança",
                "p": "Alta",
                "d": "Implementar login conforme a decisão do ADR, sessão com permissões da conta, redirecionamento (com empresa para a Visão geral; sem empresa para o Cadastro), erros junto ao formulário e estado de envio.",
                "c": [
                    "Rotas da API protegidas por autenticação",
                    "Redirecionamento conforme existência de empresa",
                    "Falhas de acesso exibidas no formulário, com nova tentativa",
                ],
                "dep": "ADR; API de cadastro da empresa",
            },
            {
                "t": "Tela de Cadastro da empresa (02)",
                "l": "etapa-3, frontend, feature",
                "p": "Alta",
                "d": "Formulário de CNPJ com consulta, conferência dos dados, CNAE, município/UF, porte e regime, com marcação de origem de cada campo e preenchimento manual se a consulta falhar.",
                "c": [
                    "Validação de campos com mensagens por campo",
                    "Origem do dado visível (usuário ou consulta)",
                    "Salvar leva à Visão geral",
                ],
                "dep": "API de cadastro da empresa; consulta de CNPJ",
            },
            {
                "t": "Tela do Assistente fiscal (04)",
                "l": "etapa-3, frontend, feature",
                "p": "Alta",
                "d": "Conversa com o assistente, confirmação do contexto da empresa, exibição do plano em 3 passos, das fontes citadas e do aviso de que não substitui contador. Consumir o streaming quando disponível.",
                "c": [
                    "Respostas exibidas com citações clicáveis",
                    "Estados de base vazia, contexto insuficiente e erro tratados",
                    "Aviso legal sempre visível nas respostas fiscais",
                ],
                "dep": "Orquestração do assistente; streaming (desejável)",
            },
            {
                "t": "Tela de Visão geral (03)",
                "l": "etapa-3, frontend, feature",
                "p": "Média",
                "d": "Resumo da empresa, indicadores fiscais (alíquota efetiva, regime, Fator R) e próximas ações, usando o endpoint de simulação e o perfil.",
                "c": [
                    "Indicadores calculados pela API, não pelo frontend",
                    "Estado vazio quando faltam dados da empresa",
                ],
                "dep": "Endpoint /fiscal/simular; cadastro da empresa",
            },
            {
                "t": "Tarefas (06): modelo, API e tela",
                "l": "etapa-3, frontend, backend, feature",
                "p": "Média",
                "d": "Persistir as ações recomendadas pelo assistente como tarefas da empresa (pendente, concluída), permitindo registrar a conclusão. Definir quando uma recomendação vira tarefa.",
                "c": [
                    "Tarefas vinculadas à empresa e ao plano de origem",
                    "Marcar e desmarcar conclusão, com data",
                    "Testes de API e de tela",
                ],
                "dep": "Orquestração do assistente; autenticação",
            },
            {
                "t": "Perfil da empresa (07)",
                "l": "etapa-3, frontend, feature",
                "p": "Baixa",
                "d": "Tela para revisar e editar os dados da empresa, mostrando a origem e a data de cada um, e recalculando indicadores ao salvar.",
                "c": ["Edição com validação", "Origem e data de cada dado visíveis"],
                "dep": "Tela de Cadastro da empresa",
            },
            {
                "t": "Situação fiscal (05)",
                "l": "etapa-3, frontend, backend, feature",
                "p": "Baixa",
                "d": "Indicadores, consultas e evidências da situação fiscal. Definir antes quais consultas públicas entram no MVP (o acervo contém regularização Receita/PGFN) e como as evidências são apresentadas.",
                "c": [
                    "Escopo de consultas do MVP definido",
                    "Evidências com fonte e data",
                    "Limites de cobertura informados ao usuário",
                ],
                "dep": "Cadastro da empresa; definição de escopo",
            },
            {
                "t": "Biblioteca de normas (08)",
                "l": "etapa-3, frontend, backend, feature",
                "p": "Média",
                "d": "Navegação de leis e normas por assunto, reaproveitando o acervo e seus metadados. Exige endpoints de listagem e leitura de documentos, hoje inexistentes na API.",
                "c": [
                    "Endpoints de listagem por assunto e de leitura de norma",
                    "Texto exibido com fonte oficial e versão",
                    "Busca por assunto ou número da norma",
                ],
                "dep": "Estrutura do frontend",
            },
            {
                "t": "Autorização e isolamento de dados entre empresas",
                "l": "etapa-3, backend, segurança, arquitetura",
                "p": "Alta",
                "d": "Definir e implementar o modelo de permissões: cada usuário só acessa a(s) própria(s) empresa(s), em todos os endpoints e no contexto enviado ao assistente. Decidir se uma conta pode ter mais de uma empresa e se há papéis (dono, contador convidado).",
                "c": [
                    "Regra de acesso definida e documentada",
                    "Toda consulta ao banco filtrada pela empresa do usuário",
                    "Testes provando que uma conta não lê dados de outra",
                    "Contexto do assistente montado só com dados da empresa autorizada",
                ],
                "dep": "Autenticação; modelo de dados do perfil da empresa",
            },
            {
                "t": "Atualizar o diagrama de arquitetura com os serviços reais",
                "l": "etapa-3, documentação, arquitetura",
                "p": "Média",
                "d": "O diagrama atual (docs/arquitetura/diagramas) é alvo de projeto. Atualizá-lo com o que for decidido e construído: frontend, API única, PostgreSQL, Qdrant, serviço de LLM, autenticação e fluxo de dados do assistente, marcando o que cruza a fronteira ética e de LGPD.",
                "c": [
                    "Arquivo editável (.excalidraw) e imagem atualizados",
                    "Fronteiras de confiança e fluxo de dados pessoais indicados",
                    "Documento arquitetura.md refletindo o diagrama",
                ],
                "dep": "ADR de stack e autenticação; decisão de hospedagem do LLM",
            },
        ],
    },
    {
        "n": 4,
        "slug": "producao",
        "titulo": "Produção",
        "objetivo": (
            "Colocar o sistema no ar de forma segura, observável e reproduzível, com decisões claras de "
            "hospedagem, conformidade com a LGPD e rotina de atualização do acervo."
        ),
        "contexto": (
            "O Compose atual serve só ao ambiente local, com Ollama no host. O modelo de geração (Qwen3 8B) "
            "exige GPU para atender usuários reais. O CI faz lint e pytest. As normas mudam (por exemplo, "
            "a alíquota geral do ICMS-DF mudou em 2024), então o acervo precisa de atualização contínua."
        ),
        "saida": "Ambientes de teste e produção com deploy automatizado, segurança, monitoramento e plano de atualização e recuperação.",
        "issues": [
            {
                "t": "Decidir a hospedagem do LLM e do embedding (ADR com custo)",
                "l": "etapa-4, decisão, infra",
                "p": "Alta",
                "d": "Comparar servidor próprio com GPU, serviço gerenciado e API de LLM de terceiros quanto a custo mensal, latência, privacidade dos dados da empresa e esforço. É a decisão que mais impacta a arquitetura, e deve ser tomada cedo.",
                "c": [
                    "Quadro comparativo com custo estimado e latência medida",
                    "Decisão registrada e aprovada pela equipe",
                    "Impacto na API e na concorrência listado",
                ],
                "dep": "Nenhuma",
            },
            {
                "t": "Containerização completa e Compose de produção",
                "l": "etapa-4, infra, devops",
                "p": "Alta",
                "d": "Imagens para API e frontend, serviços de Qdrant e PostgreSQL com volumes e backup, variáveis por ambiente e healthchecks. Remover a dependência de host.docker.internal para o modelo.",
                "c": [
                    "Todo o sistema sobe com um comando em ambiente limpo",
                    "Configuração por variáveis, sem segredos no repositório",
                    "Documentação de execução atualizada",
                ],
                "dep": "Decisão de hospedagem do LLM",
            },
            {
                "t": "CI: build de imagens e testes de integração com Qdrant",
                "l": "etapa-4, ci, devops",
                "p": "Alta",
                "d": "Ampliar o CI com build das imagens, execução de testes de integração com Qdrant e Postgres em serviço e cache de dependências.",
                "c": [
                    "Imagens construídas a cada PR",
                    "Testes de integração rodando no CI",
                    "Tempo total do CI monitorado",
                ],
                "dep": "Containerização completa",
            },
            {
                "t": "CD: deploy automatizado em staging e produção",
                "l": "etapa-4, cd, devops",
                "p": "Alta",
                "d": "Pipeline que publica imagens versionadas, implanta em staging a cada merge na main e em produção por aprovação, com forma de reverter.",
                "c": [
                    "Deploy em staging automático",
                    "Produção com aprovação manual e reversão documentada",
                    "Versão implantada visível na API",
                ],
                "dep": "CI de build de imagens",
            },
            {
                "t": "Segurança da API: limite de uso, segredos, CORS e cabeçalhos",
                "l": "etapa-4, segurança, backend",
                "p": "Alta",
                "d": "Limitar requisições por usuário e por IP, gerenciar segredos fora do repositório, restringir CORS ao frontend, validar entradas e proteger contra abuso do endpoint de IA, que é caro de executar.",
                "c": [
                    "Limite de requisições com resposta 429",
                    "Segredos em gerenciador, nunca no código",
                    "Revisão de segurança (checklist) registrada",
                ],
                "dep": "Autenticação",
            },
            {
                "t": "Conformidade com a LGPD",
                "l": "etapa-4, lgpd, segurança",
                "p": "Alta",
                "d": "CNPJ, faturamento e folha são dados da empresa e, em MEI, podem identificar uma pessoa. Definir base legal, política de privacidade, retenção, exclusão de conta e dados, e que dados chegam aos logs e a provedores externos de LLM.",
                "c": [
                    "Política de privacidade e termos redigidos",
                    "Fluxo de exclusão de conta e dados implementado",
                    "Logs sem dados sensíveis, verificado por teste",
                    "Registro do que é enviado a serviços de terceiros",
                ],
                "dep": "Decisão de hospedagem do LLM",
            },
            {
                "t": "Observabilidade: logs, métricas e alertas",
                "l": "etapa-4, observabilidade, devops",
                "p": "Média",
                "d": "Logs estruturados com identificador de requisição; métricas de latência por etapa (busca, geração), taxa de abstenção, erros e uso de GPU; alertas para indisponibilidade de Qdrant ou do modelo.",
                "c": [
                    "Painel com latência, erros e abstenção",
                    "Alertas de indisponibilidade configurados",
                    "Identificador de requisição ligando logs e resposta",
                ],
                "dep": "Containerização completa",
            },
            {
                "t": "Feedback do usuário por resposta",
                "l": "etapa-4, produto, backend",
                "p": "Média",
                "d": "Permitir marcar uma resposta como útil ou incorreta, com comentário opcional, ligada à pergunta, às fontes e à versão do acervo e do modelo, para alimentar a revisão de qualidade.",
                "c": [
                    "Feedback persistido sem dados pessoais desnecessários",
                    "Relatório periódico de respostas marcadas como incorretas",
                ],
                "dep": "Tela do Assistente fiscal; LGPD",
            },
            {
                "t": "Pipeline de atualização do acervo",
                "l": "etapa-4, dados, devops",
                "p": "Média",
                "d": "Rotina periódica para recoletar fontes, detectar normas alteradas, reprocessar o refino, reindexar no Qdrant e reavaliar a qualidade antes de promover a nova coleção. Manter a coleção anterior para voltar atrás.",
                "c": [
                    "Execução agendada e reproduzível",
                    "Alterações detectadas com relatório",
                    "Promoção só após a medição de qualidade passar",
                    "Reversão para a coleção anterior documentada",
                ],
                "dep": "Medição de qualidade no CI",
            },
            {
                "t": "Backup e restauração de Qdrant e PostgreSQL",
                "l": "etapa-4, infra, confiabilidade",
                "p": "Média",
                "d": "Rotina de backup dos dados do usuário e da coleção, com teste de restauração. O README atual já alerta para não remover o volume do Qdrant.",
                "c": [
                    "Backups automáticos com retenção definida",
                    "Restauração testada em ambiente separado",
                ],
                "dep": "Containerização completa",
            },
            {
                "t": "Teste de carga e dimensionamento",
                "l": "etapa-4, desempenho, qualidade",
                "p": "Média",
                "d": "Simular usuários simultâneos no assistente para medir latência, taxa de erro e consumo, e definir o tamanho da infraestrutura e o número esperado de usuários no lançamento.",
                "c": [
                    "Cenários de carga versionados",
                    "Limites medidos e registrados",
                    "Meta de capacidade do lançamento definida",
                ],
                "dep": "Consultas simultâneas; hospedagem definida",
            },
            {
                "t": "Modelagem de ameaças do sistema",
                "l": "etapa-4, segurança, arquitetura",
                "p": "Alta",
                "d": "Mapear ativos (dados da empresa, acervo, chaves), pontos de entrada, fronteiras de confiança e ameaças (por exemplo, método STRIDE), com a mitigação e o responsável de cada risco. Cobre ainda a cadeia do acervo: um documento coletado alterado pode envenenar as respostas.",
                "c": [
                    "Documento de ameaças com severidade e mitigação por item",
                    "Riscos altos viram issues com responsável",
                    "Revisão antes do lançamento",
                ],
                "dep": "Diagrama de arquitetura atualizado",
            },
            {
                "t": "Plano de resposta a incidentes e de continuidade",
                "l": "etapa-4, segurança, operação",
                "p": "Média",
                "d": "Definir o que fazer se houver vazamento de dados, resposta fiscal errada com impacto, indisponibilidade do modelo ou acervo corrompido: quem decide, como comunicar usuários, como desligar o assistente de forma segura e como voltar à coleção anterior.",
                "c": [
                    "Procedimentos escritos por tipo de incidente",
                    "Contatos e responsáveis definidos",
                    "Simulação (exercício de mesa) realizada uma vez",
                ],
                "dep": "Modelagem de ameaças; backup e restauração",
            },
        ],
    },
]


def estilos():
    base = getSampleStyleSheet()
    return {
        "capa": ParagraphStyle("capa", parent=base["Title"], fontSize=26, leading=30, textColor=AZUL, alignment=TA_LEFT),
        "sub": ParagraphStyle("sub", parent=base["Normal"], fontSize=12, leading=16, textColor=CINZA),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontSize=15, textColor=AZUL, spaceBefore=14, spaceAfter=6),
        "txt": ParagraphStyle("txt", parent=base["Normal"], fontSize=10, leading=14),
        "pq": ParagraphStyle("pq", parent=base["Normal"], fontSize=9, leading=12, textColor=CINZA),
        "it": ParagraphStyle("it", parent=base["Normal"], fontSize=10, leading=14, leftIndent=12, bulletIndent=2),
        "it_t": ParagraphStyle("it_t", parent=base["Heading2"], fontSize=12, leading=15, spaceAfter=2),
        "lbl": ParagraphStyle("lbl", parent=base["Normal"], fontSize=9, leading=12, textColor=colors.HexColor("#0f172a")),
    }


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def bloco_issue(etapa, i, issue, st):
    codigo = f"E{etapa['n']}.{i}"
    meta = Table(
        [
            [
                Paragraph("<b>Quem assume:</b> a definir (atribuir no GitHub)", st["lbl"]),
                Paragraph(f"<b>Prioridade:</b> {issue['p']}", st["lbl"]),
            ],
            [
                Paragraph(f"<b>Rótulos:</b> {esc(issue['l'])}", st["lbl"]),
                Paragraph(f"<b>Depende de:</b> {esc(issue['dep'])}", st["lbl"]),
            ],
        ],
        colWidths=[9.0 * cm, 8.0 * cm],
    )
    meta.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), FUNDO),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    itens = [Paragraph(f"[{codigo}] {esc(issue['t'])}", st["it_t"]), meta, Spacer(1, 4)]
    itens.append(Paragraph("<b>Descrição</b>", st["txt"]))
    itens.append(Paragraph(esc(issue["d"]), st["txt"]))
    itens.append(Spacer(1, 3))
    itens.append(Paragraph("<b>Critérios de aceite</b>", st["txt"]))
    for c in issue["c"]:
        itens.append(Paragraph(esc(c), st["it"], bulletText="-"))
    itens.append(Spacer(1, 4))
    itens.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1")))
    itens.append(Spacer(1, 6))
    return KeepTogether(itens)


def rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(CINZA)
    canvas.drawString(2 * cm, 1.2 * cm, "Sócio Digital - Planejamento de Etapas - Grupo 08")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
    canvas.restoreState()


def gerar(etapa):
    st = estilos()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    nome = f"planejamento-de-etapas-{etapa['n']}-{etapa['slug']}.pdf"
    doc = SimpleDocTemplate(
        str(OUT_DIR / nome),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"Planejamento de Etapas - Etapa {etapa['n']}: {etapa['titulo']}",
        author="Grupo 08",
    )
    s = [
        Paragraph("Planejamento de Etapas", st["sub"]),
        Paragraph(f"Etapa {etapa['n']}: {esc(etapa['titulo'])}", st["capa"]),
        Spacer(1, 6),
        Paragraph("Sócio Digital: Copiloto de Gestão Fiscal para Pequenos Negócios", st["sub"]),
        Spacer(1, 14),
        Paragraph("Objetivo", st["h1"]),
        Paragraph(esc(etapa["objetivo"]), st["txt"]),
        Paragraph("Ponto de partida", st["h1"]),
        Paragraph(esc(etapa["contexto"]), st["txt"]),
        Paragraph("Resultado esperado", st["h1"]),
        Paragraph(esc(etapa["saida"]), st["txt"]),
        Paragraph("Resumo das issues", st["h1"]),
    ]
    linhas = [["ID", "Issue", "Prioridade"]]
    for i, iss in enumerate(etapa["issues"], 1):
        linhas.append(
            [
                f"E{etapa['n']}.{i}",
                Paragraph(esc(iss["t"]), st["lbl"]),
                iss["p"],
            ]
        )
    tab = Table(linhas, colWidths=[1.6 * cm, 12.2 * cm, 3.2 * cm], repeatRows=1)
    tab.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), AZUL),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, FUNDO]),
            ]
        )
    )
    s.append(tab)
    s.append(Spacer(1, 8))
    s.append(
        Paragraph(
            "Cada issue abaixo está escrita para ser copiada ao GitHub: o título da seção vira o título da issue; "
            "os rótulos indicados devem ser criados no repositório; a descrição e os critérios de aceite vão no corpo. "
            "Não há responsável fixo: quem pegar a tarefa se atribui no GitHub. As prioridades são sugestões e devem ser confirmadas pela equipe.",
            st["pq"],
        )
    )
    s.append(PageBreak())
    s.append(Paragraph("Issues", st["h1"]))
    for i, iss in enumerate(etapa["issues"], 1):
        s.append(bloco_issue(etapa, i, iss, st))
    doc.build(s, onFirstPage=rodape, onLaterPages=rodape)
    return OUT_DIR / nome


if __name__ == "__main__":
    for e in ETAPAS:
        print(gerar(e))
