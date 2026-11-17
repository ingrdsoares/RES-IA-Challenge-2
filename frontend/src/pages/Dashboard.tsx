import { useState } from 'react';
import type { FormEvent } from 'react';
import {
  ArrowRight,
  Building2,
  CalendarDays,
  FileBadge2,
  ListChecks,
  MessageSquare,
} from 'lucide-react';
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
        <p className="mt-3 text-sm text-slate-600">
          A simulação está disponível para MEI e Simples Nacional. Regime
          cadastrado · {company.regime}.
        </p>
      ) : (
        <>
          <p className="my-4 text-sm text-slate-600">
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
              className="mt-4 rounded-xl bg-slate-50 p-4 text-sm"
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
                  className="block break-all text-emerald-800 underline"
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
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Visão geral</h1>
          <p className="mt-1 text-sm text-slate-600">
            {company.regime} · {company.municipality}/{company.state} · CNPJ{' '}
            {company.cnpj}
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
              <span className="rounded-lg bg-emerald-50 p-2 text-emerald-800">
                <Icon size={21} aria-hidden="true" />
              </span>
              <h2 className="font-semibold text-slate-700">
                {scopeNames[scope]}
              </h2>
              {status.data ? (
                <IndicatorInfo scope={scope} indicator={status.data[scope]} />
              ) : (
                <p role="status" className="text-sm text-slate-500">
                  {status.loading
                    ? 'Carregando indicador…'
                    : 'Consulta indisponível'}
                </p>
              )}
              <a
                href={`#fiscal?scope=${scope}`}
                aria-label={`Ver detalhes de ${scopeNames[scope]}`}
                className="mt-auto inline-flex items-center gap-2 pt-2 text-sm font-semibold text-emerald-800"
              >
                Ver detalhes <ArrowRight size={15} />
              </a>
            </article>
          );
        })}
      </section>
      {status.error && <Feedback error={status.error} retry={status.refresh} />}
      <section className="panel space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-bold">Próximas tarefas</h2>
          <a
            href="#tarefas"
            className="inline-flex items-center gap-2 text-sm font-semibold text-emerald-800"
          >
            Ver todas as tarefas <ArrowRight size={15} />
          </a>
        </div>
        {tasks.loading && <p role="status">Carregando tarefas…</p>}
        {tasks.error && <Feedback error={tasks.error} retry={tasks.refresh} />}
        {upcoming?.length === 0 && (
          <p className="rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
            Nenhuma tarefa pendente para esta empresa.
          </p>
        )}
        <ul className="divide-y divide-slate-100">
          {upcoming?.map((task) => (
            <li key={task.id}>
              <a
                href={`#tarefas?task=${task.id}`}
                className="flex items-center gap-3 py-3 hover:text-emerald-800"
              >
                <CalendarDays size={18} className="shrink-0 text-slate-500" />
                <span className="min-w-0">
                  <strong className="block break-words text-sm">
                    {task.title}
                  </strong>
                  <small className="text-slate-600">
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
