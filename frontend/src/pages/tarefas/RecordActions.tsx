import { useState } from 'react';
import { Pencil, Trash2 } from 'lucide-react';
import { ConfirmDelete, RecordForm, recordKinds } from './RecordForm';
import type { RecordKind, RecordValues } from './RecordForm';

export function RecordActions<T>({
  kind,
  item,
  edited,
  removed,
}: {
  kind: RecordKind;
  item: RecordValues & { id: string };
  edited: (item: T) => void;
  removed: () => void;
}) {
  const [open, setOpen] = useState<'edit' | 'delete'>();
  const close = () => setOpen(undefined);
  return (
    <div className="flex flex-wrap gap-2">
      <button type="button" className="secondary" onClick={() => setOpen('edit')}>
        <Pencil size={15} aria-hidden /> Editar
      </button>
      <button type="button" className="secondary" onClick={() => setOpen('delete')}>
        <Trash2 size={15} aria-hidden /> Excluir
      </button>
      {open === 'edit' && (
        <RecordForm<T>
          kind={kind}
          url={recordKinds[kind].path + item.id}
          initial={item}
          close={close}
          saved={(updated) => {
            close();
            edited(updated);
          }}
        />
      )}
      {open === 'delete' && (
        <ConfirmDelete kind={kind} item={item} close={close} done={removed} />
      )}
    </div>
  );
}
