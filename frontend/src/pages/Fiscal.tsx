import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  FileText,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  UploadCloud,
} from 'lucide-react';
import { RecordDetail, useRecordNavigation } from './RecordDetail';
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

function formatFileSize(bytes: number) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

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
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const request = useRef<{ body: string; key: string }>();

  function handleFile(file: File | null) {
    if (!file) {
      setSelectedFile(null);
      setFilePreview(null);
      return;
    }
    if (!acceptedTypes.includes(file.type) || file.size > 10 * 1024 * 1024 || !file.size) {
      setError('Selecione um PDF, PNG ou JPEG com conteúdo e até 10 MiB.');
      return;
    }
    setError('');
    setSelectedFile(file);
    if (file.type.startsWith('image/')) {
      setFilePreview(URL.createObjectURL(file));
    } else {
      setFilePreview(null);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const data = new FormData(event.currentTarget);
    const attachment = selectedFile;
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

        <div className="space-y-2">
          <span className="block text-sm font-semibold">
            Arquivo {evidenceId ? '' : '(opcional)'}
          </span>
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragging(false);
              const f = e.dataTransfer.files[0];
              if (f) handleFile(f);
            }}
            onClick={() => fileInputRef.current?.click()}
            className={
              'flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-4 text-center cursor-pointer transition-colors ' +
              (isDragging
                ? 'border-link bg-info/10'
                : 'border-slate-300 bg-surface-muted hover:border-slate-400')
            }
          >
            <UploadCloud size={28} className="text-slate-400" />
            <p className="text-xs text-slate-600">
              <strong className="text-link">Clique para selecionar</strong> ou
              arraste o arquivo aqui
            </p>
            <small className="text-[11px] text-slate-500">
              PDF, PNG ou JPEG de até 10 MiB.
            </small>
            <input
              ref={fileInputRef}
              type="file"
              accept={acceptedTypes.join(',')}
              className="hidden"
              onChange={(e) => handleFile(e.target.files?.[0] || null)}
              disabled={busy}
            />
          </div>

          {selectedFile && (
            <div className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white p-2.5 text-xs">
              <div className="flex items-center gap-2 min-w-0">
                {filePreview ? (
                  <img
                    src={filePreview}
                    alt="Pré-visualização"
                    className="h-10 w-10 rounded object-cover border"
                  />
                ) : (
                  <div className="flex h-10 w-10 items-center justify-center rounded bg-slate-100 font-bold text-slate-600">
                    PDF
                  </div>
                )}
                <div className="min-w-0 truncate">
                  <strong className="block truncate">{selectedFile.name}</strong>
                  <span className="text-slate-500">
                    {formatFileSize(selectedFile.size)}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  handleFile(null);
                  if (fileInputRef.current) fileInputRef.current.value = '';
                }}
                className="text-slate-400 hover:text-rose-600 p-1"
                title="Remover anexo"
              >
                <Trash2 size={16} />
              </button>
            </div>
          )}
        </div>

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

function getValidityStatus(validUntil?: string | null) {
  if (!validUntil) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(validUntil + 'T00:00:00');
  const diffDays = Math.ceil((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  if (diffDays < 0) {
    return {
      state: 'expired' as const,
      label: `Expirada (venceu há ${Math.abs(diffDays)} dia${Math.abs(diffDays) === 1 ? '' : 's'})`,
      className: 'bg-rose-100 text-rose-800 border-rose-200',
      diffDays,
    };
  }
  if (diffDays <= 30) {
    return {
      state: 'warning' as const,
      label: `Atenção: vence em ${diffDays} dia${diffDays === 1 ? '' : 's'} (renovação recomendada)`,
      className: 'bg-amber-100 text-amber-800 border-amber-200',
      diffDays,
    };
  }
  return {
    state: 'valid' as const,
    label: `Válida (restam ${diffDays} dias)`,
    className: 'bg-emerald-100 text-emerald-800 border-emerald-200',
    diffDays,
  };
}

function EvidenceDetail({ evidence }: { evidence: Evidence }) {
  const [busy, setBusy] = useState(false);
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  const validity = getValidityStatus(evidence.valid_until);
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
    <>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-semibold text-link">{kindNames[evidence.kind]}</p>
        {validity && (
          <span
            className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${validity.className}`}
          >
            {validity.state === 'valid' ? (
              <CheckCircle2 size={13} />
            ) : (
              <AlertTriangle size={13} />
            )}
            {validity.label}
          </span>
        )}
      </div>
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
        <p className="record-note text-sm">
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
    </>
  );
}

function evidenceHref(scope: Scope, id?: string) {
  const params = new URLSearchParams({ scope });
  if (id) params.set('evidence', id);
  return '#fiscal?' + params;
}

export function Fiscal({ company, params }: PageProps) {
  const requested = params.get('scope');
  const scope: Scope =
    scopes.find((item) => item === requested) || 'registration';
  const base = `/empresas/${company.id}`;
  const status = useRead<FiscalStatus>(base + '/situacao-fiscal', readJson);
  const evidence = useRead<Evidence[]>(base + '/evidencias', readList);
  const [showForm, setShowForm] = useState(false);
  const [yearFilter, setYearFilter] = useState('all');
  const [textSearch, setTextSearch] = useState('');
  const selected = params.get('evidence');
  const listHref = evidenceHref(scope);
  const navigation = useRecordNavigation(company.id, listHref, selected, !evidence.loading);
  const [notice, setNotice] = useState('');
  const items = evidence.data?.filter((item) => item.scope === scope).reverse();

  const availableYears = Array.from(
    new Set(
      items
        ?.map((it) => (it.period || it.created_at || '').slice(0, 4))
        .filter(Boolean),
    ),
  ).sort().reverse();

  const filteredItems = items?.filter((item) => {
    if (yearFilter !== 'all') {
      const itemYear = (item.period || item.created_at || '').slice(0, 4);
      if (itemYear !== yearFilter) return false;
    }
    if (textSearch.trim()) {
      const term = textSearch.toLowerCase();
      const matchKind = (kindNames[item.kind] || '').toLowerCase().includes(term);
      const matchPeriod = (item.period || '').includes(term);
      if (!matchKind && !matchPeriod) return false;
    }
    return true;
  });

  const active = selected === null ? filteredItems?.[0] : items?.find((item) => item.id === selected);
  const missing = selected !== null && !!items && !active;
  function refresh() {
    status.refresh();
    evidence.refresh();
  }
  return (
    <div className={'stack record-page' + (selected !== null ? ' record-open' : '')}>
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
      <nav aria-label="Escopo fiscal" className="record-list-context flex flex-wrap gap-2">
        {scopes.map((item) => (
          <a
            key={item}
            href={evidenceHref(item)}
            aria-current={scope === item ? 'page' : undefined}
            className={scope === item ? 'primary' : 'secondary'}
          >
            {scopeNames[item]}
          </a>
        ))}
      </nav>

      {scope === 'federal_certificate' && (
        <aside className="rounded-xl border border-sky-200 bg-sky-50/70 p-4 text-xs text-sky-950 flex flex-wrap items-center justify-between gap-3">
          <div>
            <strong className="block text-sm font-semibold">Emissão Oficial da CND Federal</strong>
            <span className="text-slate-600">
              Certidão conjunta de débitos da Receita Federal e Procuradoria-Geral da Fazenda Nacional (PGFN).
            </span>
          </div>
          <a
            href="https://solucoes.receita.fazenda.gov.br/servicos/certidaointernet/pj/emitir"
            target="_blank"
            rel="noreferrer"
            className="primary inline-flex items-center gap-1.5 py-1.5 px-3 text-xs font-semibold"
          >
            Emitir CND no portal oficial <ExternalLink size={13} />
          </a>
        </aside>
      )}

      <section className="record-list-context panel space-y-3">
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
        <section className="record-list-context panel space-y-4">
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

          {items && items.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">
              <div className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2 py-1 min-w-[140px] flex-1">
                <Search size={14} className="text-slate-400 shrink-0" />
                <input
                  type="search"
                  value={textSearch}
                  onChange={(e) => setTextSearch(e.target.value)}
                  placeholder="Buscar documento ou competência…"
                  className="w-full border-0 bg-transparent p-0 text-xs outline-none"
                />
              </div>
              {availableYears.length > 1 && (
                <select
                  value={yearFilter}
                  onChange={(e) => setYearFilter(e.target.value)}
                  className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs"
                >
                  <option value="all">Todos os anos</option>
                  {availableYears.map((yr) => (
                    <option key={yr} value={yr}>
                      Ano {yr}
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}

          {evidence.loading && <p role="status">Carregando evidências…</p>}
          {evidence.error && (
            <Feedback error={evidence.error} retry={evidence.refresh} />
          )}
          {filteredItems?.length === 0 && (
            <p className="rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
              Nenhuma evidência encontrada neste escopo.
            </p>
          )}
          <ul ref={navigation.list} className="space-y-2">
            {filteredItems?.map((item) => {
              const validity = getValidityStatus(item.valid_until);
              return (
                <li key={item.id}>
                  <a
                    href={evidenceHref(scope, item.id)}
                    data-record-id={item.id}
                    onClick={navigation.openRecord}
                    aria-current={active?.id === item.id ? 'true' : undefined}
                    className="record-option flex w-full items-start gap-3 rounded-lg border p-3 text-sm"
                  >
                    <FileText
                      size={18}
                      className="mt-0.5 shrink-0 text-link"
                    />
                    <span className="min-w-0 flex-1">
                      <strong className="block truncate">
                        {kindNames[item.kind]}
                        {item.period && ' · ' + periodLabel(item.period)}
                      </strong>
                      <span className="block text-slate-600">
                        {originLabel(item)} · {dateLabel(item.created_at)}
                      </span>
                      {validity && (
                        <span
                          className={`mt-1.5 inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-semibold border ${validity.className}`}
                        >
                          {validity.state === 'valid' ? (
                            <CheckCircle2 size={12} />
                          ) : (
                            <AlertTriangle size={12} />
                          )}
                          {validity.label}
                        </span>
                      )}
                    </span>
                  </a>
                </li>
              );
            })}
          </ul>
        </section>
        {(active || selected !== null) && <RecordDetail
          title={missing ? 'Evidência não encontrada' : 'Detalhe da evidência'}
          listHref={listHref}
          backLabel="Voltar à lista de evidências"
          navigation={navigation}
        >
          {missing && <a href={listHref} className="secondary">Ver evidências deste escopo</a>}
          {evidence.loading && <p className="lg:hidden" role="status">Carregando evidência…</p>}
          {evidence.error && <div className="lg:hidden"><Feedback error={evidence.error} retry={evidence.refresh} /></div>}
          {active && <EvidenceDetail key={active.id} evidence={active} />}
        </RecordDetail>}
      </div>
      {showForm && (
        <NewEvidence
          key={base + scope}
          scope={scope}
          base={base}
          close={() => setShowForm(false)}
          recorded={refresh}
          saved={(id) => {
            window.location.hash = evidenceHref(scope, id);
            setShowForm(false);
            setNotice('Evidência registrada.');
            refresh();
          }}
        />
      )}
    </div>
  );
}
