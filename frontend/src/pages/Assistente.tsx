import { chatDraftKey } from '../services/chatDrafts';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import {
  ArrowUpRight,
  BookOpen,
  MessagesSquare,
  History,
  FileCheck2,
  ListChecks,
  Plus,
  Send,
} from 'lucide-react';
import { api } from '../services/api';
import { formatCnpj } from '../components/Sidebar';
import { Leitor } from './Leitor';
import type { Company, Page } from '../types';
import { citationHref, type Citation } from './assistente/citacoes';
import { AnswerText } from './assistente/AnswerText';
import { OperationProgress } from './assistente/OperationProgress';
import { FailedNotice } from './assistente/FailedNotice';
import { SLOW_AFTER_MS, type OperationDetail } from './assistente/operacao';

type Conversation = { id: string; title: string; company_id: string };
type Evidence = {
  kind: string;
  period?: string;
  valid_until?: string;
  created_at: string;
};
type Indicator = { latest_evidence: Evidence | null; evidence_state: string };
type Calculation = {
  reason?: string;
  references: string[];
  result?: {
    amount: string;
    rule_version: string;
    components: Record<string, string>;
    assumptions?: string[];
  };
};
type Message = {
  id: string;
  conversation_id: string;
  operation_id: string | null;
  role: string;
  text: string;
  status: string;
  citations: Citation[];
  next_steps: string[];
  context: {
    missing_fields?: string[];
    period?: string;
    regime?: string;
    company?: { regime: string; municipality: string; state: string };
    fiscal_status?: Partial<
      Record<'registration' | 'federal_certificate' | 'obligations', Indicator>
    >;
    calculation?: Calculation;
  };
};
type Payload = {
  text: string;
  calculation?: Record<string, unknown>;
  confirmation_for?: string;
  confirmation?: Record<string, string | boolean>;
};
// Every field the backend may request (MissingField in agents/contracts.py).
const MONEY_FIELDS: Record<string, string> = {
  revenue: 'Receita da competência (R$)',
  rbt12: 'Receita dos últimos 12 meses (R$)',
  payroll12: 'Folha dos últimos 12 meses (R$)',
};
const FIELD_NAMES: Record<string, string> = {
  period: 'competência',
  regime: 'regime',
  kind: 'tipo de simulação',
  revenue: 'receita da competência',
  rbt12: 'receita dos últimos 12 meses',
  payroll12: 'folha dos últimos 12 meses',
  activity: 'atividade',
};
type Operation = { operation_id: string; status: string };

async function allPages<T>(path: string, signal: AbortSignal) {
  const rows: T[] = [];
  let cursor: string | null = null;
  do {
    const query = new URLSearchParams({ limit: '100' });
    if (cursor) query.set('cursor', cursor);
    const page: Page<T> = await api.request(path + '?' + query, { signal });
    rows.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor);
  return rows;
}

function errorText(error: unknown) {
  return error instanceof Error
    ? error.message
    : 'Não foi possível acessar a API.';
}

function chatLink(id: string) {
  return '#assistente?' + new URLSearchParams({ conversa: id });
}

function localDate(value: string) {
  return new Date(
    value.length === 10 ? value + 'T12:00:00' : value,
  ).toLocaleDateString('pt-BR');
}

const scopeLabels = {
  registration: 'Cadastro',
  federal_certificate: 'Certidão federal',
  obligations: 'Obrigações',
};
const kindLabels: Record<string, string> = {
  guide: 'Guia',
  payment: 'Comprovante de pagamento',
  declaration: 'Declaração',
  registration: 'Documento cadastral',
  certificate: 'Certidão',
  other: 'Documento',
};

function Answer({
  message,
  companyId,
}: {
  message: Message;
  companyId: string;
}) {
  const [tasks, setTasks] = useState<Record<number, string>>({});
  const [taskError, setTaskError] = useState('');
  const { calculation, fiscal_status } = message.context;

  async function createTask(index: number) {
    setTaskError('');
    setTasks((previous) => ({ ...previous, [index]: 'saving' }));
    try {
      await api.request('/empresas/' + companyId + '/tarefas', {
        method: 'POST',
        body: JSON.stringify({
          source_message_id: message.id,
          source_step_index: index,
          period: message.context.period,
        }),
      });
      setTasks((previous) => ({ ...previous, [index]: 'saved' }));
    } catch (error) {
      setTasks((previous) => ({ ...previous, [index]: '' }));
      setTaskError(errorText(error));
    }
  }

  return (
    <>
      {message.citations.length > 0 && (
        <section className="space-y-2 border-t border-slate-200 pt-3">
          <h4 className="flex items-center gap-2 text-sm font-semibold">
            <BookOpen size={16} /> Fontes citadas
          </h4>
          {message.citations.map((source, index) => {
            const article =
              /^\s*(?:#+\s*)?(Art(?:igo)?\.?\s+\d+[º°o]?(?:[-–][\p{L}\d]+)?)/iu.exec(
                source.text,
              )?.[1];
            return (
              <a
                key={source.version_id + source.anchor_id}
                className="assistant-citation"
                href={citationHref(message.conversation_id, message.id, source)}
              >
                <BookOpen size={15} aria-hidden />
                <span>[{source.citation_index ?? index + 1}] {source.title}
                  {article && !source.title.toLowerCase().includes(article.toLowerCase()) && ' · ' + article}
                </span>
                <ArrowUpRight size={14} aria-hidden />
              </a>
            );
          })}
        </section>
      )}
      {calculation && (
        <section>
          <h4 className="font-semibold">Simulação fiscal</h4>
          {calculation.result && (
            <>
              <p>
                Valor simulado de R$ {calculation.result.amount} · Regra{' '}
                {calculation.result.rule_version}
              </p>
              <ul>
                {Object.entries(calculation.result.components).map(
                  ([tax, amount]) => (
                    <li key={tax}>
                      {tax.toUpperCase()} · R$ {amount}
                    </li>
                  ),
                )}
              </ul>
              {calculation.result.assumptions?.map((note) => (
                <p key={note}>{note}</p>
              ))}
            </>
          )}
          {calculation.references
            ?.filter((url) => /^https?:\/\//i.test(url))
            .map((url, i) => (
              <a
                key={url}
                className="block text-link underline"
                href={url}
                target="_blank"
                rel="noreferrer"
              >
                Referência da regra {i + 1}
              </a>
            ))}
        </section>
      )}
      {fiscal_status && (
        <details className="text-sm">
          <summary className="cursor-pointer font-semibold">
            Evidências consideradas
          </summary>
          <ul className="mt-2 space-y-2">
            {(Object.keys(scopeLabels) as (keyof typeof scopeLabels)[]).map(
              (scope) => {
                const indicator = fiscal_status[scope];
                if (!indicator) return null;
                const evidence = indicator.latest_evidence;
                return (
                  <li key={scope}>
                    <strong>{scopeLabels[scope]}</strong> · Verificação oficial
                    não realizada.
                    {evidence ? (
                      <span className="block">
                        {kindLabels[evidence.kind] || 'Documento'} de origem
                        declarada, registrado em{' '}
                        {localDate(evidence.created_at)}.
                        {evidence.period &&
                          ' Competência ' + evidence.period + '.'}
                        {evidence.valid_until &&
                          ' Validade até ' +
                            localDate(evidence.valid_until) +
                            '.'}
                        {indicator.evidence_state === 'expired' &&
                          ' Evidência vencida.'}
                      </span>
                    ) : (
                      ' Sem evidência registrada.'
                    )}
                  </li>
                );
              },
            )}
          </ul>
        </details>
      )}
      {message.next_steps.length > 0 && (
        <section className="space-y-2">
          <h4 className="font-semibold">Próximos passos</h4>
          <ol className="assistant-steps">
            {message.next_steps.slice(0, 3).map((step, index) => (
              <li key={index}>
                <span>{step}</span>
                {tasks[index] === 'saved' ? (
                  <a className="text-link underline" href="#tarefas">
                    Ver em Tarefas
                  </a>
                ) : (
                  <button
                    type="button"
                    className="text-sm font-semibold text-link underline"
                    disabled={tasks[index] === 'saving'}
                    onClick={() => createTask(index)}
                  >
                    {tasks[index] === 'saving'
                      ? 'Criando tarefa…'
                      : 'Criar tarefa'}
                  </button>
                )}
              </li>
            ))}
          </ol>
          {taskError && <p role="alert">{taskError}</p>}
        </section>
      )}
      <p className="border-t border-slate-200 pt-2 text-xs text-slate-600">
        Orientação informativa. Valide decisões fiscais e a escrituração com um
        profissional registrado no CRC.
      </p>
    </>
  );
}

function Confirmation({
  message,
  send,
  busy,
}: {
  message: Message;
  send: (payload: Payload) => void;
  busy: boolean;
}) {
  const fields = message.context.missing_fields ?? [];
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!message.operation_id) return;
    const data = new FormData(event.currentTarget);
    const confirmation: Record<string, string | boolean> = {};
    for (const field of fields) {
      if (field === 'conditions_confirmed') {
        confirmation[field] = data.has(field);
        continue;
      }
      const value = String(data.get(field) ?? '').trim();
      if (!value) return;
      // Money goes as a decimal string; the backend rejects floats.
      confirmation[field] = field in MONEY_FIELDS ? value.replace(',', '.') : value;
    }
    const description = fields
      .filter((field) => field !== 'conditions_confirmed')
      .map((field) => (FIELD_NAMES[field] ?? field) + ' ' + confirmation[field])
      .join(', ');
    send({
      text: description ? 'Confirmo ' + description + '.' : 'Confirmo as condições informadas.',
      confirmation_for: message.operation_id,
      confirmation,
    });
  }
  return (
    <form
      className="space-y-3 rounded-xl border border-accent bg-notice p-4"
      onSubmit={submit}
    >
      <h3 className="font-semibold text-ink">Confirmação de contexto</h3>
      {fields.includes('period') && (
        <label className="block text-sm">
          Qual competência deseja consultar?
          <input type="month" name="period" required className="field" />
        </label>
      )}
      {fields.includes('regime') && (
        <label className="block text-sm">
          Qual é o regime da empresa?
          <input
            name="regime"
            required
            maxLength={40}
            defaultValue={message.context.company?.regime}
            className="field"
          />
        </label>
      )}
      {fields.includes('kind') && (
        <label className="block text-sm">
          Qual simulação deseja fazer?
          <select name="kind" required className="field">
            <option value="mei">MEI</option>
            <option value="simples">Simples Nacional</option>
          </select>
        </label>
      )}
      {fields.includes('activity') && (
        <label className="block text-sm">
          Qual é a atividade da empresa?
          <select name="activity" required className="field">
            <option value="trade">Comércio</option>
            <option value="services">Serviços</option>
            <option value="mixed">Comércio e serviços</option>
          </select>
        </label>
      )}
      {Object.entries(MONEY_FIELDS)
        .filter(([name]) => fields.includes(name))
        .map(([name, label]) => (
          <label key={name} className="block text-sm">
            {label}
            <input
              name={name}
              required
              className="field"
              inputMode="decimal"
              pattern="[0-9]+([.,][0-9]{1,2})?"
              placeholder="0,00"
            />
          </label>
        ))}
      {fields
        .filter((field) => !(field in FIELD_NAMES) && field !== 'conditions_confirmed')
        .map((field) => (
          <label key={field} className="block text-sm">
            {field}
            <input name={field} required maxLength={200} className="field" />
          </label>
        ))}
      {fields.includes('conditions_confirmed') && (
        <label className="block text-sm">
          <input type="checkbox" name="conditions_confirmed" required /> Confirmo os
          dados e condições informados para esta simulação.
        </label>
      )}
      <button className="primary" disabled={busy}>
        Confirmar contexto
      </button>
    </form>
  );
}

function Composer({
  send,
  busy,
  draft,
  setDraft,
}: {
  send: (payload: Payload) => void;
  busy: boolean;
  draft: string;
  setDraft: (text: string) => void;
}) {
  const [kind, setKind] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const submitRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport || kind) return;
    function keepSendVisible() {
      if (!viewport || viewport.width > 800 || viewport.height > 600 ||
          document.activeElement !== inputRef.current) return;
      const bottom = submitRef.current?.getBoundingClientRect().bottom;
      if (bottom === undefined) return;
      const overflow = bottom + 12 - (viewport.offsetTop + viewport.height);
      if (overflow > 0) window.scrollBy(0, overflow);
    }
    viewport.addEventListener('resize', keepSendVisible);
    return () => viewport.removeEventListener('resize', keepSendVisible);
  }, [kind]);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    if (!kind) {
      if (draft.trim()) send({ text: draft.trim() });
      return;
    }
    const period = String(data.get('period'));
    const calculation: Record<string, unknown> = {
      kind,
      period,
      conditions_confirmed: data.has('conditions_confirmed'),
    };
    if (kind === 'mei') calculation.activity = data.get('activity');
    else
      for (const name of ['rbt12', 'revenue', 'payroll12']) {
        const value = data.get(name);
        if (value) calculation[name] = String(value).replace(',', '.');
      }
    send({
      text:
        draft.trim() ||
        'Simular ' +
          (kind === 'mei' ? 'MEI' : 'Simples Nacional') +
          ' para ' +
          period,
      calculation,
    });
  }
  return (
    <form
      className="assistant-composer"
      onSubmit={submit}
    >
      <fieldset disabled={busy} className="space-y-3">
        <label className="sr-only" htmlFor="chat-question">
          Mensagem
        </label>
        <textarea
          ref={inputRef}
          id="chat-question"
          className="composer-input"
          rows={3}
          placeholder="Digite sua pergunta"
          maxLength={2000}
          required={!kind}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        {kind && (
          <div className="grid gap-3 rounded-lg bg-slate-50 p-3 text-sm sm:grid-cols-2">
            <label>
              Regime da simulação
              <select
                className="field"
                value={kind}
                onChange={(event) => setKind(event.target.value)}
              >
                <option value="mei">MEI</option>
                <option value="simples">Simples Nacional</option>
              </select>
            </label>
            <label>
              Competência
              <input className="field" type="month" name="period" required />
            </label>
            {kind === 'mei' ? (
              <label>
                Atividade
                <select className="field" name="activity">
                  <option value="trade">Comércio</option>
                  <option value="services">Serviços</option>
                  <option value="mixed">Comércio e serviços</option>
                </select>
              </label>
            ) : (
              <>
                {[
                  ['rbt12', 'Receita dos últimos 12 meses (R$)'],
                  ['revenue', 'Receita da competência (R$)'],
                  [
                    'payroll12',
                    'Folha dos últimos 12 meses (R$, se aplicável)',
                  ],
                ].map(([name, label]) => (
                  <label key={name}>
                    {label}
                    <input
                      name={name}
                      className="field"
                      required={name !== 'payroll12'}
                      inputMode="decimal"
                      pattern="[0-9]+([.,][0-9]{1,2})?"
                      placeholder="0,00"
                    />
                  </label>
                ))}
              </>
            )}
            <label className="sm:col-span-2">
              <input type="checkbox" name="conditions_confirmed" required />{' '}
              Confirmo os dados e condições informados para esta simulação.
            </label>
          </div>
        )}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <button
            type="button"
            className="text-sm font-medium text-link underline"
            onClick={() => setKind(kind ? '' : 'mei')}
          >
            {kind ? 'Cancelar simulação' : 'Simular cálculo fiscal'}
          </button>
          <button
            className="primary"
            ref={submitRef}
            disabled={busy || (!draft.trim() && !kind)}
          >
            <Send size={15} /> Enviar
          </button>
        </div>
      </fieldset>
    </form>
  );
}

type ChatProps = {
  accountId: string;
  companyId: string;
  conversation?: Conversation;
  messageId: string | null;
  onCreated: (conversation: Conversation) => void;
};

function Chat({ accountId, companyId, conversation, messageId, onCreated }: ChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [reload, setReload] = useState(0);
  const [loading, setLoading] = useState(!!conversation);
  const [sending, setSending] = useState(false);
  const draftKey = chatDraftKey(accountId, companyId, conversation?.id);
  const [draft, updateDraft] = useState(() => sessionStorage.getItem(draftKey) || '');
  function setDraft(text: string) {
    if (text) sessionStorage.setItem(draftKey, text);
    else sessionStorage.removeItem(draftKey);
    updateDraft(text);
  }
  const [readError, setReadError] = useState('');
  const [sendError, setSendError] = useState('');
  const [reviewKey, setReviewKey] = useState(0);
  const [pollError, setPollError] = useState('');
  const [explicitOperation, setExplicitOperation] = useState<Operation | null>(
    null,
  );
  const requestRef = useRef<{ body: string; key: string } | null>(null);
  const newChat = useRef<Conversation>();
  const lifetime = useRef<AbortController>();
  const threadEnd = useRef<HTMLDivElement>(null);
  const highlighted = useRef<string>();
  const path = conversation
    ? '/conversas/' + encodeURIComponent(conversation.id) + '/mensagens'
    : '';
  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    setLoading(true);
    setReadError('');
    allPages<Message>(path, controller.signal)
      .then((rows) => {
        if (controller.signal.aborted) return;
        setMessages(rows);
        setExplicitOperation(null);
      })
      .catch((error) => {
        if (!controller.signal.aborted) setReadError(errorText(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [path, reload]);

  const outstanding = messages.find(
    (message) =>
      message.role === 'user' &&
      ['awaiting_data', 'queued', 'running'].includes(message.status),
  );
  const operationId =
    explicitOperation?.operation_id ?? outstanding?.operation_id;
  const operationStatus = explicitOperation?.status ?? outstanding?.status;
  const [operation, setOperation] = useState<OperationDetail | null>(null);
  const [waitStart, setWaitStart] = useState(() => Date.now());
  const [stopped, setStopped] = useState<string | null>(null);
  const watching = !!operationId && operationId !== stopped;
  useEffect(() => {
    setOperation(null);
    setWaitStart(Date.now());
  }, [operationId]);
  useEffect(() => {
    if (!watching || !['queued', 'running'].includes(operationStatus ?? ''))
      return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    setPollError('');
    async function poll() {
      try {
        const op = await api.request<OperationDetail>('/operacoes/' + operationId, {
          signal: controller.signal,
        });
        if (controller.signal.aborted) return;
        setOperation(op);
        if (['queued', 'running'].includes(op.status))
          timer = setTimeout(poll, 1600);
        else setReload((value) => value + 1);
      } catch (error) {
        if (!controller.signal.aborted) setPollError(errorText(error));
      }
    }
    timer = setTimeout(poll, 350);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [watching, operationId, operationStatus, reviewKey]);

  useEffect(() => {
    if (loading || !messages.length) return;
    if (messageId) {
      if (highlighted.current !== messageId) {
        const element = document.getElementById('chat-message-' + messageId);
        if (element) {
          element.scrollIntoView({ block: 'center' });
          highlighted.current = messageId;
        }
      }
    } else {
      highlighted.current = undefined;
      threadEnd.current?.scrollIntoView({ block: 'nearest' });
    }
  }, [messages, messageId, loading]);

  async function send(payload: Payload) {
    const signal = lifetime.current?.signal;
    if (sending || !signal || signal.aborted) return;
    setSending(true);
    setSendError('');
    try {
      let target = conversation ?? newChat.current;
      if (!target) {
        target = await api.request<Conversation>(
          '/empresas/' + companyId + '/conversas',
          {
            method: 'POST',
            signal,
            body: JSON.stringify({ title: payload.text.slice(0, 120) }),
          },
        );
        if (signal.aborted) return;
        newChat.current = target;
        onCreated(target);
      }
      const body = JSON.stringify(payload);
      if (requestRef.current?.body !== body)
        requestRef.current = { body, key: crypto.randomUUID() };
      const receipt = await api.request<Operation>(
        '/conversas/' + target.id + '/mensagens',
        {
          method: 'POST',
          signal,
          headers: { 'Idempotency-Key': requestRef.current.key },
          body,
        },
      );
      if (signal.aborted) return;
      requestRef.current = null;
      setDraft('');
      if (!conversation) window.location.hash = chatLink(target.id);
      else {
        setExplicitOperation(receipt);
        setLoading(true);
        setReload((value) => value + 1);
      }
    } catch (error) {
      if (!signal.aborted) setSendError(errorText(error));
    } finally {
      if (!signal.aborted) setSending(false);
    }
  }

  const welcome = !loading && !readError && !messages.length;
  const period = messages.at(-1)?.context.period;
  const busy = sending || loading || watching || !!readError;
  // Re-evaluated on every poll response, which re-renders the thread.
  const slow = Date.now() - waitStart > SLOW_AFTER_MS;
  return (
    <section className={'assistant-thread' + (welcome ? ' is-welcome' : '')}>
      {welcome && (
        <header className="assistant-welcome">
          <span className="assistant-symbol"><MessagesSquare size={26} aria-hidden /></span>
          <h2>O que você precisa resolver hoje?</h2>
        </header>
      )}
      {conversation && <header className="border-b border-slate-200 pb-3">
        <h2 className="break-words text-lg font-semibold">
          {conversation.title}
        </h2>
        {period && <p className="text-sm text-slate-600">Competência · {period}</p>}
      </header>}
      {readError && (
        <p className="notice" role="alert">
          {readError}{' '}
          <button
            className="underline"
            onClick={() => setReload((value) => value + 1)}
          >
            Recarregar mensagens
          </button>
        </p>
      )}
      <div
        hidden={welcome && !messageId}
        className="assistant-messages space-y-4"
        aria-label="Mensagens da conversa"
      >
        {messages.map((message) => (
          <div
            key={message.id}
            id={'chat-message-' + message.id}
            className="space-y-2"
          >
            <article
              className={
                'w-fit max-w-[95%] space-y-3 break-words rounded-xl p-4 text-sm ' +
                (message.role === 'user'
                  ? 'ml-auto bg-slate-900 text-white'
                  : 'border border-slate-200 bg-white text-slate-800') +
                (message.id === messageId ? ' ring-2 ring-focus' : '')
              }
            >
              <h3 className="font-semibold">
                {message.role === 'user' ? 'Você' : 'Assistente fiscal'}
              </h3>
              {message.role === 'assistant' ? (
                <AnswerText
                  text={message.text}
                  citations={message.citations}
                  conversationId={message.conversation_id}
                  messageId={message.id}
                />
              ) : (
                <p className="message-copy whitespace-pre-wrap">{message.text}</p>
              )}
              {message.role === 'assistant' && (
                <Answer message={message} companyId={companyId} />
              )}
            </article>
            {message.status === 'failed' && (
              <FailedNotice
                operationId={message.operation_id}
                busy={busy}
                onRetry={() => send({ text: message.text })}
                onCopy={() => setDraft(message.text)}
              />
            )}
            {outstanding?.id === message.id &&
              operationStatus === 'awaiting_data' && (
                <Confirmation
                  message={message}
                  send={send}
                  busy={sending || loading}
                />
              )}
          </div>
        ))}
        {!loading &&
          !readError &&
          messageId &&
          !messages.some((message) => message.id === messageId) && (
            <p className="notice">A mensagem de origem está indisponível.</p>
          )}
        {loading && (
          <p className="text-sm text-slate-600" role="status">
            Carregando mensagens…
          </p>
        )}
        {!pollError &&
          watching &&
          ['queued', 'running'].includes(operationStatus ?? '') && (
            <OperationProgress
              operation={operation}
              slow={slow}
              onKeepWaiting={() => setWaitStart(Date.now())}
              onStopWaiting={() => setStopped(operationId ?? null)}
            />
          )}
        {stopped && stopped === operationId && (
          <p className="notice" role="status">
            Você parou de acompanhar esta consulta. Se a resposta ficar pronta, ela aparece aqui.{' '}
            <button className="underline" onClick={() => setReload((value) => value + 1)}>
              Recarregar
            </button>
          </p>
        )}
        {pollError && (
          <p className="notice" role="alert">
            {pollError}{' '}
            <button
              className="underline"
              onClick={() => setReviewKey((value) => value + 1)}
            >
              Verificar operação novamente
            </button>
          </p>
        )}
        <div ref={threadEnd} />
      </div>
      {sendError && (
        <p className="notice" role="alert">
          {sendError}
        </p>
      )}
      <Composer
        key={reload}
        send={send}
        busy={busy}
        draft={draft}
        setDraft={setDraft}
      />
      {welcome && (
            <div className="assistant-choices">
              <button type="button" onClick={() => send({ text: 'Paguei a guia da minha empresa?' })} disabled={busy}><FileCheck2 /> Conferir uma guia</button>
              <button type="button" onClick={() => { setDraft('Quero entender a regra sobre '); document.getElementById('chat-question')?.focus(); }}><BookOpen /> Entender uma regra</button>
              <a href="#tarefas"><ListChecks /> Consultar minhas tarefas</a>
            </div>
      )}
    </section>
  );
}

function CompanyAssistant({
  accountId,
  company,
  params,
}: {
  accountId: string;
  company: Company;
  params: URLSearchParams;
}) {
  const companyId = company.id;
  const id = params.get('conversa');
  const reading = !!(id && params.get('version_id') && params.get('document_id'));
  const [history, setHistory] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    allPages<Conversation>(
      '/empresas/' + companyId + '/conversas',
      controller.signal,
    )
      .then((rows) => {
        if (!controller.signal.aborted)
          setHistory((current) => [
            ...current.filter(
              (chat) => !rows.some((row) => row.id === chat.id),
            ),
            ...rows.reverse(),
          ]);
      })
      .catch((reason) => {
        if (!controller.signal.aborted) setError(errorText(reason));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [companyId, revision]);
  const selected = history.find((conversation) => conversation.id === id);
  const resumeKey = 'ultima-conversa:' + companyId;
  useEffect(() => {
    if (selected) sessionStorage.setItem(resumeKey, selected.id);
  }, [resumeKey, selected]);
  const lastVisited = sessionStorage.getItem(resumeKey);
  const recent = history.find((chat) => chat.id === lastVisited) ?? history[0];
  return (
    <div className={'assistant-layout' + (reading && selected ? ' with-reader' : '')}>
      <div className="assistant-main">
        <header className="assistant-heading">
          <div><h1>Assistente fiscal</h1><p><span className="assistant-company-id">{formatCnpj(company.cnpj)} · </span>{company.regime} · {company.municipality}/{company.state}</p></div>
          {id && <a className="secondary" href="#assistente"><Plus size={16} /> Nova pergunta</a>}
        </header>
        <div className="assistant-tools">
          {!id && recent && <a className="assistant-resume" href={chatLink(recent.id)}>Continuar de onde parei <ArrowUpRight size={16} /></a>}
          <details className="assistant-history" key={id || 'inicio'}>
            <summary><History size={16} /> Histórico de conversas</summary>
          {loading && <p role="status">Carregando conversas…</p>}
          {error && (
            <p className="notice" role="alert">
              {error}{' '}
              <button
                className="underline"
                onClick={() => setRevision((value) => value + 1)}
              >
                Tentar novamente
              </button>
            </p>
          )}
          {!loading && !error && !history.length && (
            <p className="text-sm text-slate-500">Nenhuma conversa salva.</p>
          )}
          <nav
            className="max-h-60 space-y-1 overflow-auto lg:max-h-[58vh]"
            aria-label="Histórico de conversas"
          >
            {history.map((chat) => (
              <a
                key={chat.id}
                href={chatLink(chat.id)}
                aria-current={chat.id === id ? 'page' : undefined}
                className={
                  'block break-words rounded-lg px-3 py-2 text-sm hover:bg-slate-100 ' +
                  (chat.id === id
                    ? 'bg-info font-semibold text-ink'
                    : 'text-slate-700')
                }
              >
                <span className="line-clamp-2">{chat.title}</span>
              </a>
            ))}
          </nav>
          </details>
        </div>
        {!id || selected ? (
          <Chat
            key={id ?? 'new'}
            accountId={accountId}
            companyId={companyId}
            conversation={selected}
            messageId={reading ? null : params.get('mensagem')}
            onCreated={(chat) =>
              setHistory((current) => [
                chat,
                ...current.filter((item) => item.id !== chat.id),
              ])
            }
          />
        ) : (
          <p className="panel" role="status">
            {loading
              ? 'Carregando conversa…'
              : error
                ? 'Histórico indisponível.'
                : 'Conversa indisponível para a empresa selecionada.'}
          </p>
        )}
      </div>
      {reading && selected && <aside className="assistant-reader" aria-label="Norma citada"><Leitor params={params} /></aside>}
    </div>
  );
}

export function Assistente(props: {
  accountId: string;
  company: Company;
  params: URLSearchParams;
}) {
  return <CompanyAssistant key={props.company.id} {...props} />;
}
