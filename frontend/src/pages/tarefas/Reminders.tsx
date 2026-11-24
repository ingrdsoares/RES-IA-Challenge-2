import { useState } from 'react';
import { BellRing } from 'lucide-react';
import { api } from '../../services/api';
import type { Account } from '../../types';
import { Feedback, problem, readJson, useRead } from '../fiscal-data';

export function Reminders() {
  const account = useRead<Account>('/auth/session', readJson);
  const [changed, setChanged] = useState<Account>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const current = changed ?? account.data;

  async function toggle(enabled: boolean) {
    setBusy(true);
    setError('');
    try {
      setChanged(
        await api.request<Account>('/auth/preferences', {
          method: 'PATCH',
          body: JSON.stringify({ reminders_enabled: enabled }),
        }),
      );
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="record-list-context panel space-y-2" aria-label="Lembretes">
      <label className="flex items-center gap-3 font-semibold">
        <BellRing size={18} aria-hidden className="text-link" />
        <input
          type="checkbox"
          checked={!!current?.reminders_enabled}
          disabled={!current || busy}
          onChange={(event) => toggle(event.target.checked)}
        />
        Receber lembretes por e-mail
      </label>
      <p className="text-sm text-ink-muted">
        {current && `Para ${current.email}: `}um aviso 7 dias antes, na véspera e no dia do
        vencimento, com as datas e a quantidade de pendências. Os títulos não vão no e-mail.
      </p>
      {account.error && <Feedback error={account.error} retry={account.refresh} />}
      {error && <Feedback error={error} />}
    </section>
  );
}
