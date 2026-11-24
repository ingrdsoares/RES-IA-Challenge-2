import { chatDraftKey } from '../services/chatDrafts';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import {
  ArrowUpRight,
  BookOpen,
  Check,
  CheckCircle2,
  Download,
  FileCheck2,
  History,
  ListChecks,
  MessagesSquare,
  Plus,
  Search,
  Send,
  ThumbsDown,
  ThumbsUp,
} from 'lucide-react';
import { api } from '../services/api';
import { formatCnpj } from '../components/Sidebar';
import { Leitor } from './Leitor';
import type { Company, Page } from '../types';
import { citationHref, type Citation } from './assistente/citacoes';
import { AnswerText } from './assistente/AnswerText';
import { OperationProgress } from './assistente/OperationProgress';
import { FailedNotice } from './assistente/FailedNotice';
import { GuidePicker } from './assistente/GuidePicker';
import { GuideReadingCard, guideHref, type GuideReading } from './assistente/GuideReading';
import { suggestions } from './Empresas';
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
    evidence_id?: string;
    guide_reading?: GuideReading;
    guide_retry_calculation?: Record<string, unknown>;
    calculation_input?: Record<string, unknown>;
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
  evidence_id?: string;
  confirmation_for?: string;
  confirmation?: Record<string, string | boolean>;
};
// Every field the backend may request (MissingField in agents/contracts.py).
const MONEY_FIELDS: Record<string, string> = {
  revenue: 'Receita da competência (R$)',
  rbt12: 'Receita dos últimos 12 meses (R$)',
  payroll12: 'Folha dos últimos 12 meses (R$)',
};
const MONEY_PATTERN = /^[0-9]+([.,][0-9]{1,2})?$/;
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

const FEEDBACK_REASONS = [
  { id: 'incorreta', label: 'Informação incorreta' },
  { id: 'incompleta', label: 'Resposta incompleta' },
  { id: 'desatualizada', label: 'Regra desatualizada' },
  { id: 'sem_fonte', label: 'Sem citação da lei' },
  { id: 'confusa', label: 'Difícil de entender' },
  { id: 'outro', label: 'Outro motivo' },
] as const;

function FeedbackWidget({ message }: { message: Message }) {
  const [showReasons, setShowReasons] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function sendFeedback(useful: boolean, reason?: string) {
    setSubmitting(true);
    try {
      await api
        .request('/rag/feedback', {
          method: 'POST',
          body: JSON.stringify({
            request_id: message.operation_id || message.id,
            useful,
            reason: reason || null,
          }),
        })
        .catch(() => {});
      setSubmitted(true);
      setShowReasons(false);
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div className="flex items-center gap-1.5 pt-2 text-xs text-ink-muted">
        <Check size={14} className="text-link" />
        <span>Obrigado pela sua avaliação!</span>
      </div>
    );
  }

  return (
    <div className="border-t border-slate-200 pt-2 text-xs">
      <div className="flex flex-wrap items-center gap-2 text-slate-500">
        <span>Esta orientação foi útil?</span>
        <button
          type="button"
          disabled={submitting}
          onClick={() => sendFeedback(true)}
          className="inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-700 hover:bg-slate-200 disabled:opacity-50"
          title="Sim, foi útil"
        >
          <ThumbsUp size={12} /> Sim
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={() => setShowReasons(true)}
          className="inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-700 hover:bg-slate-200 disabled:opacity-50"
          title="Não foi útil"
        >
          <ThumbsDown size={12} /> Não
        </button>
      </div>
      {showReasons && (
        <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-2 text-xs space-y-1.5">
          <p className="font-semibold text-slate-700">Por que não ajudou?</p>
          <div className="flex flex-wrap gap-1">
            {FEEDBACK_REASONS.map((r) => (
              <button
                key={r.id}
                type="button"
                disabled={submitting}
                onClick={() => sendFeedback(false, r.id)}
                className="rounded border border-slate-300 bg-white px-2 py-0.5 text-slate-600 hover:bg-slate-100 disabled:opacity-50"
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Answer({
  message,
  companyId,
}: {
  message: Message;
  companyId: string;
}) {
  const [tasks, setTasks] = useState<Record<number, string>>({});
  const [taskError, setTaskError] = useState('');
  const [wholeTaskState, setWholeTaskState] = useState<'idle' | 'saving' | 'saved'>('idle');
  const { calculation, fiscal_status, guide_reading } = message.context;

  async function createWholeTask() {
    setTaskError('');
    setWholeTaskState('saving');
    try {
      const firstLine = message.text.split('\n')[0].replace(/^#+\s*/, '').trim();
      const title = firstLine.length > 5 ? firstLine.slice(0, 140) : 'Orientação fiscal do assistente';
      await api.request('/empresas/' + companyId + '/tarefas', {
        method: 'POST',
        body: JSON.stringify({
          title,
          source_message_id: message.id,
          period: message.context.period || null,
        }),
      });
      setWholeTaskState('saved');
    } catch (error) {
      setWholeTaskState('idle');
      setTaskError(errorText(error));
    }
  }

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
      {guide_reading && <GuideReadingCard reading={guide_reading} />}
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
      {message.next_steps.length === 0 && (
        <div className="pt-1">
          {wholeTaskState === 'saved' ? (
            <a
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-link underline"
              href="#tarefas"
            >
              <Check size={14} /> Tarefa criada · Ver em Tarefas
            </a>
          ) : (
            <button
              type="button"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-link hover:underline"
              disabled={wholeTaskState === 'saving'}
              onClick={createWholeTask}
            >
              <Plus size={14} />
              {wholeTaskState === 'saving'
                ? 'Criando tarefa…'
                : 'Transformar esta orientação em tarefa'}
            </button>
          )}
          {taskError && <p role="alert">{taskError}</p>}
        </div>
      )}
      <FeedbackWidget message={message} />
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
  const [missing, setMissing] = useState('');
  const formRef = useRef<HTMLFormElement>(null);
  useEffect(() => {
    formRef.current?.querySelector<HTMLElement>('input, select')?.focus();
  }, []);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!message.operation_id) return;
    const data = new FormData(event.currentTarget);
    const confirmation: Record<string, string | boolean> = {};
    const empty: string[] = [];
    const malformed: string[] = [];
    for (const field of fields) {
      if (field === 'conditions_confirmed') {
        if (!data.has(field)) empty.push('confirmação das condições');
        confirmation[field] = data.has(field);
        continue;
      }
      const value = String(data.get(field) ?? '').trim();
      if (!value) {
        empty.push(FIELD_NAMES[field] ?? field.replace(/_/g, ' '));
        continue;
      }
      // noValidate disables the input pattern, so money is checked here: "1.500"
      // would otherwise reach the backend as R$ 1,50.
      if (field in MONEY_FIELDS && !MONEY_PATTERN.test(value)) {
        malformed.push(FIELD_NAMES[field]);
        continue;
      }
      // Money goes as a decimal string; the backend rejects floats.
      confirmation[field] = field in MONEY_FIELDS ? value.replace(',', '.') : value;
    }
    if (empty.length) {
      setMissing('Preencha: ' + empty.join(', ') + '.');
      return;
    }
    if (malformed.length) {
      setMissing('Corrija: ' + malformed.join(', ') + ' (use o formato 1500,00).');
      return;
    }
    setMissing('');
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
      ref={formRef}
      noValidate
      aria-labelledby={'confirmacao-' + message.id}
      className="space-y-3 rounded-xl border border-accent bg-notice p-4"
      onSubmit={submit}
    >
      <h3 id={'confirmacao-' + message.id} className="font-semibold text-ink">
        Confirmação de contexto
      </h3>
      {fields.includes('period') && (
        <>
          {message.context.guide_reading && (
            <p className="text-sm">
              {message.context.guide_reading.period
                ? 'A guia indica ' + message.context.guide_reading.period.split('-').reverse().join('/') + '.'
                : 'A competência da guia está ilegível ou ausente.'}
              {message.context.period && message.context.period !== message.context.guide_reading.period &&
                ' A pergunta indica ' + message.context.period.split('-').reverse().join('/') + '.'}
            </p>
          )}
          <label className="block text-sm">
            Qual competência deseja consultar?
            <input type="month" name="period" required className="field" />
          </label>
        </>
      )}
      {fields.includes('regime') && (
        <label className="block text-sm">
          Qual é o regime da empresa?
          <select
            name="regime"
            required
            defaultValue={
              suggestions.regime.includes(message.context.company?.regime ?? '')
                ? message.context.company?.regime
                : ''
            }
            className="field"
          >
            <option value="">Selecione…</option>
            {suggestions.regime.map((regime) => (
              <option key={regime}>{regime}</option>
            ))}
          </select>
        </label>
      )}
      {fields.includes('kind') && (
        <label className="block text-sm">
          Qual simulação deseja fazer?
          <select name="kind" required defaultValue="" className="field">
            <option value="">Selecione…</option>
            <option value="mei">MEI</option>
            <option value="simples">Simples Nacional</option>
          </select>
        </label>
      )}
      {fields.includes('activity') && (
        <label className="block text-sm">
          Qual é a atividade da empresa?
          <select name="activity" required defaultValue="" className="field">
            <option value="">Selecione…</option>
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
            Informe {field.replace(/_/g, ' ')}
            <input name={field} required maxLength={200} className="field" />
          </label>
        ))}
      {fields.includes('conditions_confirmed') && (
        <label className="block text-sm">
          <input type="checkbox" name="conditions_confirmed" required /> Confirmo os
          dados e condições informados para esta simulação.
        </label>
      )}
      {missing && <p role="alert">{missing}</p>}
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
  guideId,
}: {
  send: (payload: Payload) => void;
  busy: boolean;
  draft: string;
  setDraft: (text: string) => void;
  guideId: string;
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
      if (draft.trim()) send({ text: draft.trim(), evidence_id: guideId || undefined });
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
      evidence_id: guideId || undefined,
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
  const [guideOpen, setGuideOpen] = useState(false);
  const [guideId, setGuideId] = useState('');
  function closeGuide() {
    setGuideId('');
    setGuideOpen(false);
  }
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

  // Operations the user stopped following; they never become the tracked one again.
  const [stopped, setStopped] = useState<string[]>([]);
  const outstanding = messages.find(
    (message) =>
      message.role === 'user' &&
      ['awaiting_data', 'queued', 'running'].includes(message.status) &&
      !stopped.includes(message.operation_id ?? ''),
  );
  const operationId =
    explicitOperation?.operation_id ?? outstanding?.operation_id;
  const operationStatus = explicitOperation?.status ?? outstanding?.status;
  const [operation, setOperation] = useState<OperationDetail | null>(null);
  const [waitKey, setWaitKey] = useState(0);
  const [slow, setSlow] = useState(false);
  const watching = !!operationId;
  useEffect(() => {
    setOperation(null);
  }, [operationId]);
  // A timer, not a render-time check, so the warning shows even if polling hangs.
  useEffect(() => {
    setSlow(false);
    if (!watching) return;
    const timer = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => clearTimeout(timer);
  }, [watching, operationId, waitKey]);
  const stopWaiting = () => {
    if (operationId) setStopped((ids) => [...ids, operationId]);
    setExplicitOperation(null);
  };
  const stoppedPending =
    !watching &&
    messages.some(
      (message) =>
        stopped.includes(message.operation_id ?? '') &&
        ['queued', 'running'].includes(message.status),
    );
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
      closeGuide();
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

  function exportChat() {
    if (!messages.length) return;
    const title = conversation?.title || 'conversa-fiscal';
    const dateStr = new Date().toLocaleDateString('pt-BR');
    let md = `# Sócio Digital - Consulta Fiscal\n\n`;
    md += `**Título:** ${title}\n`;
    md += `**Data da consulta:** ${dateStr}\n\n`;
    md += `---\n\n`;
    for (const m of messages) {
      const role = m.role === 'user' ? 'Você (Empresa)' : 'Assistente Fiscal';
      md += `### ${role}\n\n${m.text}\n\n`;
      if (m.citations && m.citations.length > 0) {
        md += `**Fontes citadas:**\n`;
        for (const c of m.citations) {
          md += `- [${c.title}](${c.official_url || '#'}): ${c.text.slice(0, 140)}...\n`;
        }
        md += `\n`;
      }
      if (m.next_steps && m.next_steps.length > 0) {
        md += `**Próximos passos recomendados:**\n`;
        for (const s of m.next_steps) {
          md += `1. ${s}\n`;
        }
        md += `\n`;
      }
      md += `---\n\n`;
    }
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${title.toLowerCase().replace(/[^a-z0-9]/g, '-') || 'conversa'}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const welcome = !loading && !readError && !messages.length;
  const period = messages.at(-1)?.context.period;
  const busy = sending || loading || watching || !!readError;
  return (
    <section className={'assistant-thread' + (welcome ? ' is-welcome' : '')}>
      {welcome && (
        <header className="assistant-welcome">
          <span className="assistant-symbol"><MessagesSquare size={26} aria-hidden /></span>
          <h2>O que você precisa resolver hoje?</h2>
        </header>
      )}
      {conversation && (
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3">
          <div>
            <h2 className="break-words text-lg font-semibold">
              {conversation.title}
            </h2>
            {period && <p className="text-sm text-slate-600">Competência · {period}</p>}
          </div>
          {messages.length > 0 && (
            <button
              type="button"
              onClick={exportChat}
              className="secondary inline-flex items-center gap-1.5 py-1 px-2.5 text-xs font-semibold"
              title="Baixar conversa em arquivo Markdown"
            >
              <Download size={14} /> Exportar conversa (.md)
            </button>
          )}
        </header>
      )}
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
                <>
                  <p className="message-copy whitespace-pre-wrap">{message.text}</p>
                  {message.context.evidence_id && (
                    <a className="underline" href={guideHref(message.context.evidence_id)}>Guia anexada</a>
                  )}
                </>
              )}
              {message.role === 'assistant' && (
                <Answer message={message} companyId={companyId} />
              )}
            </article>
            {message.status === 'failed' && (
              <FailedNotice
                operationId={message.operation_id}
                busy={busy}
                onRetry={() => send({
                  text: message.text,
                  evidence_id: message.context.evidence_id,
                  calculation: message.context.guide_retry_calculation ?? message.context.calculation_input,
                })}
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
              onKeepWaiting={() => setWaitKey((value) => value + 1)}
              onStopWaiting={stopWaiting}
            />
          )}
        {stoppedPending && (
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
            </button>{' '}
            {watching && (
              <button
                className="underline"
                onClick={() => {
                  setPollError('');
                  stopWaiting();
                }}
              >
                Parar de aguardar
              </button>
            )}
          </p>
        )}
        <div ref={threadEnd} />
      </div>
      {sendError && (
        <p className="notice" role="alert">
          {sendError}
        </p>
      )}
      {guideOpen && (
        <GuidePicker
          companyId={companyId}
          selectedId={guideId}
          onSelect={setGuideId}
          onClose={closeGuide}
          onAskPayment={() => send({ text: 'Paguei a guia da minha empresa?', evidence_id: guideId || undefined })}
          disabled={busy}
        />
      )}
      <Composer
        key={reload}
        send={send}
        busy={busy}
        draft={draft}
        setDraft={setDraft}
        guideId={guideId}
      />
      {!welcome && !guideOpen && (
        <button className="text-link self-start text-sm underline" type="button"
          onClick={() => setGuideOpen(true)} disabled={busy}>Conferir uma guia</button>
      )}
      {welcome && (
        <div className="assistant-choices">
          <button
            type="button"
            onClick={() => setGuideOpen(true)}
            disabled={busy || guideOpen}
          >
            <FileCheck2 /> Conferir uma guia
          </button>
          <button
            type="button"
            onClick={() =>
              send({ text: 'Como emitir a guia DAS da minha empresa este mês?' })
            }
            disabled={busy}
          >
            <FileCheck2 /> Como emitir o DAS?
          </button>
          <button
            type="button"
            onClick={() =>
              send({
                text: 'Qual o limite de faturamento anual do MEI e o que acontece se estourar o teto?',
              })
            }
            disabled={busy}
          >
            <BookOpen /> Limite de faturamento do MEI
          </button>
          <button
            type="button"
            onClick={() =>
              send({
                text: 'Como funciona o cálculo do Fator R no Simples Nacional para saber se fico no Anexo III ou V?',
              })
            }
            disabled={busy}
          >
            <MessagesSquare /> Como calcular o Fator R?
          </button>
          <button
            type="button"
            onClick={() => send({ text: 'Paguei a guia da minha empresa?' })}
            disabled={busy}
          >
            <CheckCircle2 /> Conferir pagamento de guia
          </button>
          <button
            type="button"
            onClick={() => {
              setDraft('Quero entender a regra sobre ');
              document.getElementById('chat-question')?.focus();
            }}
          >
            <BookOpen /> Entender uma regra específica
          </button>
          <a href="#tarefas">
            <ListChecks /> Consultar minhas tarefas
          </a>
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
  const [historySearch, setHistorySearch] = useState('');
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
          {history.length > 0 && (
            <div className="my-2 flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs">
              <Search size={14} className="shrink-0 text-slate-400" />
              <input
                type="search"
                value={historySearch}
                onChange={(e) => setHistorySearch(e.target.value)}
                placeholder="Filtrar conversas…"
                className="w-full border-0 bg-transparent p-0 text-xs outline-none"
              />
            </div>
          )}
          <nav
            className="max-h-60 space-y-1 overflow-auto lg:max-h-[58vh]"
            aria-label="Histórico de conversas"
          >
            {history
              .filter((c) =>
                c.title.toLowerCase().includes(historySearch.toLowerCase()),
              )
              .map((chat) => (
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
