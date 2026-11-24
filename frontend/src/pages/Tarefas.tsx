import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import {
  Calendar,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Circle,
  List,
  Plus,
  RotateCcw,
  Sparkles,
} from 'lucide-react';
import { RecordDetail, useRecordNavigation } from './RecordDetail';
import { api } from '../services/api';
import { annualTasks, missingTasks } from './obrigacoesAno';
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

export type TaskCategory =
  | 'tributaria'
  | 'declaracao'
  | 'certidao'
  | 'trabalhista'
  | 'geral';

export const categoryLabels: Record<
  TaskCategory,
  { label: string; className: string }
> = {
  tributaria: {
    label: 'Tributária',
    className: 'bg-blue-100 text-blue-800 border-blue-200',
  },
  declaracao: {
    label: 'Declaração',
    className: 'bg-purple-100 text-purple-800 border-purple-200',
  },
  certidao: {
    label: 'Certidão',
    className: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  },
  trabalhista: {
    label: 'Trabalhista',
    className: 'bg-amber-100 text-amber-800 border-amber-200',
  },
  geral: {
    label: 'Geral',
    className: 'bg-slate-100 text-slate-700 border-slate-200',
  },
};

export function getTaskCategory(title: string): TaskCategory {
  const t = title.toLowerCase();
  if (/\b(das|guia|imposto|tribut|arrecada|recolhimento|darf)\b/.test(t))
    return 'tributaria';
  if (/\b(declara|dasn|defis|dirf|dmec|sped)\b/.test(t)) return 'declaracao';
  if (/\b(certid|cnd|crf|regularidade)\b/.test(t)) return 'certidao';
  if (
    /\b(folha|sal[áa]rio|funcion[áa]rio|empregad|fgts|pr[óo]-labore|inss)\b/.test(
      t,
    )
  )
    return 'trabalhista';
  return 'geral';
}

interface TaskEvent {
  id: string;
  completed: boolean;
  created_at: string;
}

function GenerateAnnualTasksDialog({
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
  const regime = company.regime.toLowerCase();
  const isMei =
    /\b(simei|mei)\b/.test(regime) || company.size.toLowerCase() === 'mei';
  const pending = existing.data
    ? missingTasks(annualTasks(today, isMei), existing.data)
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
          {isMei ? 'MEI' : 'Simples Nacional'}) que sua empresa ainda não tem:
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

function CalendarView({
  tasks,
  activeTaskId,
  onSelectTask,
}: {
  tasks: Task[];
  activeTaskId?: string;
  onSelectTask: (id: string) => void;
}) {
  const [currentDate, setCurrentDate] = useState(() => {
    const d = new Date();
    d.setDate(1);
    return d;
  });

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const monthNames = [
    'Janeiro',
    'Fevereiro',
    'Março',
    'Abril',
    'Maio',
    'Junho',
    'Julho',
    'Agosto',
    'Setembro',
    'Outubro',
    'Novembro',
    'Dezembro',
  ];

  function prevMonth() {
    setCurrentDate(new Date(year, month - 1, 1));
  }
  function nextMonth() {
    setCurrentDate(new Date(year, month + 1, 1));
  }

  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const firstDayOfWeek = new Date(year, month, 1).getDay();

  const daysArray = Array.from({ length: daysInMonth }, (_, i) => i + 1);
  const blanks = Array.from({ length: firstDayOfWeek }, (_, i) => i);

  const todayStr = new Date().toISOString().slice(0, 10);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-bold text-ink">
          {monthNames[month]} de {year}
        </h3>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={prevMonth}
            className="secondary p-1"
            title="Mês anterior"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            type="button"
            onClick={nextMonth}
            className="secondary p-1"
            title="Próximo mês"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-1 text-center text-xs font-semibold text-slate-500">
        {['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'].map((d) => (
          <div key={d} className="py-1">
            {d}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-1 text-xs">
        {blanks.map((b) => (
          <div
            key={'blank-' + b}
            className="h-20 rounded-lg bg-surface-muted/30 p-1"
          />
        ))}
        {daysArray.map((day) => {
          const dayStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
          const isToday = dayStr === todayStr;
          const dayTasks = tasks.filter((t) => t.due_date === dayStr);

          return (
            <div
              key={day}
              className={
                'flex h-20 flex-col justify-between overflow-y-auto rounded-lg border p-1 ' +
                (isToday
                  ? 'border-link bg-info/10 font-bold'
                  : 'border-slate-200 bg-white')
              }
            >
              <div className="flex items-center justify-between text-[11px]">
                <span className={isToday ? 'text-link' : 'text-slate-600'}>
                  {day}
                </span>
                {dayTasks.length > 0 && (
                  <span className="rounded-full bg-slate-200 px-1 text-[9px] font-bold text-slate-700">
                    {dayTasks.length}
                  </span>
                )}
              </div>
              <div className="mt-1 space-y-1">
                {dayTasks.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => onSelectTask(t.id)}
                    className={
                      'block w-full truncate rounded px-1 py-0.5 text-left text-[10px] font-medium leading-tight ' +
                      (t.id === activeTaskId
                        ? 'bg-link text-white'
                        : t.completed
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-amber-100 text-amber-900 hover:bg-amber-200')
                    }
                    title={t.title}
                  >
                    {t.completed ? '✓ ' : '• '}
                    {t.title}
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
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
  const selected = params.get('task');
  const [viewMode, setViewMode] = useState<'list' | 'calendar'>('list');
  const [selectedCategory, setSelectedCategory] = useState<'all' | TaskCategory>('all');
  const [generatingAnnual, setGeneratingAnnual] = useState(false);
  const [creating, setCreating] = useState(false);
  const [notice, setNotice] = useState('');

  const filteredTasks = tasks.data?.filter((task) => {
    if (selectedCategory === 'all') return true;
    return getTaskCategory(task.title) === selectedCategory;
  });

  const active =
    selected === null
      ? filteredTasks?.[0]
      : tasks.data?.find((task) => task.id === selected);
  const listHref = taskHref(filter);
  const navigation = useRecordNavigation(
    company.id,
    listHref,
    selected,
    !tasks.loading,
  );
  const missing = selected !== null && !!tasks.data && !active;

  return (
    <div
      className={
        'stack record-page' + (selected !== null ? ' record-open' : '')
      }
    >
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-3xl font-bold tracking-tight">Tarefas</h1>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="secondary inline-flex items-center gap-1.5"
            onClick={() => {
              setNotice('');
              setGeneratingAnnual(true);
            }}
          >
            <Sparkles size={16} className="text-amber-500" /> Gerar obrigações do ano
          </button>
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
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <nav
          aria-label="Filtrar tarefas por status"
          className="record-list-context flex flex-wrap gap-2"
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

        <div className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white p-1 text-xs">
          <button
            type="button"
            onClick={() => setViewMode('list')}
            className={
              'inline-flex items-center gap-1 rounded px-2.5 py-1 font-semibold ' +
              (viewMode === 'list'
                ? 'bg-slate-900 text-white'
                : 'text-slate-600 hover:bg-slate-100')
            }
          >
            <List size={14} /> Lista
          </button>
          <button
            type="button"
            onClick={() => setViewMode('calendar')}
            className={
              'inline-flex items-center gap-1 rounded px-2.5 py-1 font-semibold ' +
              (viewMode === 'calendar'
                ? 'bg-slate-900 text-white'
                : 'text-slate-600 hover:bg-slate-100')
            }
          >
            <Calendar size={14} /> Calendário
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        <span className="mr-1 font-medium text-slate-500">Categoria:</span>
        <button
          type="button"
          onClick={() => setSelectedCategory('all')}
          className={
            'rounded-full px-2.5 py-0.5 font-medium ' +
            (selectedCategory === 'all'
              ? 'bg-slate-800 text-white'
              : 'border border-slate-200 bg-white text-slate-600 hover:bg-slate-50')
          }
        >
          Todas
        </button>
        {(
          [
            'tributaria',
            'declaracao',
            'certidao',
            'trabalhista',
            'geral',
          ] as TaskCategory[]
        ).map((cat) => {
          const info = categoryLabels[cat];
          const isSelected = selectedCategory === cat;
          return (
            <button
              key={cat}
              type="button"
              onClick={() => setSelectedCategory(cat)}
              className={
                'rounded-full border px-2.5 py-0.5 font-medium ' +
                (isSelected
                  ? 'border-slate-800 bg-slate-800 text-white'
                  : `${info.className} hover:opacity-80`)
              }
            >
              {info.label}
            </button>
          );
        })}
      </div>

      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}

      <div className="grid items-start gap-4 lg:grid-cols-[1.25fr_1fr]">
        <section
          className="record-list-context panel space-y-3"
          aria-label="Lista de tarefas"
        >
          {tasks.loading && <p role="status">Carregando tarefas…</p>}
          {tasks.error && (
            <Feedback error={tasks.error} retry={tasks.refresh} />
          )}
          {filteredTasks?.length === 0 && (
            <p className="text-sm text-slate-600">
              Nenhuma tarefa{' '}
              {filter === 'pending'
                ? 'pendente '
                : filter === 'done'
                  ? 'concluída '
                  : ''}
              encontrada para os filtros selecionados.
            </p>
          )}

          {viewMode === 'calendar' ? (
            <CalendarView
              tasks={filteredTasks || []}
              activeTaskId={active?.id}
              onSelectTask={(id) => {
                window.location.hash = taskHref(filter, id);
              }}
            />
          ) : (
            <ul ref={navigation.list} className="space-y-2">
              {filteredTasks?.map((task) => {
                const cat = getTaskCategory(task.title);
                const catInfo = categoryLabels[cat];
                return (
                  <li key={task.id}>
                    <a
                      href={taskHref(filter, task.id)}
                      data-record-id={task.id}
                      onClick={navigation.openRecord}
                      aria-current={active?.id === task.id ? 'true' : undefined}
                      className="record-option flex items-start gap-3 rounded-xl border p-4"
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
                      <span className="min-w-0 flex-1">
                        <div className="mb-1 flex flex-wrap items-center gap-1.5">
                          <span
                            className={`rounded px-1.5 py-0.5 text-[10px] font-semibold border ${catInfo.className}`}
                          >
                            {catInfo.label}
                          </span>
                        </div>
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
                );
              })}
            </ul>
          )}
        </section>
        {(active || selected !== null) && (
          <RecordDetail
            title={missing ? 'Tarefa não encontrada' : 'Detalhe da tarefa'}
            listHref={listHref}
            backLabel="Voltar à lista de tarefas"
            navigation={navigation}
          >
            {missing && (
              <a className="secondary" href={taskHref('all')}>
                Ver todas as tarefas
              </a>
            )}
            {tasks.loading && (
              <p className="lg:hidden" role="status">
                Carregando tarefa…
              </p>
            )}
            {tasks.error && (
              <div className="lg:hidden">
                <Feedback error={tasks.error} retry={tasks.refresh} />
              </div>
            )}
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
          </RecordDetail>
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
      {generatingAnnual && (
        <GenerateAnnualTasksDialog
          company={company}
          url={listUrl}
          close={() => setGeneratingAnnual(false)}
          done={() => {
            setGeneratingAnnual(false);
            setNotice('Obrigações fiscais do ano geradas com sucesso!');
            tasks.refresh();
          }}
        />
      )}
    </div>
  );
}
