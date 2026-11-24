# Plano de implementação da leitura de guias no Assistente Fiscal

> **Para quem implementar:** use `superpowers:subagent-driven-development` ou `superpowers:executing-plans`. Marque os passos com `- [x]` depois de verificá-los.

**Objetivo** — Permitir que uma pergunta no Assistente use uma imagem de DAS já enviada na tela Fiscal.

**Arquitetura** — A mensagem referencia uma evidência da empresa. O worker lê a imagem do bucket privado, envia texto e imagem ao `deepseek-flash` e reaproveita os campos validados ao retomar a mesma consulta. O Assistente apresenta esses campos ao lado da orientação fiscal e das citações existentes.

**Stack** — FastAPI, Pydantic, HTTPX, PostgreSQL, RQ, SeaweedFS/S3, React, Playwright e Pytest.

**Especificação** — [Leitura de guias no Assistente Fiscal](../specs/2026-11-24-assistente-leitura-de-guias-design.md).

## Restrições

- Uma imagem PNG ou JPEG de DAS por mensagem, a partir de evidência existente. Vale o limite vigente de 10 MiB por arquivo.
- Habilitação explícita em `GUIDE_VISION_ENABLED`, com `DEEPSEEK_API_KEY` no ambiente. O provedor de texto continua definido por `LLM_PROVIDER`.
- A UI informa o envio da imagem selecionada à DeepSeek antes de o usuário enviar a pergunta. O bucket privado existente fornece os bytes.
- A saída documental cobre competência, vencimento e valor. A verificação de pagamento segue o fluxo fiscal existente.
- A homologação no provedor usa uma guia fictícia. A suíte automatizada usa respostas controladas.

## Foco da revisão

- Mesmo titular com duas empresas e evidência vinculada à outra empresa. A API recusa a referência e o worker repete a checagem de vínculo. Tarefas 1 e 3.
- Evidências antigas com PNG, JPEG e PDF. Listar por MIME real do objeto e checar a assinatura novamente no worker. Tarefas 1 e 3.
- Imagem cortada ou resposta inválida do provedor. Campos ilegíveis aparecem como ausentes e resultados fora do contrato não são publicados. Tarefas 2 e 3.
- Competência explícita divergente e retomada da mesma consulta. A confirmação preserva a imagem original e a leitura concluída. Tarefa 3.
- Falha no envio ou clique para tentar novamente. A consulta mantém o vínculo com a guia, inclusive após recarregar a conversa. Tarefa 4.

## Arquivos e responsabilidades

| Área | Arquivos | Responsabilidade |
| --- | --- | --- |
| Configuração e API | `backend/api/app/config.py`, `backend/.env.example`, `backend/compose.yaml`, `backend/compose.prod.yaml`, `backend/api/app/assistant/{router,schemas,service,context}.py`, `backend/api/app/evidence/service.py`, `backend/api/app/storage.py` | Habilitação, opções elegíveis, autorização e vínculo à mensagem. |
| Visão e execução | `backend/api/app/llm_client.py`, novo `backend/api/app/assistant/agents/guide_vision.py`, `backend/api/app/assistant/agents/{executor,prompts}.py` | Chamada multimodal, validação, retomada e publicação dos campos. |
| Interface | `frontend/src/pages/Assistente.tsx`, novo `frontend/src/pages/assistente/GuidePicker.tsx`, `frontend/src/pages/assistente/operacao.ts`, `frontend/src/types/openapi.d.ts` | Seleção, histórico, progresso e apresentação da leitura. |
| Testes e reprodução | `backend/api/tests/test_guide_vision.py`, `backend/api/tests/mvp/test_guide_messages.py`, `frontend/e2e/assistente.pw.ts`, `backend/README.md` | Contratos, execução da fila e roteiro com guia fictícia. |

## Tarefa 1 — Disponibilidade, seleção e vínculo da evidência

**Produz** — `GET /empresas/{company_id}/guias-para-assistente?cursor=…` com `GuideOptionsView(enabled: bool, items: list[GuideOption], next_cursor: str | None)`. Cada `GuideOption` contém `id`, `period` e `created_at`. `MessageInput.evidence_id: UUID | None` referencia uma guia.

- [x] Em `test_guide_messages.py`, escrever `test_guide_options_include_existing_png_and_jpeg_only` e `test_rejects_foreign_or_unavailable_guide`. Cobrir `enabled=false` sem chamada ao S3, PNG/JPEG antigos, PDF, anexos ausentes, outra empresa da mesma conta, conta diferente, envio com leitura desabilitada e tentativa de trocar a imagem numa confirmação. A referência a outra empresa deve devolver 404 e nenhuma tentativa rejeitada deve enfileirar consulta.
- [x] Rodar `../../.venv/bin/python -m pytest tests/mvp/test_guide_messages.py -q -k 'options or rejects'` em `backend/api`, com os serviços de teste do README. Esperar falha por falta da rota e do campo.
- [x] Adicionar `guide_vision_enabled: bool = False` a `Settings`. Usar a flag e a presença de `deepseek_api_key` para calcular a disponibilidade. Propagar a flag no Compose local e de produção, nos ambientes de API/worker, e documentar a variável no `.env.example`.
- [x] Adicionar `ObjectStorage.content_type(key: str, private: bool) -> str | None` com `HeadObject`. Em `evidence/service.py`, implementar `require_guide_attachment(db, account_id, company_id, evidence_id) -> Evidence` para reusar a autorização existente e verificar tipo `guide`, empresa e arquivo. Na rota de opções, paginar as guias anexadas com o cursor existente e filtrar por MIME do S3. Uma página filtrada pode vir vazia com `next_cursor`. Chaves de objetos ficam no servidor. Em `submit_message`, validar a guia e o MIME antes de enfileirar. Tratar 404 do objeto como arquivo indisponível e falha de conexão como 503.
- [x] Persistir o UUID no pedido da operação e no contexto da mensagem do usuário como `evidence_id`, incluindo o campo apenas quando fornecido. Manter a forma do pedido textual usada no cálculo da chave idempotente. Recusar `evidence_id` no payload de confirmação. Para consultas com guia, adiar a confirmação automática de competência até o worker ler o documento. Preservar as demais validações de contexto e cálculo.
- [x] Rodar novamente o comando da tarefa. Esperar que os testes de opções e autorização passem. Fazer o commit da configuração e do vínculo.

## Tarefa 2 — Chamada de visão com saída validada

**Produz** — `GuideReading(period: Period | None, due_date: date | None, amount: Money | None)` e `read_guide(settings: Settings, image: bytes, media_type: str, *, timeout: float, http_client: httpx.Client | None = None) -> tuple[GuideReading, dict]` em `assistant/agents/guide_vision.py`. Usar os tipos de competência e valor existentes, com decimal não negativo e duas casas na saída.

- [x] Escrever `test_deepseek_vision_sends_instruction_and_image` com `httpx.MockTransport`. Conferir `/chat/completions`, modelo `deepseek-flash`, partes `text` e `image_url`, MIME e bytes iguais à entrada, e retorno para `2026-10`, `2026-11-20` e `81.05`. Escrever `test_guide_reading_handles_null_fields_and_rejects_invalid_values` com campo `null`, competência inválida, data impossível, número em ponto flutuante e JSON inválido. Verificar que uma falha HTTP vira erro de dependência sem expor imagem, chave ou corpo do provedor.
- [x] Rodar `../../.venv/bin/python -m pytest tests/test_guide_vision.py -q` em `backend/api`. Esperar falha pela ausência do adaptador.
- [x] Ampliar a tipagem do cliente compatível com Chat Completions em `llm_client.py` para blocos tipados de conteúdo. Reaproveitar a configuração de DeepSeek, timeout, JSON e tratamento de erros. Em `read_guide`, usar a configuração de DeepSeek e modelo explícito para esta chamada, enviar a imagem em uma data URL e pedir JSON com campos nulos quando a leitura não for possível. A instrução fixa de extração trata o texto presente na imagem como conteúdo do documento. A saída contém somente os três campos validados e metadados de uso esperados pelo registro de etapas.
- [x] Rodar `../../.venv/bin/python -m pytest tests/test_guide_vision.py tests/test_llm_client.py -q`. Esperar que os novos testes e os contratos de geração textual passem. Fazer o commit do adaptador.

## Tarefa 3 — Leitura e retomada pelo worker

**Consome** — `require_guide_attachment` da tarefa 1 e `read_guide` da tarefa 2. **Produz** — etapa `document` e `Message.context.guide_reading` com `{evidence_id, period, due_date, amount}`. Os campos ausentes são `null`.

- [x] Em `test_guide_messages.py`, escrever `test_worker_reads_guide_before_supervisor_and_reuses_reading_after_confirmation`. Enviar “Qual a competência e o valor desta guia?” sem competência na mensagem e verificar extração primeiro e publicação com os valores. Para uma consulta fiscal dependente de competência, cobrir competência ausente e divergente. Ao confirmar, verificar mesma operação, `read_guide` chamado uma vez, e competência confirmada usada pelo fiscal. Escrever `test_worker_handles_unreadable_guide_and_rejects_wrong_signature` para cobrir os três campos nulos, confirmação quando aplicável, assinatura divergente e verificação de vínculo também no worker. Em ambos, atestar que a imagem não aparece no registro da operação, na telemetria nem no contexto público.
- [x] Rodar `../../.venv/bin/python -m pytest tests/mvp/test_guide_messages.py -q -k worker`. Esperar falha até existir a etapa `document`.
- [x] Em `executor.py`, executar `document` antes de `plan` quando o pedido original tiver `evidence_id`. Usar `claim_step` e `finish_step` com o UUID da evidência como entrada. Depois de confirmar o vínculo, reaproveitar uma etapa `document` concluída da mesma execução e com o mesmo hash de entrada, mesmo que a revisão da confirmação tenha mudado. Na leitura nova, declarar MIME a partir da assinatura PNG/JPEG e conferir a concordância com os metadados e o checksum. Manter o prazo da etapa, os retries e o tratamento de falhas do executor. Persistir campos validados e metadados da etapa.
- [x] Em `executor.py` e `prompts.py`, deixar o supervisor decidir se a pergunta precisa de norma ou diagnóstico. Permitir uma consulta só de leitura com plano sem especialistas quando a imagem estiver presente. O bloco documental publicado vem do resultado validado e fica disponível mesmo se a busca jurídica não encontrar suporte. Quando a consulta fiscal precisar de competência, aproveitar o valor lido se a mensagem não informar outro e pedir confirmação quando houver ausência ou divergência. Uma confirmação prevalece nas revisões seguintes. Manter os campos lidos separados do cálculo e da situação de pagamento.
- [x] Rodar `../../.venv/bin/python -m pytest tests/mvp/test_guide_messages.py tests/mvp/test_multiagent_workflow.py tests/mvp/test_evidence.py -q`. Esperar publicação de uma única resposta por operação e regressões de chat e evidências verdes. Fazer o commit da integração do worker.

## Tarefa 4 — Fluxo visual e homologação

**Consome** — Rota de opções e `evidence_id` da tarefa 1, etapa `document` e `guide_reading` da tarefa 3. **Produz** — seleção de uma guia em **Conferir uma guia**, identificação da evidência no histórico e leitura visível na resposta.

- [x] Em `frontend/e2e/assistente.pw.ts`, escrever `envia pergunta com a guia selecionada e mostra os dados lidos` e `mantém a guia ao tentar novamente e preserva o chat por texto`. Verificar texto e UUID no POST; aviso de envio à DeepSeek; estado `Lendo a guia`; referência à evidência, `10/2026`, `20/11/2026` e `R$ 81,05` na resposta; orientação para imagem ilegível; tentativa novamente com o mesmo vínculo; troca de empresa limpando a seleção; e envio textual com leitura desativada. Incluir uma página vazia com `next_cursor` seguida de uma guia elegível.
- [x] Com o frontend de teste ativo, rodar `npm run test:e2e -- e2e/assistente.pw.ts` em `frontend`. Esperar falha dos novos cenários antes de implementar a seleção.
- [x] Implementar `GuidePicker({companyId, selectedId, onSelect})` em `frontend/src/pages/assistente/GuidePicker.tsx`. Usar a rota nova, navegando até a próxima página enquanto houver cursor, inclusive quando a página vier vazia. Exibir o fallback textual quando a leitura estiver desativada. Em `Assistente.tsx`, vincular o seletor ao atalho existente, guardar a seleção no envio e aproveitar `Message.context.evidence_id` no reenvio após falha. Limpar a seleção depois do envio aceito e na troca de empresa/conversa. Exibir os dados validados e um atalho para a evidência no Fiscal. Em `operacao.ts`, cadastrar o rótulo `Lendo a guia`.
- [x] Atualizar os tipos com `npm run api:types` contra a API atualizada. Rodar `npm test`, `npm run build` e `npm run test:e2e -- e2e/assistente.pw.ts`. Esperar saída zero nos três comandos.
- [x] Descrever a habilitação no `backend/README.md`, disponibilizar a guia fictícia e fazer o commit da interface e do roteiro.
- [ ] Homologar na DeepSeek com a chave no ambiente local. Conferir os campos, a indicação de pagamento e uma pergunta textual. Registrar tempos e resultados observados. A chave não estava configurada durante os testes automatizados.
