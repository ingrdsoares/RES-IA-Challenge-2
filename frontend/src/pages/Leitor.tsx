import { useEffect, useRef, useState } from 'react';
import {
  ArrowLeft,
  ExternalLink,
  FileText,
  List,
  MessageSquare,
} from 'lucide-react';
import { api } from '../services/api';
import { type NormMetadata, validity } from './Biblioteca';

interface Resolution extends Partial<NormMetadata> {
  state: 'exact' | 'anchor_unavailable' | 'version_unavailable';
  historical?: boolean;
  anchor_id: string | null;
  json_url: string | null;
  original_url: string | null;
}

interface Section {
  anchor_id: string;
  text: string;
}

interface Reading {
  request: string;
  resolution?: Resolution;
  sections?: Section[];
  textFailed?: boolean;
  error?: boolean;
}

function webLink(raw?: string | null) {
  if (!raw) return undefined;
  try {
    const url = new URL(raw);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : undefined;
  } catch {
    return undefined;
  }
}

function sectionTitle(section: Section, index: number) {
  const article =
    /^\s*(?:#+\s*)?(Art(?:igo)?\.?\s+\d+[º°o]?(?:[-–][\p{L}\d]+)?)/iu.exec(
      section.text,
    );
  if (article) return article[1];
  const first = section.text
    .split('\n', 1)[0]
    .replace(/^#+\s*/, '')
    .trim();
  return first.length && first.length <= 65 ? first : `Trecho ${index + 1}`;
}

export function Leitor({ params }: { params: URLSearchParams }) {
  const documentId = params.get('document_id');
  const versionId = params.get('version_id');
  const anchor = params.get('anchor_id');
  const conversation = params.get('conversa');
  const message = params.get('mensagem');
  const library = params.get('biblioteca');
  const conversationQuery = new URLSearchParams();
  if (conversation) conversationQuery.set('conversa', conversation);
  if (message) conversationQuery.set('mensagem', message);
  const citationQuery = new URLSearchParams({
    document_id: documentId || '',
    version_id: versionId || '',
  });
  if (anchor) citationQuery.set('anchor_id', anchor);
  const endpoint =
    !documentId || !versionId
      ? ''
      : anchor || conversation
        ? `/citacoes/resolver?${citationQuery}`
        : `/normas/${encodeURIComponent(documentId)}/versoes/${encodeURIComponent(versionId)}`;
  const [attempt, setAttempt] = useState(0);
  const [reading, setReading] = useState<Reading | null>(null);
  const current = reading?.request === endpoint ? reading : null;
  const resolution = current?.resolution;
  const cited = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!endpoint) return;
    const controller = new AbortController();
    const { signal } = controller;
    async function load() {
      const resolved = await api.request<Resolution>(endpoint, { signal });
      if (signal.aborted) return;
      setReading({ request: endpoint, resolution: resolved });
      const url = webLink(resolved.json_url);
      if (!url || resolved.state === 'version_unavailable') return;
      try {
        const response = await fetch(url, { signal, credentials: 'omit' });
        if (!response.ok) throw new Error();
        const body: { sections?: Section[] } = await response.json();
        if (
          !Array.isArray(body.sections) ||
          !body.sections.length ||
          !body.sections.every(
            (s) =>
              typeof s?.anchor_id === 'string' && typeof s.text === 'string',
          )
        )
          throw new Error();
        if (!signal.aborted)
          setReading({
            request: endpoint,
            resolution: resolved,
            sections: body.sections,
          });
      } catch {
        if (!signal.aborted)
          setReading({
            request: endpoint,
            resolution: resolved,
            textFailed: true,
          });
      }
    }
    load().catch(() => {
      if (!signal.aborted) setReading({ request: endpoint, error: true });
    });
    return () => controller.abort();
  }, [endpoint, attempt]);

  const exactAnchor =
    anchor &&
    resolution?.state === 'exact' &&
    resolution.anchor_id === anchor &&
    current?.sections?.some((section) => section.anchor_id === anchor)
      ? anchor
      : null;
  useEffect(() => {
    if (exactAnchor) {
      cited.current?.scrollIntoView({ block: 'center' });
      cited.current?.focus({ preventScroll: true });
    }
  }, [endpoint, exactAnchor]);

  function retry() {
    setReading(null);
    setAttempt((count) => count + 1);
  }
  const official = webLink(resolution?.official_url);
  const original = webLink(resolution?.original_url);
  const readable = resolution && resolution.state !== 'version_unavailable';
  const unavailableAnchor =
    readable &&
    anchor &&
    (resolution.state === 'anchor_unavailable' ||
      ((current?.sections ||
        current?.textFailed ||
        !webLink(resolution.json_url)) &&
        !exactAnchor));
  return (
    <div className="stack space-y-5">
      <nav
        aria-label="Voltar à origem"
        className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm font-semibold text-link"
      >
        {conversation && (
          <a
            className="inline-flex items-center gap-1.5 hover:underline"
            href={`#assistente?${conversationQuery}`}
          >
            <MessageSquare size={16} aria-hidden /> Voltar à resposta
          </a>
        )}
        <a
          className="inline-flex items-center gap-1.5 hover:underline"
          href={library ? `#normas?${new URLSearchParams(library)}` : '#normas'}
        >
          <ArrowLeft size={16} aria-hidden /> Biblioteca de normas
        </a>
      </nav>
      <header className="space-y-3">
        <h1 className="break-words text-3xl font-bold tracking-tight text-slate-900">
          {resolution?.title || 'Leitor da norma'}
        </h1>
        {resolution?.title && (
          <p className="text-sm text-slate-600">
            {[
              resolution.norm_type,
              resolution.authority,
              resolution.jurisdiction,
            ]
              .filter(Boolean)
              .join(' · ')}
          </p>
        )}
      </header>
      {!endpoint && (
        <p className="notice" role="alert">
          O link precisa identificar o documento e a versão. Escolha uma versão
          na biblioteca.
        </p>
      )}
      {endpoint && !current && (
        <p className="panel p-5 text-sm text-slate-600" role="status">
          Carregando a versão solicitada…
        </p>
      )}
      {current?.error && (
        <div className="panel space-y-3 p-5" role="alert">
          <p>Não foi possível consultar a versão solicitada.</p>
          <button className="secondary" onClick={retry}>
            Tentar novamente
          </button>
        </div>
      )}
      {resolution && (
        <>
          {resolution.historical && (
            <p className="rounded-lg border border-accent bg-notice px-4 py-3 text-sm text-ink">
              Versão histórica. A vigência desta versão já terminou.
            </p>
          )}
          {resolution.state === 'version_unavailable' && (
            <p className="notice" role="status">
              A versão solicitada está indisponível.
              {official && ' Consulte a publicação oficial.'}
            </p>
          )}
          {unavailableAnchor && (
            <p className="notice" role="status">
              O destaque do trecho citado está indisponível nesta versão.
            </p>
          )}
          {readable && (
            <>
              {current?.sections ? (
                <div className={current.sections.length > 1 ? "grid items-start gap-5 lg:grid-cols-[minmax(12rem,15rem)_minmax(0,1fr)]" : "grid gap-3"}>
                  <details key={versionId} open={current.sections.length > 1}
                    className="panel p-4 lg:sticky lg:top-4"
                    aria-label="Sumário da norma"
                  >
                    <summary className="flex cursor-pointer items-center gap-2 font-semibold text-slate-900">
                      <List size={17} aria-hidden /> Sumário
                    </summary>
                    <ul className="max-h-60 space-y-1 overflow-y-auto lg:max-h-[65vh]">
                      {current.sections.map((section, index) => (
                        <li key={section.anchor_id}>
                          <button
                            type="button"
                            className={`block w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-slate-100 ${section.anchor_id === exactAnchor ? 'bg-info font-semibold text-ink' : 'text-slate-700'}`}
                            onClick={() => {
                              const passage = document.getElementById(
                                `norm-section-${index}`,
                              );
                              passage?.scrollIntoView({ block: 'center' });
                              passage?.focus({ preventScroll: true });
                            }}
                          >
                            {sectionTitle(section, index)}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </details>
                  <article
                    className="panel min-w-0 divide-y divide-slate-100 px-5 sm:px-8"
                    aria-label="Texto da norma"
                  >
                    {current.sections.map((section, index) => {
                      const selected = section.anchor_id === exactAnchor;
                      return (
                        <section
                          key={section.anchor_id}
                          id={`norm-section-${index}`}
                          tabIndex={-1}
                          ref={selected ? cited : null}
                          className="scroll-mt-8 py-5 outline-offset-2"
                        >
                          {selected && (
                            <strong className="mb-2 block text-xs font-bold uppercase tracking-wide text-link">
                              Trecho citado
                            </strong>
                          )}
                          <p className="whitespace-pre-wrap break-words text-base leading-8 text-slate-800">
                            {selected ? (
                              <mark className="rounded-sm bg-highlight px-0.5 py-0.5 text-ink">
                                {section.text}
                              </mark>
                            ) : (
                              section.text
                            )}
                          </p>
                          {selected && <p className="mt-3 text-sm text-slate-600">
                            Versão · {resolution.version_label || versionId}
                          </p>}
                        </section>
                      );
                    })}
                  </article>
                </div>
              ) : current?.textFailed || !webLink(resolution.json_url) ? (
                <div className="panel space-y-3 p-5">
                  <p role="status" className="text-sm text-slate-700">
                    O texto para leitura na plataforma está indisponível.
                  </p>
                  {current?.textFailed && (
                    <button className="secondary" onClick={retry}>
                      Tentar carregar o texto novamente
                    </button>
                  )}
                </div>
              ) : (
                <p className="panel p-5 text-sm" role="status">
                  Carregando o texto da norma…
                </p>
              )}
              {original && (
                <a
                  href={original}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 text-sm font-semibold text-link hover:underline"
                >
                  <FileText size={16} aria-hidden /> Abrir arquivo original
                  desta versão <ExternalLink size={14} aria-hidden />
                </a>
              )}
            </>
          )}
          <div className="panel flex flex-wrap items-start justify-between gap-4 p-5">
            <dl className="flex flex-wrap gap-x-8 gap-y-4 text-sm">
              {!exactAnchor && <div>
                <dt className="text-xs font-semibold text-slate-500">Versão</dt>
                <dd className="mt-1 break-all font-medium">
                  {resolution.version_label || versionId}
                </dd>
              </div>}
              <div>
                <dt className="text-xs font-semibold text-slate-500">
                  Vigência
                </dt>
                <dd className="mt-1">
                  {validity(resolution.effective_from, resolution.effective_to)}
                </dd>
              </div>
              {Boolean(resolution.subjects?.length) && (
                <div>
                  <dt className="text-xs font-semibold text-slate-500">
                    Assuntos
                  </dt>
                  <dd className="mt-1">{resolution.subjects?.join(', ')}</dd>
                </div>
              )}
            </dl>
            {official && (
              <a
                href={official}
                target="_blank"
                rel="noreferrer"
                className="secondary inline-flex items-center gap-2"
              >
                Ver publicação oficial <ExternalLink size={15} aria-hidden />
              </a>
            )}
          </div>
        </>
      )}
    </div>
  );
}
