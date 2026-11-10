# Backend do MVP — Sócio Digital

Status: aprovado pelo usuário em 2026-11-10. Execução por fluxos completos; plano de implementação é a próxima etapa.

## Intenção e fontes de decisão

Construir o backend que atende às nove telas do MVP, evoluindo a API RAG existente para um produto com contexto empresarial, histórico, fontes verificáveis, cálculos e organização fiscal.

Fontes prioritárias: decisões do usuário nesta conversa; `docs/diagramas/socio-digital-design-backend-2.excalidraw`; `docs/diagramas/socio-digital-telas-mvp-2.excalidraw`; escolhas de Nasser registradas nos commits `29c97ee`, `c15cf01`, `a8e0df9`, `5a4c191`, `ad08db8`, `3792de8` e `0ee0dad`. O desenho novo do backend está presente no workspace, ainda sem commit.

Por orientação expressa do usuário, a documentação de requisitos da Ingrid não será usada como autoridade de decisões. Em particular, concluir uma tarefa não comprova regularidade nem pagamento.

## Abordagens consideradas

1. Implementar fluxos completos, com persistência, serviços, rotas e verificação em cada etapa. Escolhida pelo usuário: permite validar cedo o uso das telas e o isolamento das empresas.
2. Implementar por camadas, construindo todo o banco, depois serviços e rotas. Adia a validação dos fluxos e não foi escolhida.

Arquitetura já definida pelos desenhos: backend modular FastAPI e worker, PostgreSQL, bucket, Qdrant e fila. Não há necessidade de microserviços por domínio.

## Escopo aprovado na conversa

- Cadastro aberto com acesso imediato, sem confirmação de e-mail nesta entrega.
- Autenticação própria por e-mail e senha, hash Argon2id, sessões no PostgreSQL, cookie HttpOnly, SameSite=Lax e Secure em produção; proteção CSRF, expiração, revogação e limite de tentativas.
- Uma conta possui várias empresas. Cada empresa pertence exclusivamente à conta que a criou. Selecionar um perfil determina o contexto da navegação.
- Cadastro e edição de empresa com procedência dos campos.
- Biblioteca e leitor de normas, versões e citações por âncoras.
- Assistente com conversas persistidas, confirmação de contexto, fontes e até três próximos passos.
- Situação fiscal baseada em evidências declaradas, anexos privados e tarefas com histórico.
- Cálculos determinísticos de MEI e Simples Nacional, incluindo Fator R.
- Ingestão administrativa por comando, sem tela administrativa.
- PostgreSQL, armazenamento compatível com S3, Redis e worker. Execução local via Docker Compose foi a premissa apresentada pelo assistente após a concordância do usuário, sem definição de hospedagem de produção.

## Fora da primeira entrega

Conectores oficiais, confirmação de e-mail, lembretes externos, compartilhamento de empresas, frontend, tela administrativa e deploy público. Esqueci minha senha/envio de e-mails não foram solicitados e ficam fora desta primeira entrega por proposta do assistente. Não emitir guias, transmitir declarações nem apresentar simulações como apurações oficiais.

## Invariantes e limites

- Autorizar acesso a cada recurso pelo proprietário da empresa; UUID ou empresa selecionada no navegador não constituem autorização.
- Separar norma, cálculo e fato fiscal nas respostas. Guia anexada não comprova pagamento. Conclusão de tarefa só altera tarefa e histórico.
- Distinguir ausência, indisponibilidade, vencimento e pendência comprovada. Sem evidência válida, não afirmar regularidade.
- Arquivos empresariais privados nunca entram no índice jurídico compartilhado.
- Citações apontam para documento, versão e âncora retornados por ferramentas. Validar existência e vínculo não comprova que toda afirmação textual é sustentada; não prometer essa garantia.
- Cálculos são executados pelo motor, nunca pelo modelo generativo. Ausência de dados ou regra válida gera motivo estruturado, sem valores presumidos.
- Preservar versões publicadas e evidências anteriores; falha de consulta não apaga a última evidência.

## Módulos e armazenamento

### Acesso e empresas

Conta, sessão e empresa no PostgreSQL. Todas as empresas têm `owner_account_id`; conversas, evidências e tarefas têm `company_id`. A empresa ativa é estado de navegação do cliente: cada rota informa a empresa ou resolve sua empresa a partir do recurso, sempre com autorização no servidor.

Cadastro coleta CNPJ, CNAE principal, porte, regime e município/UF. Sem conector, procedência é declarada. Campos mantêm origem e data da alteração. Não inferir regime tributário a partir do porte ou CNAE. Dados financeiros são solicitados no contexto do cálculo e associados à competência; sua ausência no perfil não bloqueia o cadastro.

Propostas do assistente: normalizar e-mail e impor unicidade; CNPJ único por conta; não permitir troca de CNPJ após criação nesta versão, orientando criar outro perfil. Não oferecer edição ou exclusão de contas e empresas nesta entrega.

Sessões usam token opaco aleatório; guardar apenas seu hash no banco. Logout revoga a sessão. A proteção CSRF cobre operações mutáveis e login; validar origem e usar token CSRF. Proposta: frontend e API servidos no mesmo site, incluindo proxy em desenvolvimento, CORS restrito quando necessário. Mensagens de login não revelam existência da conta. Limitação de tentativas deve funcionar entre processos, com Redis. Segredos configuráveis por ambiente, sem valores de produção no repositório.

### Base jurídica e ingestão

Comando administrativo recebe arquivos e metadados de fonte oficial; coloca original no bucket e registra job idempotente. Worker normaliza JSON por versão com seções/artigos/parágrafos e âncoras estáveis dentro da versão. PostgreSQL contém catálogo, assuntos, vigência, checksum e chaves dos objetos. Bucket contém original e JSON imutáveis por versão; Qdrant é índice derivado.

Entrada inicial proposta: HTML, Markdown e PDF com texto extraível; PDF sem texto retorna necessidade de tratamento, sem OCR nesta entrega. O comando admite referências aos arquivos já existentes no acervo. Reutilização dos coletores e do refino será avaliada no plano, sem reescrever o pipeline inteiro.

Estados de versão: recebida, processando, pronta, falhou; somente pronta participa do catálogo público e da recuperação. Antes de publicar, validar JSON, metadados e correspondência de todas as âncoras indexadas. Publicação usa estado no catálogo como referência; consultas filtram versões publicadas e revalidam resultados no catálogo para não expor índices parciais. Reprocessamento não substitui silenciosamente versão publicada.

Biblioteca pesquisa título, número, artigo e palavra-chave e filtra assunto, tipo, órgão e vigência. Leitor resolve `document_id + version_id + anchor_id`; retorna metadados e URLs dos objetos. Bucket de normas também pode ser privado, com URLs temporárias e CORS restrito para leitura direta do navegador. Sem âncora, abrir a mesma versão com aviso; sem versão disponível, informar e oferecer a fonte oficial. Não redirecionar silenciosamente para versão atual.

### Assistente

Persistir conversa e mensagens por empresa, operação idempotente, contexto empresarial utilizado, confirmações, citações e próximos passos. Estado de resposta distingue concluída, aguardando dados, contexto insuficiente e falha. Confirmar competência quando ambígua; não assumir que um período mencionado corresponde ao pagamento.

Proposta após revisão: usar os dados declarados do perfil selecionado sem reconfirmar a cada conversa. Pedir esclarecimento quando faltarem entradas obrigatórias, houver ambiguidade ou divergência entre mensagem e perfil. A empresa da conversa é fixa; trocar de perfil abre ou recupera conversas da outra empresa. Registrar snapshot dos dados usados em cada operação; resposta a uma solicitação de esclarecimento retoma essa operação, sem sobrescrever o perfil automaticamente.

Ferramentas: recuperação jurídica, motor fiscal e consulta interna de evidências. Conectores externos permanecem indisponíveis nesta entrega. Resposta distingue explicação normativa, resultado calculado e situação não verificada. Validador rejeita citações inventadas e preserva IDs e contexto usados. No máximo três próximos passos; transformação em tarefa exige ação explícita do usuário para evitar criação automática indesejada (proposta do assistente).

Reutilizar `backend/api/app` e os modelos configuráveis existentes; não trocar modelos nem reindexar a coleção atual sem necessidade documentada. O contrato atual não possui version_id/anchor_id: preservar `/rag/query` como consulta jurídica existente, sem contexto privado, e construir o contrato persistido do produto separadamente. A partir da introdução de autenticação, proteger também a rota legada; health e readiness permanecem públicos, sem dados sensíveis. Índice novo ou migração explícita para trechos versionados, preservando a coleção existente.

Proposta: aceitar mensagem com HTTP 202 e identificador de operação; worker processa e cliente consulta estado/histórico por polling. Não incluir streaming nesta entrega. Repetição da mesma operação não duplica mensagem, cálculo ou tarefas.

### Motor fiscal

Revisar `src/fiscal` antes de integrar. Código atual usa floats, parâmetros padrão e arredondamentos sem contrato completo de vigência. Não é suficiente expô-lo diretamente como motor validado.

Contrato recebe empresa, competência, dados obrigatórios e operação; retorna estado, resultado, premissas, entradas utilizadas, versão da regra e referências. Valores monetários usam Decimal e representação decimal no contrato. Definir arredondamentos em regras testadas. Validar números negativos, limites e situações não cobertas. Regras precisam de vigência e revisão explícita antes de habilitação; sem regra revisada para uma competência, responder indisponível em vez de usar defaults.

Escopo: simulação mensal de MEI e Simples, seleção de faixa e Fator R nos cenários cobertos. Não presumir enquadramento completo apenas por CNAE. Casos especiais não cobertos retornam limitação estruturada. Fontes/tabelas e competência habilitada devem ser documentadas e avaliadas no plano; implementar mecanismo não autoriza publicar regra fiscal não revisada.

### Evidências, painel e tarefas

Evidência registra empresa, tipo, origem declarada, competência/abrangência, coleta, validade quando conhecida e referência ao arquivo privado. Sem análise documental automática nesta etapa: usuário informa metadados; upload não confirma seu conteúdo (proposta do assistente). Arquivos têm limites de tamanho/tipo, chaves geradas pelo servidor e download autorizado com URL temporária.

Painel deriva indicadores independentes de cadastro, certidão federal e obrigações. Na ausência de conectores, mostrar origem declarada e ausência de verificação oficial. Exibir data e escopo, inclusive para evidência vencida. Cadastro manual de empresa não equivale a cadastro ativo na Receita.

Proposta após revisão: obrigações são cadastradas manualmente com nome/tipo, competência e prazo opcional, podendo receber evidências e tarefas vinculadas. Não gerar calendário nem presumir aplicabilidade por regime nesta etapa. O painel resume somente os registros disponíveis, explicita a cobertura parcial e mantém o estado de verificação oficial como não verificado. Ausência de registros não significa inexistência de obrigações; prazo vencido de tarefa não é pendência fiscal confirmada.

Tarefa registra orientação, competência, prazo opcional, vínculo de origem e histórico. Atualização de conclusão é idempotente. Ações podem ser revertidas com evento correspondente por proposta do assistente. Lembretes externos não são executados nesta etapa.

## Contratos HTTP a detalhar no plano

- Acesso: cadastro, login, logout, sessão atual e token CSRF.
- Empresas: POST/GET `/empresas`, GET/PATCH `/empresas/{id}`.
- Conversas: POST/GET `/empresas/{id}/conversas`; GET conversa e mensagens; POST mensagem; GET operação pendente.
- Normas: GET `/normas`, GET `/normas/{id}/versoes/{versao}`, resolução de citação e âncora.
- Fiscal: GET `/empresas/{id}/situacao-fiscal`, POST/GET evidências e acesso autorizado a anexos.
- Tarefas: GET/POST por empresa, GET/PATCH tarefa, histórico.
- Cálculos: POST por empresa e GET resultado persistido.

Rotas ilustram responsabilidades; nomes finais ficam com o implementador. Listagens paginadas, erros estruturados, validação de entrada e estados assíncronos fazem parte dos contratos. Recursos alheios não revelam sua existência.

## Execução e consistência

Compose integra API, worker, PostgreSQL, Redis, Qdrant e implementação S3 local, proposta MinIO. Ollama e modelos mantêm a configuração existente. Migrações versionadas no banco, volumes persistentes e exemplos de ambiente sem segredos.

Proposta: fila Redis com biblioteca de worker escolhida no plano; jobs duráveis registrados no PostgreSQL, mecanismo de outbox para publicação recuperável, tentativas limitadas, timeout e estados de falha observáveis. Não depender de promessa de execução exatamente uma vez: handlers idempotentes e reconciliação de operações interrompidas. Não fazer transação distribuída entre bucket, PostgreSQL e Qdrant.

Retenção inicial proposta: não executar expurgo automático de histórico ou versões nesta entrega. Sessões expiradas e objetos temporários podem ter limpeza própria. Política de retenção de produção precisa de decisão antes de deploy público. Logs registram IDs de operação e estados, sem senhas, tokens, conteúdo de anexos ou conversas. Medir latência, falhas de jobs e rejeição de citações.

## Sequência escolhida e verificação

1. Fundação mínima e fluxo cadastro → login → criar/selecionar empresas, com isolamento verificado entre contas.
2. Ingestão → biblioteca → leitor versionado, com recuperação após falhas e âncoras verificadas.
3. Conversa → confirmação → recuperação → resposta persistida → leitor na citação; testar idempotência e falhas de modelo.
4. Upload declarado → evidência → painel e tarefa → conclusão/histórico, comprovando que tarefas não alteram regularidade.
5. Cálculos versionados → ferramenta do assistente, incluindo testes de precisão, limites e falta de dados/regras.

Cada fluxo terá testes de domínio e integração necessários; verificar acesso indevido, CSRF, revogação de sessão, arquivos privados, publicação parcial e reprocessamento. Preservar testes úteis de RAG e avaliação. Testes locais não equivalem a validação fiscal profissional nem a produção homologada.

## Decisões deixadas ao plano

Biblioteca de sessões, ORM/migrações, cliente S3, worker, limites exatos, duração de sessões/URLs, schemas e índices, implementação das buscas textuais e estratégia de indexação versionada. Escolher alternativas compatíveis com o código existente e documentar justificativas. Consultar documentação oficial atual das dependências antes de implementar.

O plano deve explicitar as propostas do assistente acima; aprovação desta spec aprova essas propostas, sem atribuí-las retroativamente ao usuário.
