import { useState } from 'react';
import type { FormEvent } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Building2,
  CalendarDays,
  Edit3,
  FileBadge2,
  ListChecks,
  MessageSquare,
  TrendingUp,
} from 'lucide-react';
import { formatCnpj } from '../components/Sidebar';
import { api } from '../services/api';
import type { Company } from '../types';
import {
  dateLabel,
  Feedback,
  IndicatorInfo,
  periodLabel,
  problem,
  readJson,
  readList,
  scopeNames,
  scopes,
  useRead,
} from './fiscal-data';
import type { FiscalStatus, PageProps, Task } from './fiscal-data';

const scopeIcons = {
  registration: Building2,
  federal_certificate: FileBadge2,
  obligations: ListChecks,
};
const money = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
});
const percent = new Intl.NumberFormat('pt-BR', {
  style: 'percent',
  maximumFractionDigits: 4,
});
interface Calculation {
  status: string;
  reason: string | null;
  request: { period: string };
  references: string[];
  result: {
    amount: string;
    effective_rate?: string;
    factor_r?: string | null;
    annex?: string;
    rule_version: string;
    assumptions: string[];
  } | null;
}
function Simulator({ company }: { company: Company }) {
  const [response, setResponse] = useState<Calculation>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const regime = company.regime.toLowerCase();
  const isMei =
    /\b(simei|mei)\b/.test(regime) || company.size.toLowerCase() === 'mei';
  const isSimples = regime.includes('simples');
  async function calculate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const fields = new FormData(event.currentTarget);
    const values = isMei
      ? { activity: fields.get('activity') }
      : {
          rbt12: fields.get('rbt12'),
          revenue: fields.get('revenue'),
          payroll12: fields.get('payroll12') || null,
        };
    setBusy(true);
    setError('');
    setResponse(undefined);
    try {
      setResponse(
        await api.request<Calculation>(`/empresas/${company.id}/calculos`, {
          method: 'POST',
          body: JSON.stringify({
            kind: isMei ? 'mei' : 'simples',
            period: fields.get('period'),
            conditions_confirmed: fields.has('confirmed'),
            ...values,
          }),
        }),
      );
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }
  const result = response?.result;
  return (
    <details className="panel">
      <summary className="cursor-pointer font-semibold">
        Simulação tributária
      </summary>
      {!isMei && !isSimples ? (
        <p className="mt-3 text-sm text-ink-muted">
          A simulação está disponível para MEI e Simples Nacional. Regime
          cadastrado · {company.regime}.
        </p>
      ) : (
        <>
          <p className="my-4 text-sm text-ink-muted">
            Informe os dados da competência para simular o DAS de{' '}
            {isMei ? 'MEI' : 'Simples Nacional'} com a regra revisada
            disponível.
          </p>
          <form
            onSubmit={calculate}
            onChange={() => {
              setResponse(undefined);
              setError('');
            }}
            className="space-y-4"
          >
            <fieldset disabled={busy} className="grid gap-4 sm:grid-cols-2">
              <label className="field">
                Competência
                <input type="month" name="period" required />
              </label>
              {isMei ? (
                <label className="field">
                  Atividade
                  <select name="activity" required defaultValue="">
                    <option value="" disabled>
                      Selecione
                    </option>
                    <option value="trade">Comércio</option>
                    <option value="services">Serviços</option>
                    <option value="mixed">Comércio e serviços</option>
                  </select>
                </label>
              ) : (
                <>
                  <label className="field">
                    Receita acumulada em 12 meses (R$)
                    <input
                      name="rbt12"
                      type="number"
                      min="0"
                      step="0.01"
                      required
                    />
                  </label>
                  <label className="field">
                    Receita do mês (R$)
                    <input
                      name="revenue"
                      type="number"
                      min="0"
                      step="0.01"
                      required
                    />
                  </label>
                  <label className="field">
                    Folha em 12 meses (R$), se houver Fator R
                    <input name="payroll12" type="number" min="0" step="0.01" />
                  </label>
                </>
              )}
              <label className="col-span-full flex items-center gap-2 text-sm">
                <input type="checkbox" name="confirmed" required />
                Confirmo o enquadramento e os dados desta competência.
              </label>
            </fieldset>
            <button className="primary" disabled={busy}>
              {busy ? 'Calculando…' : 'Simular DAS'}
            </button>
          </form>
          {error && <Feedback error={error} />}
          {response && (
            <div
              className="mt-4 rounded-xl bg-surface-muted p-4 text-sm"
              role="status"
            >
              <h3 className="font-semibold">
                Resultado da competência {periodLabel(response.request.period)}
              </h3>
              {result ? (
                <>
                  <dl className="my-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
                    <dt>DAS simulado</dt>
                    <dd className="font-bold">
                      {money.format(Number(result.amount))}
                    </dd>
                    {result.annex && (
                      <>
                        <dt>Anexo</dt>
                        <dd>{result.annex}</dd>
                      </>
                    )}
                    {result.effective_rate != null && (
                      <>
                        <dt>Alíquota efetiva</dt>
                        <dd>{percent.format(Number(result.effective_rate))}</dd>
                      </>
                    )}
                    {!isMei && (
                      <>
                        <dt>Fator R</dt>
                        <dd>
                          {result.factor_r == null
                            ? 'Não aplicável'
                            : percent.format(Number(result.factor_r))}
                        </dd>
                      </>
                    )}
                    <dt>Versão da regra</dt>
                    <dd>{result.rule_version}</dd>
                  </dl>
                  {result.assumptions.map((item) => (
                    <p key={item}>{item}</p>
                  ))}
                </>
              ) : (
                <p>
                  {response.reason?.replace('payroll12', 'folha em 12 meses') ||
                    'Simulação indisponível.'}
                </p>
              )}
              {response.references.map((ref) => (
                <a
                  href={ref}
                  key={ref}
                  target="_blank"
                  rel="noreferrer"
                  className="block break-all text-link underline"
                >
                  {ref}
                </a>
              ))}
            </div>
          )}
        </>
      )}
    </details>
  );
}

function UrgentAlertBanner({ tasks }: { tasks?: Task[] | null }) {
  if (!tasks?.length) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const critical = tasks
    .filter((t) => t.due_date && !t.completed)
    .map((t) => {
      const due = new Date(t.due_date + 'T00:00:00');
      const diffMs = due.getTime() - today.getTime();
      const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
      return { task: t, diffDays };
    })
    .filter((item) => item.diffDays <= 7)
    .sort((a, b) => a.diffDays - b.diffDays);

  if (!critical.length) return null;

  const overdue = critical.filter((c) => c.diffDays < 0);
  const isUrgent = overdue.length > 0;

  return (
    <aside
      role="alert"
      className={
        'rounded-xl border p-4 text-sm ' +
        (isUrgent
          ? 'border-rose-300 bg-rose-50 text-rose-950'
          : 'border-amber-300 bg-amber-50 text-amber-950')
      }
    >
      <div className="flex items-center gap-2 font-bold">
        <AlertTriangle
          size={18}
          className={isUrgent ? 'text-rose-600' : 'text-amber-600'}
        />
        <span>
          {isUrgent
            ? `Atenção: ${overdue.length} obrigação(ões) em atraso!`
            : `Próximos vencimentos críticos nesta semana (${critical.length})`}
        </span>
      </div>
      <ul className="mt-3 divide-y divide-black/10">
        {critical.slice(0, 3).map(({ task, diffDays }) => (
          <li
            key={task.id}
            className="flex flex-wrap items-center justify-between gap-2 py-2"
          >
            <div className="min-w-0">
              <strong className="block truncate">{task.title}</strong>
              <small className="text-black/70">
                Prazo oficial: {task.due_date ? dateLabel(task.due_date) : '-'}
              </small>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={
                  'rounded-full px-2.5 py-0.5 text-xs font-semibold ' +
                  (diffDays < 0
                    ? 'bg-rose-600 text-white'
                    : diffDays === 0
                      ? 'bg-amber-600 text-white'
                      : 'bg-amber-200 text-amber-900')
                }
              >
                {diffDays < 0
                  ? `Atrasado há ${Math.abs(diffDays)} dia(s)`
                  : diffDays === 0
                    ? 'Vence hoje'
                    : diffDays === 1
                      ? 'Vence amanhã'
                      : `Vence em ${diffDays} dias`}
              </span>
              <a
                href={`#tarefas?task=${task.id}`}
                className="font-semibold underline hover:opacity-80"
              >
                Ver tarefa
              </a>
            </div>
          </li>
        ))}
      </ul>
    </aside>
  );
}

function RevenueThermometer({ company }: { company: Company }) {
  const regime = company.regime.toLowerCase();
  const isMei =
    /\b(simei|mei)\b/.test(regime) || company.size.toLowerCase() === 'mei';

  const limit = isMei ? 81000 : 4800000;

  const storageKey = 'revenue:' + company.id;
  const [revenue, setRevenue] = useState<number>(() => {
    const saved = localStorage.getItem(storageKey);
    return saved ? Number(saved) : isMei ? 48500 : 850000;
  });
  const [editing, setEditing] = useState(false);
  const [inputVal, setInputVal] = useState(String(revenue));

  function save(e: FormEvent) {
    e.preventDefault();
    const val = Number(inputVal) || 0;
    setRevenue(val);
    localStorage.setItem(storageKey, String(val));
    setEditing(false);
  }

  const pct = Math.min(100, Math.round((revenue / limit) * 100));
  const remaining = Math.max(0, limit - revenue);

  const statusColor =
    pct < 70
      ? 'bg-emerald-500'
      : pct < 90
        ? 'bg-amber-500'
        : 'bg-rose-600';

  return (
    <section className="panel space-y-4" aria-label="Termômetro de Faturamento">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="rounded-lg bg-info p-2 text-link">
            <TrendingUp size={20} />
          </span>
          <div>
            <h2 className="font-bold text-ink">
              Termômetro de Limite de Faturamento Anual
            </h2>
            <p className="text-xs text-ink-muted">
              {isMei
                ? 'Teto do MEI: R$ 81.000,00/ano (média R$ 6.750,00/mês)'
                : 'Teto Simples Nacional: R$ 4.800.000,00/ano (sublimite R$ 3.600.000,00)'}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            setInputVal(String(revenue));
            setEditing(!editing);
          }}
          className="secondary inline-flex items-center gap-1.5 text-xs font-semibold"
        >
          <Edit3 size={14} /> {editing ? 'Cancelar' : 'Ajustar receita informada'}
        </button>
      </div>

      {editing && (
        <form onSubmit={save} className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-surface-muted p-3">
          <label className="field text-xs">
            Receita Bruta Acumulada no Ano (R$)
            <input
              type="number"
              step="0.01"
              min="0"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              required
              className="text-sm font-semibold"
            />
          </label>
          <button className="primary text-xs py-2">Salvar valor</button>
        </form>
      )}

      <div>
        <div className="mb-2 flex flex-wrap items-center justify-between text-sm">
          <span>
            Faturamento acumulado: <strong>{money.format(revenue)}</strong>
          </span>
          <span className="font-semibold text-ink">
            {pct}% do teto ({money.format(limit)})
          </span>
        </div>
        <div className="h-3 w-full overflow-hidden rounded-full bg-slate-200">
          <div
            className={`h-full transition-all duration-500 ${statusColor}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 text-xs">
        <div className="rounded-lg bg-surface-muted p-3">
          <span className="block text-ink-muted">Saldo restante até o teto</span>
          <strong className="text-base text-ink">{money.format(remaining)}</strong>
        </div>
        <div className="rounded-lg bg-surface-muted p-3">
          <span className="block text-ink-muted">Diagnóstico preventivo</span>
          <span
            className={
              'font-semibold ' +
              (pct < 70
                ? 'text-emerald-700'
                : pct < 90
                  ? 'text-amber-700'
                  : 'text-rose-700')
            }
          >
            {pct < 70
              ? 'Faixa segura de faturamento no período.'
              : pct < 90
                ? 'Atenção: aproximando-se do teto anual do regime.'
                : 'Alerta crítico: risco iminente de desenquadramento fiscal!'}
          </span>
        </div>
      </div>
    </section>
  );
}

export function Dashboard({ company }: PageProps) {
  const base = `/empresas/${company.id}`;
  const status = useRead<FiscalStatus>(base + '/situacao-fiscal', readJson);
  const tasks = useRead<Task[]>(base + '/tarefas?completed=false', readList);
  const upcoming = tasks.data
    ?.slice()
    .sort((a, b) => (a.due_date || '9999').localeCompare(b.due_date || '9999'))
    .slice(0, 4);
  return (
    <div className="stack">
      <UrgentAlertBanner tasks={tasks.data} />
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Visão geral</h1>
          <p className="mt-1 text-sm text-ink-muted">
            {company.regime} · {company.municipality}/{company.state} · CNPJ{' '}
            {formatCnpj(company.cnpj)}
          </p>
        </div>
        <a href="#assistente" className="primary">
          <MessageSquare size={16} /> Abrir assistente
        </a>
      </div>
      <section
        aria-label="Indicadores fiscais"
        className="grid gap-4 md:grid-cols-3"
      >
        {scopes.map((scope) => {
          const Icon = scopeIcons[scope];
          return (
            <article
              className="panel flex flex-col items-start gap-3"
              key={scope}
            >
              <span className="rounded-lg bg-info p-2 text-link">
                <Icon size={21} aria-hidden="true" />
              </span>
              <h2 className="font-semibold text-ink">
                {scopeNames[scope]}
              </h2>
              {status.data ? (
                <IndicatorInfo scope={scope} indicator={status.data[scope]} />
              ) : (
                <p role="status" className="text-sm text-ink-muted">
                  {status.loading
                    ? 'Carregando indicador…'
                    : 'Consulta indisponível'}
                </p>
              )}
              <a
                href={`#fiscal?scope=${scope}`}
                aria-label={`Ver detalhes de ${scopeNames[scope]}`}
                className="touch-link mt-auto inline-flex items-center gap-2 text-sm font-semibold text-link"
              >
                Ver detalhes <ArrowRight size={15} />
              </a>
            </article>
          );
        })}
      </section>
      {status.error && <Feedback error={status.error} retry={status.refresh} />}
      <RevenueThermometer company={company} />
      <section className="panel space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-bold">Próximas tarefas</h2>
          <a
            href="#tarefas"
            className="touch-link inline-flex items-center gap-2 text-sm font-semibold text-link"
          >
            Ver todas as tarefas <ArrowRight size={15} />
          </a>
        </div>
        {tasks.loading && <p role="status">Carregando tarefas…</p>}
        {tasks.error && <Feedback error={tasks.error} retry={tasks.refresh} />}
        {upcoming?.length === 0 && (
          <p className="rounded-lg bg-surface-muted p-4 text-sm text-ink-muted">
            Nenhuma tarefa pendente para esta empresa.
          </p>
        )}
        <ul className="divide-y divide-subtle">
          {upcoming?.map((task) => (
            <li key={task.id}>
              <a
                href={`#tarefas?task=${task.id}`}
                className="flex items-center gap-3 py-3 hover:text-link"
              >
                <CalendarDays size={18} className="shrink-0 text-ink-muted" />
                <span className="min-w-0">
                  <strong className="block break-words text-sm">
                    {task.title}
                  </strong>
                  <small className="text-ink-muted">
                    {task.due_date
                      ? 'Prazo ' + dateLabel(task.due_date)
                      : 'Prazo não informado'}
                    {task.period &&
                      ' · Competência ' + periodLabel(task.period)}
                  </small>
                </span>
              </a>
            </li>
          ))}
        </ul>
      </section>
      <Simulator
        key={[company.id, company.cnae, company.regime, company.size].join('/')}
        company={company}
      />
    </div>
  );
}
