import { useState, type FormEvent } from 'react';
import { Archive, ArchiveRestore, Pencil, Search } from 'lucide-react';
import { api } from '../../services/api';
import { Feedback, FormDialog, problem } from '../fiscal-data';

interface Chat {
  id: string;
  title: string;
  archived_at?: string | null;
}

function Rename({
  chat,
  close,
  saved,
}: {
  chat: Chat;
  close: () => void;
  saved: (chat: Chat) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const title = String(new FormData(event.currentTarget).get('title') || '').trim();
    if (!title) {
      setError('Informe o título da conversa.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      saved(
        await api.request<Chat>('/conversas/' + chat.id, {
          method: 'PATCH',
          body: JSON.stringify({ title }),
        }),
      );
    } catch (err) {
      setError(problem(err));
      setBusy(false);
    }
  }
  return (
    <FormDialog title="Renomear conversa" close={close} busy={busy}>
      <form onSubmit={submit} className="space-y-4">
        <label className="field">
          Título
          <input name="title" required maxLength={120} defaultValue={chat.title} disabled={busy} />
        </label>
        {error && <Feedback error={error} />}
        <button className="primary" disabled={busy}>
          {busy ? 'Salvando…' : 'Salvar'}
        </button>
      </form>
    </FormDialog>
  );
}

export function ConversationHistory({
  conversations,
  currentId,
  href,
  changed,
}: {
  conversations: Chat[];
  currentId: string | null;
  href: (id: string) => string;
  changed: (chat: Chat) => void;
}) {
  const [search, setSearch] = useState('');
  const [showArchived, setShowArchived] = useState(false);
  const [renaming, setRenaming] = useState<Chat>();
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  async function archive(chat: Chat) {
    setBusy(chat.id);
    setError('');
    try {
      changed(
        await api.request<Chat>('/conversas/' + chat.id, {
          method: 'PATCH',
          body: JSON.stringify({ archived: !chat.archived_at }),
        }),
      );
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy('');
    }
  }

  const shown = conversations.filter(
    (chat) =>
      !!chat.archived_at === showArchived &&
      chat.title.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <>
      <div className="my-2 flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs">
        <Search size={14} className="shrink-0 text-slate-400" />
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filtrar conversas…"
          className="w-full border-0 bg-transparent p-0 text-xs outline-none"
        />
      </div>
      <label className="mb-2 flex items-center gap-2 text-xs text-slate-600">
        <input
          type="checkbox"
          checked={showArchived}
          onChange={(e) => setShowArchived(e.target.checked)}
        />
        Mostrar arquivadas
      </label>
      {error && <Feedback error={error} />}
      <nav
        className="max-h-60 space-y-1 overflow-auto lg:max-h-[58vh]"
        aria-label="Histórico de conversas"
      >
        {shown.length === 0 && (
          <p className="text-sm text-slate-500">
            {showArchived ? 'Nenhuma conversa arquivada.' : 'Nenhuma conversa encontrada.'}
          </p>
        )}
        {shown.map((chat) => (
          <div key={chat.id} className="flex items-center gap-1">
            <a
              href={href(chat.id)}
              aria-current={chat.id === currentId ? 'page' : undefined}
              className={
                'block min-w-0 flex-1 break-words rounded-lg px-3 py-2 text-sm hover:bg-slate-100 ' +
                (chat.id === currentId ? 'bg-info font-semibold text-ink' : 'text-slate-700')
              }
            >
              <span className="line-clamp-2">{chat.title}</span>
            </a>
            <button
              type="button"
              className="touch-link rounded-lg p-2 text-slate-500 hover:bg-slate-100"
              aria-label={'Renomear ' + chat.title}
              onClick={() => setRenaming(chat)}
            >
              <Pencil size={15} aria-hidden />
            </button>
            <button
              type="button"
              className="touch-link rounded-lg p-2 text-slate-500 hover:bg-slate-100"
              aria-label={(chat.archived_at ? 'Restaurar ' : 'Arquivar ') + chat.title}
              onClick={() => archive(chat)}
              disabled={busy === chat.id}
            >
              {chat.archived_at ? (
                <ArchiveRestore size={15} aria-hidden />
              ) : (
                <Archive size={15} aria-hidden />
              )}
            </button>
          </div>
        ))}
      </nav>
      {renaming && (
        <Rename
          chat={renaming}
          close={() => setRenaming(undefined)}
          saved={(chat) => {
            setRenaming(undefined);
            changed(chat);
          }}
        />
      )}
    </>
  );
}
