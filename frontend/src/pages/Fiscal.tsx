import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { FileText, Plus, RefreshCw } from 'lucide-react';
import { api } from '../services/api';
import {
  dateLabel,
  Feedback,
  FormDialog,
  IndicatorInfo,
  kindNames,
  originLabel,
  periodLabel,
  problem,
  readJson,
  readList,
  scopeNames,
  scopes,
  useRead,
} from './fiscal-data';
import type { Evidence, FiscalStatus, PageProps, Scope } from './fiscal-data';

const kindsByScope: Record<Scope, (keyof typeof kindNames)[]> = {
  registration: ['registration', 'other'],
  federal_certificate: ['certificate', 'other'],
  obligations: ['guide', 'payment', 'declaration', 'other'],
};
const acceptedTypes = ['application/pdf', 'image/png', 'image/jpeg'];

function NewEvidence({
  scope,
  base,
  close,
  saved,
  recorded,
}: {
  scope: Scope;
  base: string;
  close: () => void;
  saved: (id: string) => void;
  recorded: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [evidenceId, setEvidenceId] = useState<string>();
  const request = useRef<{ body: string; key: string }>();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const data = new FormData(event.currentTarget);
    const file = data.get('file');
    const attachment = file instanceof File && file.name ? file : null;
    if (
      attachment &&
      (!acceptedTypes.includes(attachment.type) ||
        attachment.size > 10 * 1024 * 1024 ||
        !attachment.size)
    ) {
      setError('Selecione um PDF, PNG ou JPEG com conteúdo e até 10 MiB.');
      return;
    }
    setBusy(true);
    setError('');
    let id = evidenceId;
    try {
      if (!id) {
        const body = JSON.stringify({
          kind: data.get('kind'),
          scope,
          period: data.get('period') || null,
          valid_until: data.get('valid_until') || null,
        });
        if (request.current?.body !== body)
          request.current = { body, key: crypto.randomUUID() };
        const evidence = await api.request<Evidence>(base + '/evidencias', {
          method: 'POST',
          headers: { 'Idempotency-Key': request.current.key },
          body,
        });
        id = evidence.id;
        setEvidenceId(id);
      }
      if (attachment) {
        await api.request(`/evidencias/${id}/arquivo`, {
          method: 'PUT',
          headers: { 'Content-Type': attachment.type },
          body: attachment,
        });
      }
      saved(id);
    } catch (err) {
      if (id) recorded();
      setError(
        (id ? 'Dados registrados. Falha ao enviar o anexo. ' : '') +
          problem(err),
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <FormDialog title="Adicionar documento" busy={busy} close={close}>
      <form onSubmit={submit} className="space-y-4">
        <p className="text-sm text-slate-600">
          Escopo · {scopeNames[scope]}
          <br />
          Origem · Declaração do usuário
        </p>
        <fieldset disabled={busy || !!evidenceId} className="space-y-3">
          <label className="field">
            Tipo de documento
            <select name="kind">
              {kindsByScope[scope].map((kind) => (
                <option key={kind} value={kind}>
                  {kindNames[kind]}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Competência (opcional)
            <input type="month" name="period" />
          </label>
          <label className="field">
            Validade (opcional)
            <input type="date" name="valid_until" />
          </label>
        </fieldset>
        <label className="field">
          Arquivo {evidenceId ? '' : '(opcional)'}
          <input
            name="file"
            type="file"
            accept={acceptedTypes.join(',')}
            required={!!evidenceId}
            disabled={busy}
          />
          <small className="font-normal text-slate-500">
            PDF, PNG ou JPEG de até 10 MiB.
          </small>
        </label>
        {error && <Feedback error={error} />}
        <button className="primary" disabled={busy}>
          {busy
            ? 'Salvando…'
            : evidenceId
              ? 'Reenviar anexo'
              : 'Registrar evidência'}
        </button>
      </form>
    </FormDialog>
  );
}

function EvidenceDetail({ evidence }: { evidence: Evidence }) {
  const [busy, setBusy] = useState(false);
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  async function locateFile() {
    setBusy(true);
    setError('');
    try {
      const file = await api.request<{ url: string }>(
        `/evidencias/${evidence.id}/arquivo`,
      );
      const target = new URL(file.url);
      if (!['https:', 'http:'].includes(target.protocol))
        throw new Error('Link do anexo indisponível.');
      setUrl(target.href);
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <aside className="panel space-y-4" aria-label="Detalhe da evidência">
      <h2 className="font-bold">Detalhe da evidência</h2>
      <p className="font-semibold text-emerald-800">
        {kindNames[evidence.kind]}
      </p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
        <dt>Origem</dt>
        <dd>{originLabel(evidence)}</dd>
        <dt>Coleta</dt>
        <dd>{dateLabel(evidence.created_at, true)}</dd>
        <dt>Abrangência</dt>
        <dd>{scopeNames[evidence.scope]}</dd>
        <dt>Competência</dt>
        <dd>{periodLabel(evidence.period)}</dd>
        <dt>Validade</dt>
        <dd>{dateLabel(evidence.valid_until)}</dd>
      </dl>
      {evidence.kind === 'guide' && (
        <p className="text-sm text-slate-600">
          Esta guia documenta a emissão. O pagamento continua sem verificação.
        </p>
      )}
      {url ? (
        <a href={url} target="_blank" rel="noreferrer" className="secondary">
          Abrir arquivo
        </a>
      ) : (
        <button onClick={locateFile} disabled={busy} className="secondary">
          {busy ? 'Consultando…' : 'Consultar anexo'}
        </button>
      )}
      {error && <Feedback error={error} />}
    </aside>
  );
}

export function Fiscal({ company, params }: PageProps) {
  const requested = params.get('scope');
  const scope: Scope =
    scopes.find((item) => item === requested) || 'registration';
  const base = `/empresas/${company.id}`;
  const status = useRead<FiscalStatus>(base + '/situacao-fiscal', readJson);
  const evidence = useRead<Evidence[]>(base + '/evidencias', readList);
  const [showForm, setShowForm] = useState(false);
  const [selected, setSelected] = useState('');
  const [notice, setNotice] = useState('');
  const items = evidence.data?.filter((item) => item.scope === scope).reverse();
  const active = items?.find((item) => item.id === selected) || items?.[0];
  function refresh() {
    status.refresh();
    evidence.refresh();
  }
  return (
    <div className="stack">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-3xl font-bold tracking-tight">Situação fiscal</h1>
        <button
          onClick={() => {
            setNotice('');
            refresh();
          }}
          className="secondary"
          disabled={status.loading || evidence.loading}
        >
          <RefreshCw size={16} /> Atualizar consultas
        </button>
      </div>
      <nav aria-label="Escopo fiscal" className="flex flex-wrap gap-2">
        {scopes.map((item) => (
          <a
            key={item}
            href={`#fiscal?scope=${item}`}
            aria-current={scope === item ? 'page' : undefined}
            className={scope === item ? 'primary' : 'secondary'}
          >
            {scopeNames[item]}
          </a>
        ))}
      </nav>
      <section className="panel space-y-3">
        <h2 className="text-lg font-bold">{scopeNames[scope]}</h2>
        {status.loading && <p role="status">Carregando indicador…</p>}
        {status.error && (
          <Feedback error={status.error} retry={status.refresh} />
        )}
        {status.data && (
          <IndicatorInfo scope={scope} indicator={status.data[scope]} />
        )}
        <p className="border-t border-slate-100 pt-3 text-sm text-slate-600">
          A atualização consulta as evidências da empresa. A consulta automática
          aos órgãos públicos está indisponível neste canal.
        </p>
      </section>
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      <div className="grid items-start gap-4 lg:grid-cols-[1.25fr_1fr]">
        <section className="panel space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-bold">Evidências registradas</h2>
            <button
              className="secondary"
              onClick={() => {
                setNotice('');
                setShowForm(true);
              }}
            >
              <Plus size={16} /> Adicionar documento
            </button>
          </div>
          {evidence.loading && <p role="status">Carregando evidências…</p>}
          {evidence.error && (
            <Feedback error={evidence.error} retry={evidence.refresh} />
          )}
          {items?.length === 0 && (
            <p className="rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
              Nenhuma evidência registrada neste escopo.
            </p>
          )}
          <ul className="space-y-2">
            {items?.map((item) => (
              <li key={item.id}>
                <button
                  onClick={() => setSelected(item.id)}
                  aria-pressed={active?.id === item.id}
                  className={
                    'flex w-full items-start gap-3 rounded-lg border p-3 text-left text-sm ' +
                    (active?.id === item.id
                      ? 'border-emerald-300 bg-emerald-50'
                      : 'border-slate-200 hover:bg-slate-50')
                  }
                >
                  <FileText
                    size={18}
                    className="mt-0.5 shrink-0 text-emerald-800"
                  />
                  <span>
                    <strong className="block">
                      {kindNames[item.kind]}
                      {item.period && ' · ' + periodLabel(item.period)}
                    </strong>
                    <span className="text-slate-600">
                      {originLabel(item)} · {dateLabel(item.created_at)}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
        {active && <EvidenceDetail key={active.id} evidence={active} />}
      </div>
      {showForm && (
        <NewEvidence
          key={base + scope}
          scope={scope}
          base={base}
          close={() => setShowForm(false)}
          recorded={refresh}
          saved={(id) => {
            setSelected(id);
            setShowForm(false);
            setNotice('Evidência registrada.');
            refresh();
          }}
        />
      )}
    </div>
  );
}
