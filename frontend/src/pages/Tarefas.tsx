import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { CheckCircle2, Circle, Plus, RotateCcw } from 'lucide-react';
import { api } from '../services/api';
import {
  dateLabel,
  Feedback,
  FormDialog,
  periodLabel,
  problem,
  readList,
  useRead,
} from './fiscal-data';
import type { PageProps, Task } from './fiscal-data';

const filters = {
  all: 'Todas',
  pending: 'Pendentes',
  done: 'Concluídas',
} as const;
type Filter = keyof typeof filters;
interface TaskEvent {
  id: string;
  completed: boolean;
  created_at: string;
}

function NewTask({
  url,
  close,
  saved,
}: {
  url: string;
  close: () => void;
  saved: (task: Task) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = new FormData(event.currentTarget);
    const title = String(form.get('title') || '').trim();
    if (!title) {
      setError('Informe a orientação da tarefa.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      saved(
        await api.request<Task>(url, {
          method: 'POST',
          body: JSON.stringify({
            title,
            period: form.get('period') || null,
            due_date: form.get('due') || null,
          }),
        }),
      );
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <FormDialog title="Nova tarefa" close={close} busy={busy}>
      <form onSubmit={submit} className="space-y-4">
        <fieldset disabled={busy} className="space-y-4">
          <label className="field">
            Orientação da tarefa
            <textarea name="title" rows={3} required maxLength={500} />
          </label>
          <label className="field">
            Competência (opcional)
            <input type="month" name="period" />
          </label>
          <label className="field">
            Prazo (opcional)
            <input type="date" name="due" />
          </label>
        </fieldset>
        {error && <Feedback error={error} />}
        <button className="primary" disabled={busy}>
          {busy ? 'Criando…' : 'Criar tarefa'}
        </button>
      </form>
    </FormDialog>
  );
}

function TaskDetails({
  task,
  changed,
}: {
  task: Task;
  changed: (updated: Task) => void;
}) {
  const history = useRead<TaskEvent[]>(
    `/tarefas/${task.id}/historico`,
    readList,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const key = useRef('');
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
    <aside className="panel space-y-4">
      <h2 className="text-lg font-bold">Detalhe da tarefa</h2>
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
      <p className="text-sm text-slate-600">
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
    </aside>
  );
}

function taskHref(filter: Filter, id?: string) {
  const params = new URLSearchParams();
  if (filter !== 'all') params.set('filter', filter);
  if (id) params.set('task', id);
  return '#tarefas' + (params.size ? '?' + params : '');
}

export function Tarefas({ company, params }: PageProps) {
  const listUrl = `/empresas/${company.id}/tarefas`;
  const requested = params.get('filter');
  const filter: Filter =
    requested === 'pending' || requested === 'done' ? requested : 'all';
  const query =
    filter === 'all' ? '' : '?completed=' + String(filter === 'done');
  const tasks = useRead<Task[]>(listUrl + query, readList);
  const active =
    tasks.data?.find((task) => task.id === params.get('task')) ||
    tasks.data?.[0];
  const [creating, setCreating] = useState(false);
  const [notice, setNotice] = useState('');

  return (
    <div className="stack">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-3xl font-bold tracking-tight">Tarefas</h1>
        <button
          className="primary"
          onClick={() => {
            setNotice('');
            setCreating(true);
          }}
        >
          <Plus size={16} /> Nova tarefa
        </button>
      </div>
      <nav
        aria-label="Filtrar tarefas por status"
        className="flex flex-wrap gap-2"
      >
        {(Object.keys(filters) as Filter[]).map((item) => (
          <a
            key={item}
            href={taskHref(item)}
            aria-current={filter === item ? 'page' : undefined}
            className={filter === item ? 'primary' : 'secondary'}
          >
            {filters[item]}
          </a>
        ))}
      </nav>
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      <div className="grid items-start gap-4 lg:grid-cols-[1.25fr_1fr]">
        <section className="panel space-y-3" aria-label="Lista de tarefas">
          {tasks.loading && <p role="status">Carregando tarefas…</p>}
          {tasks.error && (
            <Feedback error={tasks.error} retry={tasks.refresh} />
          )}
          {tasks.data?.length === 0 && (
            <p className="text-sm text-slate-600">
              Nenhuma tarefa{' '}
              {filter === 'pending'
                ? 'pendente '
                : filter === 'done'
                  ? 'concluída '
                  : ''}
              para esta empresa.
            </p>
          )}
          <ul className="space-y-2">
            {tasks.data?.map((task) => (
              <li key={task.id}>
                <a
                  href={taskHref(filter, task.id)}
                  aria-current={active?.id === task.id ? 'true' : undefined}
                  className={
                    'flex items-start gap-3 rounded-xl border p-4 ' +
                    (active?.id === task.id
                      ? 'border-accent bg-info'
                      : 'border-slate-200 hover:bg-slate-50')
                  }
                >
                  {task.completed ? (
                    <CheckCircle2
                      size={18}
                      className="mt-1 shrink-0 text-link"
                    />
                  ) : (
                    <Circle
                      size={18}
                      className="mt-1 shrink-0 text-slate-400"
                    />
                  )}
                  <span className="min-w-0">
                    <strong className="block break-words text-sm">
                      {task.title}
                    </strong>
                    <span className="text-sm text-slate-600">
                      {task.completed ? 'Concluída' : 'Pendente'}
                      {task.period &&
                        ' · Competência ' + periodLabel(task.period)}
                    </span>
                    <small className="block text-slate-500">
                      {task.due_date
                        ? 'Prazo ' + dateLabel(task.due_date)
                        : 'Prazo não informado'}
                    </small>
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </section>
        {active && (
          <TaskDetails
            key={active.id}
            task={active}
            changed={(updated) => {
              setNotice(
                updated.completed ? 'Tarefa concluída.' : 'Tarefa reaberta.',
              );
              window.location.hash = taskHref(
                filter,
                filter === 'all' ? updated.id : undefined,
              );
              tasks.refresh();
            }}
          />
        )}
      </div>
      {creating && (
        <NewTask
          url={listUrl}
          close={() => setCreating(false)}
          saved={(task) => {
            setCreating(false);
            setNotice('Tarefa criada.');
            window.location.hash = taskHref(
              filter === 'done' ? 'pending' : filter,
              task.id,
            );
            tasks.refresh();
          }}
        />
      )}
    </div>
  );
}
