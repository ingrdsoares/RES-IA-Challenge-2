import { useEffect, useState, type FormEvent } from 'react';
import {
  ArrowRight,
  BookOpen,
  ChevronRight,
  FileText,
  Search,
} from 'lucide-react';
import { api } from '../services/api';

export interface NormMetadata {
  document_id: string;
  version_id: string;
  title: string;
  version_label: string;
  norm_type: string;
  authority: string;
  jurisdiction: string | null;
  subjects: string[];
  effective_from: string | null;
  effective_to: string | null;
  official_url: string;
}

const filters = [
  'q',
  'subject',
  'norm_type',
  'authority',
  'effective_on',
] as const;
const topics = [
  'MEI e SIMEI',
  'Simples Nacional',
  'Tributos e guias',
  'Declarações',
  'Notas fiscais',
];

export function validity(from?: string | null, to?: string | null) {
  const format = (value: string) => value.split('-').reverse().join('/');
  if (from && to) return `${format(from)} a ${format(to)}`;
  if (from) return `A partir de ${format(from)}`;
  if (to) return `Até ${format(to)}`;
  return 'Não informada';
}

interface CatalogPage {
  items: NormMetadata[];
  next_cursor: string | null;
}

function catalogLink(params: URLSearchParams) {
  return params.size ? `#normas?${params}` : '#normas';
}

export function Biblioteca({ params }: { params: URLSearchParams }) {
  const applied = new URLSearchParams();
  for (const name of [...filters, 'cursor']) {
    const value = params.get(name);
    if (value) applied.set(name, value);
  }
  const search = applied.toString();
  const [result, setResult] = useState<{
    search: string;
    page?: CatalogPage;
    error?: boolean;
  } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const page = result?.search === search ? result.page : undefined;
  const error = result?.search === search && result.error;

  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams(search);
    query.set('limit', '20');
    api
      .request<CatalogPage>(`/normas?${query}`, { signal: controller.signal })
      .then((page) => {
        if (!controller.signal.aborted) setResult({ search, page });
      })
      .catch(() => {
        if (!controller.signal.aborted) setResult({ search, error: true });
      });
    return () => controller.abort();
  }, [search, attempt]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const query = new URLSearchParams();
    for (const name of filters) {
      const value = String(values.get(name) || '').trim();
      if (value) query.set(name, value);
    }
    window.location.hash = catalogLink(query);
  }

  function pageLink(cursor?: string | null) {
    const query = new URLSearchParams(search);
    if (cursor) query.set('cursor', cursor);
    else query.delete('cursor');
    return catalogLink(query);
  }

  function openDocument(norm: NormMetadata) {
    const query = new URLSearchParams({
      document_id: norm.document_id,
      version_id: norm.version_id,
    });
    if (search) query.set('biblioteca', search);
    return `#leitor?${query}`;
  }

  const distinct = (values: string[]) =>
    [...new Set(values)].sort((a, b) => a.localeCompare(b, 'pt-BR'));
  const subjects = distinct([
    ...topics,
    ...(page?.items.flatMap((norm) => norm.subjects) || []),
  ]);
  const clear = (form: HTMLFormElement | null) => {
    if (search) window.location.hash = '#normas';
    else form?.reset();
  };

  return (
    <div className="stack space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">
          Biblioteca de normas
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          Consulte leis e normas fiscais por assunto, órgão ou período de
          vigência.
        </p>
      </header>
      <form key={search} onSubmit={submit} className="panel space-y-4 p-5">
        <label className="block text-sm font-semibold text-slate-800">
          Buscar por título, número, artigo ou palavra-chave
          <span className="relative mt-1.5 block">
            <Search
              size={17}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
              aria-hidden
            />
            <input
              name="q"
              type="search"
              maxLength={256}
              defaultValue={params.get('q') || ''}
              placeholder="Ex.: MEI, art. 18-A, declaração anual"
              className="field w-full !pl-10"
            />
          </span>
        </label>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {(
            [
              ['subject', 'Assunto', subjects, 'Todos os assuntos'],
              [
                'norm_type',
                'Tipo de norma',
                distinct(page?.items.map((n) => n.norm_type) || []),
                'Todos os tipos',
              ],
              [
                'authority',
                'Órgão',
                distinct(page?.items.map((n) => n.authority) || []),
                'Todos os órgãos',
              ],
            ] as const
          ).map(([name, label, options, placeholder]) => (
            <label
              key={name}
              className="block text-sm font-medium text-slate-700"
            >
              {label}
              <input
                name={name}
                list={`opcoes-${name}`}
                placeholder={placeholder}
                defaultValue={params.get(name) || ''}
                className="field mt-1.5 w-full"
              />
              <datalist id={`opcoes-${name}`}>
                {options.map((option) => (
                  <option key={option} value={option} />
                ))}
              </datalist>
            </label>
          ))}
          <label className="block text-sm font-medium text-slate-700">
            Vigente em
            <input
              name="effective_on"
              type="date"
              defaultValue={params.get('effective_on') || ''}
              className="field mt-1.5 w-full"
            />
          </label>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" className="primary">
            Buscar normas
          </button>
          <button
            className="secondary"
            type="button"
            onClick={(event) => clear(event.currentTarget.form)}
          >
            Limpar filtros
          </button>
        </div>
      </form>
      <section
        className="panel overflow-hidden"
        aria-labelledby="norm-results"
        aria-busy={!page && !error}
      >
        <div className="flex items-center gap-2 border-b border-slate-200 px-5 py-4">
          <BookOpen size={19} className="text-emerald-700" aria-hidden />
          <h2
            id="norm-results"
            className="text-lg font-semibold text-slate-900"
          >
            Normas encontradas
          </h2>
        </div>
        {!page && !error && (
          <p role="status" className="p-5 text-sm text-slate-600">
            Carregando normas…
          </p>
        )}
        {error && (
          <div role="alert" className="space-y-3 p-5">
            <p>A biblioteca está indisponível no momento.</p>
            <button
              className="secondary"
              onClick={() => {
                setResult(null);
                setAttempt((n) => n + 1);
              }}
            >
              Tentar novamente
            </button>
          </div>
        )}
        {page && !page.items.length && (
          <p role="status" className="p-5 text-sm text-slate-600">
            Nenhuma norma encontrada
            {search
              ? '. Limpe ou ajuste os filtros para refazer a busca.'
              : ' na biblioteca.'}
          </p>
        )}
        {page && (
          <ul className="divide-y divide-slate-100">
            {page.items.map((norm) => (
              <li key={norm.version_id}>
                <a
                  href={openDocument(norm)}
                  className="group flex items-start gap-3 px-5 py-4 transition hover:bg-emerald-50/50 focus-visible:outline-emerald-700"
                >
                  <FileText
                    size={20}
                    className="mt-1 shrink-0 text-emerald-700"
                    aria-hidden
                  />
                  <div className="min-w-0 flex-1">
                    <h3 className="break-words font-semibold text-slate-900 group-hover:text-emerald-800">
                      {norm.title}
                    </h3>
                    <p className="mt-1 text-sm text-slate-600">
                      {[norm.norm_type, norm.authority, norm.version_label]
                        .filter(Boolean)
                        .join(' · ')}
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      Vigência ·{' '}
                      {validity(norm.effective_from, norm.effective_to)}
                    </p>
                    {norm.subjects.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {norm.subjects.map((subject) => (
                          <span
                            key={subject}
                            className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700"
                          >
                            {subject}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <ChevronRight
                    size={18}
                    className="mt-1 shrink-0 text-slate-500"
                    aria-hidden
                  />
                </a>
              </li>
            ))}
          </ul>
        )}
        {(params.has('cursor') || page?.next_cursor) && (
          <nav
            aria-label="Paginação de normas"
            className="flex flex-wrap items-center justify-between gap-4 border-t border-slate-200 px-5 py-3 text-sm font-semibold text-emerald-800"
          >
            {params.has('cursor') && <a href={pageLink()}>Primeira página</a>}
            {page?.next_cursor && (
              <a
                className="ml-auto inline-flex items-center gap-2"
                href={pageLink(page.next_cursor)}
              >
                Próxima página <ArrowRight size={15} aria-hidden />
              </a>
            )}
          </nav>
        )}
      </section>
    </div>
  );
}
