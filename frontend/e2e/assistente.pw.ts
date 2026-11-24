import { expect, test, type Page } from '@playwright/test';

const REFUSAL = 'Não encontrei contexto normativo publicado e vigente suficiente para responder.';
const company = {
  id: 'empresa-teste',
  cnpj: '11222333000181',
  cnae: '6201501',
  size: 'ME',
  regime: 'Simples Nacional',
  municipality: 'Brasília',
  state: 'DF',
  provenance: {},
  created_at: '2026-01-01',
};
const citation = {
  document_id: 'd1',
  version_id: 'v1',
  anchor_id: 'a1',
  title: 'LC 123/2006',
  text: 'Art. 13. O Simples Nacional implica o recolhimento mensal…',
  official_url: 'https://www.planalto.gov.br/',
  citation_index: 1,
};
const userMsg = {
  id: 'm1',
  conversation_id: 'c1',
  operation_id: 'op1',
  role: 'user',
  status: 'answered',
  text: 'Qual a periodicidade do DAS?',
  citations: [],
  next_steps: [],
  context: {},
};
const answerMsg = {
  ...userMsg,
  id: 'm2',
  role: 'assistant',
  text: 'O recolhimento é mensal. [1]',
  citations: [citation],
};

type Mock = { messages: unknown[]; operations?: Record<string, unknown> };

async function openChat(page: Page, mock: Mock) {
  // Registered first so every specific route below wins; nothing reaches a real API.
  await page.route('**/api/**', (route) => route.fulfill({ status: 404, json: { detail: 'sem mock' } }));
  await page.route('**/api/auth/session', (route) =>
    route.fulfill({ json: { id: 'conta-teste', email: 'teste@example.invalid' } }));
  await page.route('**/api/auth/csrf', (route) => route.fulfill({ json: { csrf_token: 'csrf' } }));
  await page.route('**/api/empresas?*', (route) =>
    route.fulfill({ json: { items: [company], next_cursor: null } }));
  await page.route('**/api/empresas/empresa-teste/conversas?*', (route) =>
    route.fulfill({
      json: { items: [{ id: 'c1', title: 'Consulta', company_id: 'empresa-teste' }], next_cursor: null },
    }));
  await page.route('**/api/conversas/c1/mensagens**', (route) =>
    route.request().method() === 'POST'
      ? route.fulfill({ status: 202, json: { operation_id: 'op2', status: 'queued' } })
      : route.fulfill({ json: { items: mock.messages, next_cursor: null } }));
  await page.route('**/api/operacoes/*', (route) => {
    const id = route.request().url().split('/').pop()!;
    const op = mock.operations?.[id];
    return op ? route.fulfill({ json: op }) : route.fulfill({ status: 404, json: { detail: 'Operação não encontrada' } });
  });
  await page.goto('/#assistente?conversa=c1');
}

test('marcador [1] abre o trecho citado no leitor lateral', async ({ page }) => {
  await openChat(page, { messages: [userMsg, answerMsg] });
  const link = page.getByRole('link', { name: /Fonte 1: LC 123\/2006/ });
  await expect(link).toHaveText('[1]');
  await expect(link).toHaveAttribute('href', /anchor_id=a1/);
});

test('recusa aparece como aviso com caminho para a Biblioteca', async ({ page }) => {
  await openChat(page, { messages: [userMsg, { ...answerMsg, text: REFUSAL, citations: [] }] });
  await expect(page.getByRole('note')).toContainText('Ainda não há norma publicada');
  await expect(page.getByRole('link', { name: 'Ver normas disponíveis' })).toHaveAttribute('href', '#normas');
});

test('mostra as etapas dos agentes enquanto a consulta roda', async ({ page }) => {
  await openChat(page, {
    messages: [{ ...userMsg, status: 'running' }],
    operations: {
      op1: {
        operation_id: 'op1', status: 'running', error: null,
        run: { status: 'running', stages: [
          { name: 'plan', status: 'succeeded', attempts: 1, error: null },
          { name: 'legal', status: 'running', attempts: 1, error: null },
        ] },
      },
    },
  });
  const progress = page.getByRole('status', { name: 'Andamento da consulta' });
  await expect(progress).toContainText('Entendendo a pergunta');
  await expect(progress).toContainText('Buscando normas vigentes');
});

test('parar de aguardar libera o envio', async ({ page }) => {
  await page.clock.install();
  await openChat(page, {
    messages: [{ ...userMsg, status: 'running' }],
    operations: { op1: { operation_id: 'op1', status: 'running', error: null, run: null } },
  });
  await expect(page.getByRole('button', { name: 'Enviar', exact: true })).toBeDisabled();
  await page.clock.fastForward('03:01');
  await page.getByRole('button', { name: 'Parar de aguardar' }).click();
  await page.getByRole('textbox', { name: 'Mensagem' }).fill('Outra pergunta');
  await expect(page.getByRole('button', { name: 'Enviar', exact: true })).toBeEnabled();
  await expect(page.getByText('Você parou de acompanhar esta consulta')).toBeVisible();
});

test('falha explica o motivo e reenvia a mesma pergunta', async ({ page }) => {
  await openChat(page, {
    messages: [{ ...userMsg, status: 'failed' }],
    operations: {
      op1: {
        operation_id: 'op1', status: 'failed', error: 'agent_execution_failed',
        run: { status: 'failed', stages: [
          { name: 'legal', status: 'failed', attempts: 1, error: 'invalid_agent_result' },
        ] },
      },
    },
  });
  await expect(page.getByRole('alert')).toContainText('não passou na conferência de fontes');
  const sent = page.waitForRequest(
    (r) => r.method() === 'POST' && r.url().includes('/conversas/c1/mensagens'),
  );
  await page.getByRole('button', { name: 'Tentar de novo' }).click();
  expect(JSON.parse((await sent).postData()!)).toEqual({ text: userMsg.text });
});

test('confirmação exige escolha explícita e mostra o que falta', async ({ page }) => {
  await openChat(page, {
    messages: [{
      ...userMsg,
      status: 'awaiting_data',
      context: {
        missing_fields: ['regime', 'kind', 'conditions_confirmed'],
        company: { regime: 'Simples Nacional', municipality: 'Brasília', state: 'DF' },
      },
    }],
    operations: { op1: { operation_id: 'op1', status: 'awaiting_data', error: null, run: null } },
  });
  const form = page.getByRole('form', { name: 'Confirmação de contexto' });
  await expect(form.getByLabel('Qual é o regime da empresa?')).toBeFocused();
  await expect(form.getByLabel('Qual é o regime da empresa?')).toHaveValue('Simples Nacional');
  await expect(form.getByLabel('Qual simulação deseja fazer?')).toHaveValue('');
  await form.getByRole('button', { name: 'Confirmar contexto' }).click();
  await expect(form.getByRole('alert')).toHaveText('Preencha: tipo de simulação, confirmação das condições.');
});

test('valor em formato errado não passa na confirmação', async ({ page }) => {
  await openChat(page, {
    messages: [{ ...userMsg, status: 'awaiting_data', context: { missing_fields: ['revenue'] } }],
    operations: { op1: { operation_id: 'op1', status: 'awaiting_data', error: null, run: null } },
  });
  const form = page.getByRole('form', { name: 'Confirmação de contexto' });
  await form.getByLabel('Receita da competência (R$)').fill('1.500');
  let posted = false;
  page.on('request', (r) => { if (r.method() === 'POST') posted = true; });
  await form.getByRole('button', { name: 'Confirmar contexto' }).click();
  await expect(form.getByRole('alert')).toHaveText('Corrija: receita da competência (use o formato 1500,00).');
  expect(posted).toBe(false);
});

test('depois de parar de aguardar, a nova pergunta é acompanhada', async ({ page }) => {
  await page.clock.install();
  const mock = {
    messages: [{ ...userMsg, status: 'running' }] as unknown[],
    operations: {
      op1: { operation_id: 'op1', status: 'running', error: null, run: null },
      op2: { operation_id: 'op2', status: 'running', error: null,
        run: { status: 'running', stages: [{ name: 'plan', status: 'running', attempts: 1, error: null }] } },
    } as Record<string, unknown>,
  };
  await openChat(page, mock);
  await expect(page.getByRole('status', { name: 'Andamento da consulta' })).toBeVisible();
  await page.clock.fastForward('03:01');
  await page.getByRole('button', { name: 'Parar de aguardar' }).click();
  mock.messages.push({ ...userMsg, id: 'm3', operation_id: 'op2', status: 'running', text: 'Outra pergunta' });
  await page.getByRole('textbox', { name: 'Mensagem' }).fill('Outra pergunta');
  await page.getByRole('button', { name: 'Enviar', exact: true }).click();
  await page.clock.fastForward('00:02');
  await expect(page.getByRole('status', { name: 'Andamento da consulta' })).toContainText('Entendendo a pergunta');
  await expect(page.getByRole('button', { name: 'Enviar', exact: true })).toBeDisabled();
});

test('polling pendurado ainda oferece parar de aguardar', async ({ page }) => {
  await page.clock.install();
  await openChat(page, { messages: [{ ...userMsg, status: 'running' }] });
  await page.route('**/api/operacoes/*', () => { /* nunca responde */ });
  await expect(page.getByRole('status', { name: 'Andamento da consulta' })).toBeVisible();
  await page.clock.fastForward('03:01');
  await expect(page.getByRole('button', { name: 'Parar de aguardar' })).toBeVisible();
});

test('erro no polling ainda permite parar de aguardar', async ({ page }) => {
  await openChat(page, { messages: [{ ...userMsg, status: 'running' }] });
  await page.route('**/api/operacoes/*', (route) => route.fulfill({ status: 500, json: { detail: 'Falha interna' } }));
  await page.getByRole('button', { name: 'Parar de aguardar' }).click();
  await page.getByRole('textbox', { name: 'Mensagem' }).fill('Outra pergunta');
  await expect(page.getByRole('button', { name: 'Enviar', exact: true })).toBeEnabled();
});

test('avaliação da resposta envia a operação e confirma só depois de salvar', async ({ page }) => {
  let body: unknown;
  await openChat(page, { messages: [userMsg, answerMsg] });
  await page.route('**/api/rag/feedback', (route) => {
    body = route.request().postDataJSON();
    return route.fulfill({ status: 204 });
  });
  await page.getByRole('button', { name: 'Não', exact: true }).click();
  await page.getByRole('button', { name: 'Difícil de entender' }).click();
  await expect(page.getByText('Obrigado pela sua avaliação!')).toBeVisible();
  expect(body).toEqual({ request_id: 'op1', useful: false, reason: 'confusa' });
});

test('avaliação que falha mostra o erro e permite tentar de novo', async ({ page }) => {
  let status = 404;
  await openChat(page, { messages: [userMsg, answerMsg] });
  await page.route('**/api/rag/feedback', (route) =>
    status === 404
      ? route.fulfill({ status, json: { detail: 'Consulta não encontrada' } })
      : route.fulfill({ status }));
  await page.getByRole('button', { name: 'Sim', exact: true }).click();
  await expect(page.getByText('Não foi possível salvar sua avaliação. Tente novamente.')).toBeVisible();
  await expect(page.getByText('Obrigado pela sua avaliação!')).toHaveCount(0);
  status = 204;
  await page.getByRole('button', { name: 'Sim', exact: true }).click();
  await expect(page.getByText('Obrigado pela sua avaliação!')).toBeVisible();
});

const guideId = 'evidence-guide-id';
const guideFields = { evidence_id: guideId, period: '2026-10', due_date: '2026-11-20', amount: '81.05' };

test('envia pergunta com a guia selecionada e mostra os dados lidos', async ({ page }) => {
  const mock: Mock = { messages: [userMsg], operations: {} };
  await openChat(page, mock);
  await page.route('**/api/empresas/empresa-teste/guias-para-assistente**', (route) => {
    const cursor = new URL(route.request().url()).searchParams.get('cursor');
    return route.fulfill({ json: cursor ? {
      enabled: true, items: [{ id: guideId, period: '2026-10', created_at: '2026-11-20T12:00:00Z' }],
      next_cursor: null,
    } : { enabled: true, items: [], next_cursor: 'segunda-pagina' } });
  });

  await page.getByRole('button', { name: 'Conferir uma guia' }).click();
  const guide = page.getByLabel('Guia cadastrada');
  await expect(guide).toBeEnabled();
  await expect(page.getByText(/imagem selecionada será enviada à DeepSeek/)).toBeVisible();
  await guide.selectOption(guideId);
  const question = 'Qual a competência e o valor desta guia?';
  await page.getByRole('textbox', { name: 'Mensagem' }).fill(question);

  mock.operations!.op2 = {
    operation_id: 'op2', status: 'running', error: null,
    run: { status: 'running', stages: [{ name: 'document', status: 'running', attempts: 1, error: null }] },
  };
  await page.route('**/api/conversas/c1/mensagens**', (route) => {
    if (route.request().method() !== 'POST') return route.fallback();
    mock.messages.push({
      ...userMsg, id: 'm-guide', operation_id: 'op2', text: question, status: 'queued',
      context: { evidence_id: guideId },
    });
    return route.fulfill({ status: 202, json: { operation_id: 'op2', status: 'queued' } });
  });
  const sent = page.waitForRequest((r) => r.method() === 'POST' && r.url().includes('/conversas/c1/mensagens'));
  await page.getByRole('button', { name: 'Enviar', exact: true }).click();
  expect((await sent).postDataJSON()).toEqual({ text: question, evidence_id: guideId });
  await expect(page.getByRole('status', { name: 'Andamento da consulta' })).toContainText('Lendo a guia');

  mock.messages.splice(1, 1, {
    ...userMsg, id: 'm-guide', operation_id: 'op2', text: question, status: 'answered',
    context: { evidence_id: guideId },
  }, {
    ...answerMsg, text: 'O pagamento não foi verificado.', citations: [],
    context: { guide_reading: guideFields },
  });
  mock.operations!.op2 = { operation_id: 'op2', status: 'succeeded', error: null, run: null };

  const reading = page.getByRole('region', { name: 'Dados lidos na guia' });
  await expect(reading).toContainText('10/2026');
  await expect(reading).toContainText('20/11/2026');
  await expect(reading).toContainText(/R\$\s81,05/);
  await expect(reading.getByRole('link', { name: 'Ver guia na tela Fiscal' }))
    .toHaveAttribute('href', '#fiscal?scope=obligations&evidence=' + guideId);

  await page.route('**/api/empresas/empresa-teste/tarefas', (route) => {
    expect(route.request().method()).toBe('POST');
    expect(route.request().postDataJSON()).toMatchObject({ source_message_id: answerMsg.id });
    return route.fulfill({ status: 201, json: { id: 'tarefa-da-guia' } });
  });
  await page.getByRole('button', { name: 'Transformar esta orientação em tarefa' }).click();
  await expect(page.locator('article a[href="#tarefas"]')).toBeVisible();
});

test('mantém a guia ao tentar novamente e preserva o chat por texto', async ({ page }) => {
  const calculation = { kind: 'mei', period: '2026-10', activity: 'services', conditions_confirmed: true };
  await openChat(page, {
    messages: [
      { ...userMsg, status: 'failed', context: { evidence_id: guideId, calculation_input: calculation } },
      {
        ...answerMsg, citations: [], context: {
          guide_reading: { evidence_id: guideId, period: null, due_date: null, amount: null },
        },
      },
    ],
    operations: {
      op1: { operation_id: 'op1', status: 'failed', error: 'agent_execution_failed',
        run: { status: 'failed', stages: [{ name: 'document', status: 'failed', attempts: 1, error: 'invalid_agent_result' }] } },
      op2: { operation_id: 'op2', status: 'succeeded', error: null, run: null },
    },
  });

  await page.route('**/api/empresas/empresa-teste/guias-para-assistente**', (route) =>
    route.fulfill({ json: { enabled: false, items: [], next_cursor: null } }));
  await expect(page.getByText('Envie uma imagem mais nítida para conferir os campos ilegíveis.')).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('A leitura da guia falhou.');

  const retried = page.waitForRequest((r) => r.method() === 'POST' && r.url().includes('/conversas/c1/mensagens'));
  await page.getByRole('button', { name: 'Tentar de novo' }).click();
  expect((await retried).postDataJSON()).toEqual({ text: userMsg.text, evidence_id: guideId, calculation });

  await page.getByRole('button', { name: 'Conferir uma guia' }).click();
  await expect(page.getByText('A leitura por imagem está indisponível.')).toBeVisible();
  const sent = page.waitForRequest((r) => r.method() === 'POST' && r.url().includes('/conversas/c1/mensagens'));
  await page.getByRole('button', { name: 'Perguntar sobre pagamento' }).click();
  expect((await sent).postDataJSON()).toEqual({ text: 'Paguei a guia da minha empresa?' });
});


test('limpa a guia selecionada ao trocar de empresa', async ({ page }) => {
  await openChat(page, { messages: [] });
  await page.route('**/api/empresas?*', (route) => route.fulfill({ json: {
    items: [company, { ...company, id: 'outra-empresa', cnpj: '11444777000161' }], next_cursor: null,
  } }));
  await page.route('**/api/empresas/outra-empresa/conversas?*', (route) =>
    route.fulfill({ json: { items: [], next_cursor: null } }));
  await page.route('**/api/empresas/empresa-teste/guias-para-assistente**', (route) =>
    route.fulfill({ json: {
      enabled: true, items: [{ id: guideId, period: '2026-10', created_at: '2026-11-20T12:00:00Z' }],
      next_cursor: null,
    } }));
  await page.route('**/api/empresas/outra-empresa/guias-para-assistente**', (route) =>
    route.fulfill({ json: { enabled: true, items: [], next_cursor: null } }));
  await page.reload();
  await page.getByRole('button', { name: 'Conferir uma guia' }).click();
  await page.getByLabel('Guia cadastrada').selectOption(guideId);
  await page.getByLabel('Empresa ativa').selectOption('outra-empresa');
  await expect(page.getByLabel('Guia cadastrada')).toHaveCount(0);
  await page.getByRole('button', { name: 'Conferir uma guia' }).click();
  await expect(page.getByText('Nenhuma guia em PNG ou JPEG.')).toBeVisible();
});


test('mostra a competência da pergunta e da guia antes de confirmar', async ({ page }) => {
  await openChat(page, { messages: [{
    ...userMsg, status: 'awaiting_data',
    context: { evidence_id: guideId, period: '2026-11', guide_reading: guideFields, missing_fields: ['period'] },
  }] });
  const confirmation = page.getByRole('form', { name: 'Confirmação de contexto' });
  await expect(confirmation).toContainText('A guia indica 10/2026. A pergunta indica 11/2026.');
  await expect(confirmation.getByLabel('Qual competência deseja consultar?')).toHaveValue('');
});
