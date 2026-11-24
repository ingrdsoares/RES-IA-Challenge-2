import { useState } from 'react';
import { api } from '../../services/api';
import { dateLabel, Feedback, FormDialog, problem, readList, useRead } from '../fiscal-data';
import type { PageProps, Task } from '../fiscal-data';
import { isMei } from '../regime';
import { annualTasks, missingTasks } from '../obrigacoesAno';

export function GenerateAnnualTasksDialog({
  company,
  url,
  close,
  done,
}: {
  company: PageProps['company'];
  url: string;
  close: () => void;
  done: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');

  const existing = useRead<Task[]>(url, readList);
  const today = new Date();
  const year = today.getFullYear();
  const mei = isMei(company);
  const pending = existing.data
    ? missingTasks(annualTasks(today, mei), existing.data)
    : [];
  const [total, setTotal] = useState(0);

  async function generate() {
    setBusy(true);
    setError('');
    setProgress(0);
    setTotal(pending.length);
    try {
      for (const task of pending) {
        await api.request(url, {
          method: 'POST',
          body: JSON.stringify(task),
        });
        setProgress((count) => count + 1);
      }
      done();
    } catch (err) {
      setError(problem(err));
      existing.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <FormDialog
      title={`Gerar Obrigações do Ano (${year})`}
      busy={busy}
      close={close}
    >
      <div className="space-y-4 text-sm">
        <p className="text-slate-600">
          Serão criadas as obrigações ainda não vencidas de {year} (
          {mei ? 'MEI' : 'Simples Nacional'}) que sua empresa ainda não tem:
        </p>
        {existing.loading && <p role="status">Conferindo tarefas…</p>}
        {existing.error && (
          <Feedback error={existing.error} retry={existing.refresh} />
        )}
        {existing.data && pending.length === 0 && (
          <p>Todas as obrigações do período já estão nas suas tarefas.</p>
        )}
        <ul className="list-disc space-y-1 pl-5 text-xs text-slate-700">
          {pending.map((task) => (
            <li key={task.title}>
              {task.title}: prazo {dateLabel(task.due_date)}
            </li>
          ))}
        </ul>

        {busy && (
          <div className="rounded-lg bg-info/10 p-3 text-xs font-medium text-link">
            Gerando obrigação {progress} de {total}…
          </div>
        )}

        {error && <Feedback error={error} />}

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={close}
            disabled={busy}
            className="secondary"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={generate}
            disabled={busy || pending.length === 0}
            className="primary"
          >
            {busy
              ? 'Gerando…'
              : `Confirmar e Gerar ${pending.length} Obrigações`}
          </button>
        </div>
      </div>
    </FormDialog>
  );
}
