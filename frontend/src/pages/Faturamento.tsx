import { useState, type FormEvent } from 'react';
import { FileText, Pencil, Plus, Printer, Trash2 } from 'lucide-react';
import { formatCnpj } from '../components/Sidebar';
import { api } from '../services/api';
import type { Company } from '../types';
import { money, monthlyReport, parseAmount, revenueGroups } from './receita';
import type { MonthlyRevenue, RevenueField } from './receita';
import { Feedback, FormDialog, periodLabel, problem, readJson, useRead } from './fiscal-data';
import type { PageProps } from './fiscal-data';
import { isMei } from './regime';
import { RevenueThermometer } from './RevenueThermometer';
import './receita.css';

const monthNames = [
  'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
];
const fieldNames = revenueGroups.flatMap((group): RevenueField[] => [group.without, group.with]);

function MonthForm({
  url,
  period,
  initial,
  close,
  saved,
}: {
  url: string;
  period: string;
  initial?: MonthlyRevenue;
  close: () => void;
  saved: () => void;
}) {
  const [values, setValues] = useState(
    () =>
      Object.fromEntries(
        fieldNames.map((name) => [
          name,
          initial && Number(initial[name]) ? initial[name].replace('.', ',') : '',
        ]),
      ) as Record<RevenueField, string>,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const parsed = fieldNames.map((name) => parseAmount(values[name]));
  const total = parsed.reduce((sum, value) => sum + Math.round(Number(value) * 100), 0) / 100;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (parsed.includes(null)) {
      setError('Informe valores como 1.500,00, sem sinal negativo.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await api.request(url, {
        method: 'PUT',
        body: JSON.stringify(
          Object.fromEntries(fieldNames.map((name, index) => [name, parsed[index]])),
        ),
      });
      saved();
    } catch (err) {
      setError(problem(err));
      setBusy(false);
    }
  }
  const input = (name: RevenueField, label: string) => (
    <label className="field">
      {label}
      <input
        inputMode="decimal"
        placeholder="0,00"
        value={values[name]}
        onChange={(event) => {
          setValues({ ...values, [name]: event.target.value });
          setError('');
        }}
      />
    </label>
  );
  return (
    <FormDialog title={'Faturamento de ' + periodLabel(period)} close={close} busy={busy}>
      <form onSubmit={submit} className="space-y-4">
        {revenueGroups.map((group) => (
          <fieldset key={group.with} disabled={busy} className="grid gap-3 sm:grid-cols-2">
            <legend className="mb-1 text-sm font-semibold">{group.title}</legend>
            {input(group.with, 'Com documento fiscal')}
            {input(group.without, 'Sem documento fiscal')}
          </fieldset>
        ))}
        <p className="text-sm">
          Total do mês:{' '}
          <strong>{parsed.includes(null) ? '—' : money.format(total)}</strong>
        </p>
        {error && <Feedback error={error} />}
        <button className="primary" disabled={busy}>
          {busy ? 'Salvando…' : 'Salvar mês'}
        </button>
      </form>
    </FormDialog>
  );
}

function DeleteMonth({
  url,
  period,
  close,
  done,
}: {
  url: string;
  period: string;
  close: () => void;
  done: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function remove() {
    setBusy(true);
    setError('');
    try {
      await api.request<void>(url, { method: 'DELETE' });
      done();
    } catch (err) {
      setError(problem(err));
      setBusy(false);
    }
  }
  return (
    <FormDialog title={'Excluir ' + periodLabel(period)} close={close} busy={busy}>
      <div className="space-y-4 text-sm">
        <p>O lançamento deste mês será removido e não poderá ser recuperado.</p>
        {error && <Feedback error={error} />}
        <div className="flex justify-end gap-2">
          <button type="button" className="secondary" onClick={close} disabled={busy}>
            Cancelar
          </button>
          <button type="button" className="primary" onClick={remove} disabled={busy}>
            {busy ? 'Excluindo…' : 'Excluir lançamento'}
          </button>
        </div>
      </div>
    </FormDialog>
  );
}

function Report({ company, month }: { company: Company; month: MonthlyRevenue }) {
  return (
    <section
      className="panel print-report space-y-4"
      aria-label="Relatório mensal das receitas brutas"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-bold">Relatório mensal das receitas brutas</h2>
        <button type="button" className="secondary no-print" onClick={() => window.print()}>
          <Printer size={15} aria-hidden /> Imprimir ou salvar em PDF
        </button>
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt>CNPJ</dt>
        <dd>{formatCnpj(company.cnpj)}</dd>
        <dt>Empreendedor individual</dt>
        <dd className="report-line" />
        <dt>Período de apuração</dt>
        <dd>{periodLabel(month.period)}</dd>
      </dl>
      <table className="w-full text-left text-sm">
        <tbody>
          {monthlyReport(month).map((row) => (
            <tr key={row.field} className="border-b border-slate-200">
              <td className="py-1.5 pr-3 font-semibold">{row.field}</td>
              <td className="py-1.5 pr-3">
                {row.field === 'X' ? row.label : `${row.title}: ${row.label}`}
              </td>
              <td className="whitespace-nowrap py-1.5 text-right tabular-nums">
                {money.format(row.amount)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-4 pt-4 text-sm">
        <dt>Local e data</dt>
        <dd className="report-line" />
        <dt>Assinatura</dt>
        <dd className="report-line" />
      </dl>
      <p className="text-xs text-ink-muted">
        Anexe os documentos fiscais de compras e serviços tomados e as notas emitidas no período.
        Valores declarados pela empresa, nos campos da Resolução CGSN nº 140/2018, Anexo X. Confira
        com o modelo oficial antes de assinar.
      </p>
    </section>
  );
}

export function Faturamento({ company }: PageProps) {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const base = `/empresas/${company.id}/faturamento-mensal`;
  const list = useRead<{ items: MonthlyRevenue[] }>(
    `${base}?from=${year}-01&to=${year}-12`,
    readJson,
  );
  const [editing, setEditing] = useState('');
  const [deleting, setDeleting] = useState('');
  const [reporting, setReporting] = useState('');
  const [revision, setRevision] = useState(0);
  const months = new Map(list.data?.items.map((item) => [item.period, item]));
  const lastMonth = year < now.getFullYear() ? 12 : now.getMonth() + 1;
  const reported = months.get(reporting);

  function changed() {
    setEditing('');
    setDeleting('');
    list.refresh();
    setRevision((value) => value + 1);
  }

  return (
    <div className="stack">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Faturamento</h1>
          <p className="text-ink-muted">
            Receita bruta por mês. O total alimenta o termômetro do limite anual.
          </p>
        </div>
        <label className="field">
          Ano
          <select
            value={year}
            onChange={(event) => {
              setYear(Number(event.target.value));
              setReporting('');
            }}
          >
            {Array.from({ length: 5 }, (_, index) => now.getFullYear() - index).map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>
      </div>
      <RevenueThermometer key={`${year}/${revision}`} company={company} year={year} standalone={false} />
      <section className="panel space-y-3" aria-label="Meses">
        {list.loading && <p role="status">Carregando meses…</p>}
        {list.error && <Feedback error={list.error} retry={list.refresh} />}
        {list.data && (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-ink-muted">
                <th className="py-2 font-semibold">Mês</th>
                <th className="py-2 text-right font-semibold">Receita</th>
                <th className="py-2">
                  <span className="sr-only">Ações</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {monthNames.map((name, index) => {
                const period = `${year}-${String(index + 1).padStart(2, '0')}`;
                const month = months.get(period);
                return (
                  <tr key={period} className="border-b border-slate-100">
                    <th scope="row" className="py-2 font-medium">
                      {name}
                    </th>
                    <td className="py-2 text-right tabular-nums">
                      {month ? money.format(Number(month.total)) : 'Não lançado'}
                    </td>
                    <td className="py-2">
                      <div className="flex flex-wrap justify-end gap-2">
                        {month && isMei(company) && (
                          <button
                            type="button"
                            className="secondary"
                            aria-label={'Relatório de ' + name}
                            onClick={() => setReporting(period)}
                          >
                            <FileText size={15} aria-hidden />
                          </button>
                        )}
                        {index < lastMonth && (
                          <button
                            type="button"
                            className="secondary"
                            aria-label={(month ? 'Editar ' : 'Lançar ') + name}
                            onClick={() => setEditing(period)}
                          >
                            {month ? <Pencil size={15} aria-hidden /> : <Plus size={15} aria-hidden />}
                          </button>
                        )}
                        {month && (
                          <button
                            type="button"
                            className="secondary"
                            aria-label={'Excluir ' + name}
                            onClick={() => setDeleting(period)}
                          >
                            <Trash2 size={15} aria-hidden />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
      {reported && <Report company={company} month={reported} />}
      {editing && (
        <MonthForm
          key={editing}
          url={`${base}/${editing}`}
          period={editing}
          initial={months.get(editing)}
          close={() => setEditing('')}
          saved={changed}
        />
      )}
      {deleting && (
        <DeleteMonth
          url={`${base}/${deleting}`}
          period={deleting}
          close={() => setDeleting('')}
          done={changed}
        />
      )}
    </div>
  );
}
