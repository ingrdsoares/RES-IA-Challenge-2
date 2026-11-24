import { useState, type FormEvent } from 'react';
import { api } from '../../services/api';
import { Feedback, FormDialog, problem } from '../fiscal-data';

export interface RecordValues {
  title: string;
  period: string | null;
  due_date: string | null;
}

/** Tarefas e obrigações usam os mesmos campos; só mudam os nomes. */
export const recordKinds = {
  task: {
    field: 'title',
    label: 'Orientação da tarefa',
    missing: 'Informe a orientação da tarefa.',
    due: 'Prazo (opcional)',
    maxLength: 500,
    create: ['Nova tarefa', 'Criar tarefa', 'Criando…'],
    edit: 'Editar tarefa',
    remove: 'Excluir tarefa',
    path: '/tarefas/',
  },
  obligation: {
    field: 'name',
    label: 'Nome da obrigação',
    missing: 'Informe o nome da obrigação.',
    due: 'Vencimento (opcional)',
    maxLength: 120,
    create: ['Nova obrigação', 'Cadastrar obrigação', 'Cadastrando…'],
    edit: 'Editar obrigação',
    remove: 'Excluir obrigação',
    path: '/obrigacoes/',
  },
} as const;
export type RecordKind = keyof typeof recordKinds;

export function RecordForm<T>({
  kind,
  url,
  initial,
  close,
  saved,
}: {
  kind: RecordKind;
  url: string;
  initial?: RecordValues;
  close: () => void;
  saved: (item: T) => void;
}) {
  const text = recordKinds[kind];
  const [title, action, saving] = initial
    ? [text.edit, 'Salvar alterações', 'Salvando…']
    : text.create;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = new FormData(event.currentTarget);
    const name = String(form.get('name') || '').trim();
    if (!name) {
      setError(text.missing);
      return;
    }
    setBusy(true);
    setError('');
    try {
      saved(
        await api.request<T>(url, {
          method: initial ? 'PUT' : 'POST',
          body: JSON.stringify({
            [text.field]: name,
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
    <FormDialog title={title} close={close} busy={busy}>
      <form onSubmit={submit} className="space-y-4">
        <fieldset disabled={busy} className="space-y-4">
          <label className="field">
            {text.label}
            {kind === 'task' ? (
              <textarea
                name="name"
                rows={3}
                required
                maxLength={text.maxLength}
                defaultValue={initial?.title}
              />
            ) : (
              <input
                name="name"
                required
                maxLength={text.maxLength}
                placeholder="Ex. DAS de novembro"
                defaultValue={initial?.title}
              />
            )}
          </label>
          <label className="field">
            Competência (opcional)
            <input type="month" name="period" defaultValue={initial?.period ?? ''} />
          </label>
          <label className="field">
            {text.due}
            <input type="date" name="due" defaultValue={initial?.due_date ?? ''} />
          </label>
        </fieldset>
        {error && <Feedback error={error} />}
        <button className="primary" disabled={busy}>
          {busy ? saving : action}
        </button>
      </form>
    </FormDialog>
  );
}

export function ConfirmDelete({
  kind,
  item,
  close,
  done,
}: {
  kind: RecordKind;
  item: { id: string; title: string };
  close: () => void;
  done: () => void;
}) {
  const text = recordKinds[kind];
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function remove() {
    setBusy(true);
    setError('');
    try {
      await api.request<void>(text.path + item.id, { method: 'DELETE' });
      done();
    } catch (err) {
      setError(problem(err));
      setBusy(false);
    }
  }
  return (
    <FormDialog title={text.remove} close={close} busy={busy}>
      <div className="space-y-4 text-sm">
        <p className="break-words">
          <strong>{item.title}</strong> será removida e não poderá ser recuperada.
        </p>
        {error && <Feedback error={error} />}
        <div className="flex justify-end gap-2">
          <button type="button" className="secondary" onClick={close} disabled={busy}>
            Cancelar
          </button>
          <button type="button" className="primary" onClick={remove} disabled={busy}>
            {busy ? 'Excluindo…' : 'Excluir definitivamente'}
          </button>
        </div>
      </div>
    </FormDialog>
  );
}
