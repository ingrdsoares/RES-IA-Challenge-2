import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Building2,
  CalendarDays,
  FileBadge2,
  ListChecks,
  MessageSquare,
} from 'lucide-react';
import { formatCnpj } from '../components/Sidebar';
import { agendaHref, buildAgenda, daysUntil } from './tarefas/agenda';
import type { AgendaItem, Obligation } from './tarefas/agenda';
import { money, previousMonths, rbt12 } from './receita';
import type { MonthlyRevenue } from './receita';
import { RevenueThermometer } from './RevenueThermometer';
import { isMei as isMeiCompany } from './regime';
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
  const isMei = isMeiCompany(company);
  const form = useRef<HTMLFormElement>(null);
  const [prefill, setPrefill] = useState('');
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
  async function fillFromLaunched() {
    const fields = form.current!.elements;
    const input = (name: string) => fields.namedItem(name) as HTMLInputElement;
    const period = input('period').value;
    setResponse(undefined);
    setError('');
    if (!period) {
      setPrefill('Escolha a competência primeiro.');
      return;
    }
    setPrefill('');
    try {
      const { items } = await api.request<{ items: MonthlyRevenue[] }>(
        `/empresas/${company.id}/faturamento-mensal?from=${previousMonths(period)[0]}&to=${period}`,
      );
      const total = rbt12(items, period);
      input('rbt12').value = total ?? '';
      input('revenue').value = items.find((item) => item.period === period)?.total ?? '';
      if (total === null)
        setPrefill('Faltam meses lançados para calcular a receita de 12 meses.');
    } catch (err) {
      setError(problem(err));
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
            ref={form}
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
                  <div className="col-span-full flex flex-wrap items-center gap-3 text-sm">
                    <button type="button" className="secondary" onClick={fillFromLaunched}>
                      Usar faturamento lançado
                    </button>
                    {prefill && <span role="status">{prefill}</span>}
                  </div>
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

function UrgentAlertBanner({ items }: { items: AgendaItem[] }) {
  const critical = items.flatMap((item) => {
    const diffDays = item.due_date ? daysUntil(item.due_date) : Infinity;
    return diffDays <= 7 ? [{ item, diffDays }] : [];
  });

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
            ? `Atenção: ${overdue.length} item(ns) em atraso!`
            : `Próximos vencimentos críticos nesta semana (${critical.length})`}
        </span>
      </div>
      <ul className="mt-3 divide-y divide-black/10">
        {critical.slice(0, 3).map(({ item, diffDays }) => (
          <li
            key={item.kind + item.id}
            className="flex flex-wrap items-center justify-between gap-2 py-2"
          >
            <div className="min-w-0">
              <strong className="block truncate">{item.title}</strong>
              <small className="text-black/70">
                Prazo: {item.due_date ? dateLabel(item.due_date) : '-'}
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
                href={agendaHref({}, item)}
                className="font-semibold underline hover:opacity-80"
              >
                Ver detalhes
              </a>
            </div>
          </li>
        ))}
      </ul>
    </aside>
  );
}

export function Dashboard({ company }: PageProps) {
  const base = `/empresas/${company.id}`;
  const status = useRead<FiscalStatus>(base + '/situacao-fiscal', readJson);
  const tasks = useRead<Task[]>(base + '/tarefas?completed=false', readList);
  const obligations = useRead<Obligation[]>(base + '/obrigacoes', readList);
  const loading = tasks.loading || obligations.loading;
  const agenda = buildAgenda(tasks.data ?? [], obligations.data ?? [], { status: 'pending' });
  const upcoming = agenda.slice(0, 4);
  return (
    <div className="stack">
      <UrgentAlertBanner items={agenda} />
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
      <RevenueThermometer key={company.id} company={company} />
      <section className="panel space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-bold">Próximos vencimentos</h2>
          <a
            href="#tarefas"
            className="touch-link inline-flex items-center gap-2 text-sm font-semibold text-link"
          >
            Ver tarefas e obrigações <ArrowRight size={15} />
          </a>
        </div>
        {loading && <p role="status">Carregando vencimentos…</p>}
        {tasks.error && <Feedback error={tasks.error} retry={tasks.refresh} />}
        {obligations.error && (
          <Feedback error={obligations.error} retry={obligations.refresh} />
        )}
        {!loading && !tasks.error && !obligations.error && upcoming.length === 0 && (
          <p className="rounded-lg bg-surface-muted p-4 text-sm text-ink-muted">
            Nenhuma tarefa ou obrigação pendente para esta empresa.
          </p>
        )}
        <ul className="divide-y divide-subtle">
          {upcoming.map((item) => (
            <li key={item.kind + item.id}>
              <a
                href={agendaHref({}, item)}
                className="flex items-center gap-3 py-3 hover:text-link"
              >
                <CalendarDays size={18} className="shrink-0 text-ink-muted" />
                <span className="min-w-0">
                  <strong className="block break-words text-sm">
                    {item.title}
                  </strong>
                  <small className="text-ink-muted">
                    {item.due_date
                      ? 'Prazo ' + dateLabel(item.due_date)
                      : 'Prazo não informado'}
                    {item.period &&
                      ' · Competência ' + periodLabel(item.period)}
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
