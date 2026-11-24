import { useRef, useState } from 'react';
import { CheckCircle2, RotateCcw } from 'lucide-react';
import { api } from '../../services/api';
import { dateLabel, Feedback, periodLabel, problem, readList, useRead } from '../fiscal-data';
import type { Task } from '../fiscal-data';
import { categoryLabels, getTaskCategory } from './categorias';
import { RecordActions } from './RecordActions';

interface TaskEvent {
  id: string;
  completed: boolean;
  created_at: string;
}

export function TaskDetails({
  task,
  changed,
  edited,
  removed,
}: {
  task: Task;
  changed: (updated: Task) => void;
  edited: (updated: Task) => void;
  removed: () => void;
}) {
  const history = useRead<TaskEvent[]>(
    `/tarefas/${task.id}/historico`,
    readList,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const key = useRef('');
  const category = getTaskCategory(task.title);
  const catInfo = categoryLabels[category];

  async function toggle() {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      if (!key.current) key.current = crypto.randomUUID();
      const updated = await api.request<Task>(`/tarefas/${task.id}`, {
        method: 'PATCH',
        headers: { 'Idempotency-Key': key.current },
        body: JSON.stringify({ completed: !task.completed }),
      });
      key.current = '';
      changed(updated);
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span
          className={`inline-block rounded-full border px-2.5 py-0.5 text-xs font-semibold ${catInfo.className}`}
        >
          {catInfo.label}
        </span>
        <span className="text-xs text-slate-500">
          {task.completed ? 'Concluída' : 'Pendente'}
        </span>
      </div>
      <p className="whitespace-pre-wrap break-words font-semibold">
        {task.title}
      </p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-2 text-sm">
        <dt>Status</dt>
        <dd>{task.completed ? 'Concluída' : 'Pendente'}</dd>
        <dt>Competência</dt>
        <dd>{periodLabel(task.period)}</dd>
        <dt>Prazo</dt>
        <dd>{task.due_date ? dateLabel(task.due_date) : 'Não informado'}</dd>
        <dt>Origem</dt>
        <dd>
          {task.source_message_id
            ? 'Plano do assistente' +
              (task.source_step_index !== null
                ? ' · Passo ' + (task.source_step_index + 1)
                : '')
            : 'Criada pelo usuário'}
        </dd>
        {task.completed_at && (
          <>
            <dt>Conclusão</dt>
            <dd>{dateLabel(task.completed_at, true)}</dd>
          </>
        )}
      </dl>
      <button
        className={task.completed ? 'secondary' : 'primary'}
        onClick={toggle}
        disabled={busy}
      >
        {task.completed ? <RotateCcw size={16} /> : <CheckCircle2 size={16} />}
        {busy
          ? 'Salvando…'
          : task.completed
            ? 'Reabrir tarefa'
            : 'Marcar como concluída'}
      </button>
      {error && <Feedback error={error} />}
      <RecordActions<Task> kind="task" item={task} edited={edited} removed={removed} />
      <p className="record-note text-sm">
        A conclusão registra o andamento da tarefa. A situação fiscal depende
        das evidências da empresa.
      </p>
      <div className="space-y-2 border-t border-slate-200 pt-4">
        <h3 className="text-sm font-bold">Histórico da tarefa</h3>
        {history.loading && <p role="status">Carregando histórico…</p>}
        {history.error && (
          <Feedback error={history.error} retry={history.refresh} />
        )}
        {history.data && (
          <ol className="space-y-2 text-sm">
            {history.data
              .slice()
              .reverse()
              .map((item) => (
                <li key={item.id}>
                  {item.completed ? 'Concluída' : 'Reaberta'} ·{' '}
                  {dateLabel(item.created_at, true)}
                </li>
              ))}
            <li>Criada · {dateLabel(task.created_at, true)}</li>
          </ol>
        )}
      </div>
    </>
  );
}
