import { useEffect, useState } from 'react';
import {
  LayoutDashboard,
  MessagesSquare,
  Landmark,
  ListChecks,
  BookOpen,
  Building2,
  CircleHelp,
  LogOut,
  Menu,
  X,
  Plus,
  SquarePen,
  TrendingUp,
} from 'lucide-react';
import { Brand } from './Header';
import { api } from '../services/api';
import type { Company } from '../types';
import { readList } from '../pages/fiscal-data';

type NavItem = readonly [key: string, label: string, icon: typeof MessagesSquare];
const groups: readonly (readonly [string, readonly NavItem[]])[] = [
  ['Atendimento', [['assistente', 'Assistente fiscal', MessagesSquare]]],
  [
    'Empresa',
    [
      ['dashboard', 'Visão geral', LayoutDashboard],
      ['faturamento', 'Faturamento', TrendingUp],
      ['fiscal', 'Situação fiscal', Landmark],
      ['tarefas', 'Tarefas e obrigações', ListChecks],
      ['perfil', 'Perfil da empresa', Building2],
    ],
  ],
  [
    'Consulta',
    [
      ['normas', 'Biblioteca de normas', BookOpen],
      ['ajuda', 'Ajuda', CircleHelp],
    ],
  ],
];
const links = groups.flatMap(([, items]) => items);
export const titles: Record<string, string> = {
  ...Object.fromEntries(links.map(([id, label]) => [id, label])),
  cadastro: 'Cadastro da empresa',
  leitor: 'Leitor da norma',
};
export function formatCnpj(id: string) {
  return id.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5');
}

type Conversation = { id: string; title: string };
type Summary = { recent: Conversation[]; pending: number | null; online: boolean | null };

// Live context for the side panel; refreshed when the company or the page changes.
function useSummary(companyId: string | undefined, page: string) {
  const [summary, setSummary] = useState<Summary>({ recent: [], pending: null, online: null });
  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    const update = (part: Partial<Summary>) => {
      if (!signal.aborted) setSummary((current) => ({ ...current, ...part }));
    };
    api.request('/ready', { signal }).then(
      () => update({ online: true }),
      () => update({ online: false }),
    );
    if (companyId) {
      // The API lists oldest first; the panel shows the three most recent.
      readList<Conversation>('/empresas/' + companyId + '/conversas', signal).then(
        (rows) => update({ recent: rows.slice(-3).reverse() }),
        () => update({ recent: [] }),
      );
      Promise.all([
        readList('/empresas/' + companyId + '/tarefas?completed=false', signal),
        readList<{ completed: boolean }>('/empresas/' + companyId + '/obrigacoes', signal),
      ]).then(
        ([tasks, obligations]) =>
          update({ pending: tasks.length + obligations.filter((item) => !item.completed).length }),
        () => update({ pending: null }),
      );
    }
    return () => controller.abort();
  }, [companyId, page]);
  return summary;
}

export function Sidebar({
  page,
  companies,
  company,
  onSelect,
  onLogout,
}: {
  page: string;
  companies: Company[];
  company?: Company;
  onSelect: (id: string) => void;
  onLogout: () => void;
}) {
  const [open, setOpen] = useState(false);
  const { recent, pending, online } = useSummary(company?.id, page);
  const close = () => setOpen(false);
  return (
    <aside className={'sidebar ' + (open ? 'is-open' : '')}>
      <div className="side-head">
        <Brand />
        <button
          aria-label="Menu de navegação"
          aria-expanded={open}
          className="mobile-menu"
          onClick={() => setOpen(!open)}
        >
          {open ? <X /> : <Menu />}
        </button>
      </div>
      <div className="side-content">
        <div className="company-picker">
          <label htmlFor="company">Empresa ativa</label>
          {company ? (
            <>
              <select
                id="company"
                value={company.id}
                onChange={(e) => {
                  onSelect(e.target.value);
                  close();
                }}
              >
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {formatCnpj(c.cnpj)}
                  </option>
                ))}
              </select>
              <span className="company-meta">
                {company.regime} · {company.municipality}/{company.state}
              </span>
            </>
          ) : (
            <strong>Primeiro cadastro</strong>
          )}
          <a href="#cadastro" onClick={close}>
            <Plus size={14} aria-hidden /> Cadastrar empresa
          </a>
        </div>
        <nav aria-label="Navegação principal">
          {company && (
            <>
              <a className="nav-new" href="#assistente" onClick={close}>
                <SquarePen size={17} aria-hidden /> Nova pergunta
              </a>
              {groups.map(([group, items]) => (
                <div key={group} className="nav-group">
                  <p className="nav-group-title" aria-hidden>
                    {group}
                  </p>
                  {items.map(([key, label, Icon]) => (
                    <div key={key}>
                      <a
                        href={'#' + key}
                        aria-current={
                          key === page || (key === 'normas' && page === 'leitor')
                            ? 'page'
                            : undefined
                        }
                        onClick={close}
                      >
                        <Icon size={18} aria-hidden />
                        <span className="flex-1">{label}</span>
                        {key === 'tarefas' && !!pending && (
                          <>
                            <span className="nav-badge" aria-hidden>
                              {pending > 99 ? '99+' : pending}
                            </span>
                            <span className="sr-only">
                              {' · ' + pending + (pending === 1 ? ' pendente' : ' pendentes')}
                            </span>
                          </>
                        )}
                      </a>
                      {key === 'assistente' && recent.length > 0 && (
                        <ul className="nav-recent" aria-label="Conversas recentes">
                          {recent.map((chat) => (
                            <li key={chat.id}>
                              <a href={'#assistente?conversa=' + chat.id} title={chat.title} onClick={close}>
                                {chat.title}
                              </a>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              ))}
            </>
          )}
        </nav>
        <div className="side-foot">
          {online !== null && (
            <p
              role="status"
              aria-label="Status do serviço"
              className={'service-status ' + (online ? 'is-online' : 'is-offline')}
            >
              <span className="service-dot" aria-hidden />
              {online ? 'Serviço disponível' : 'Serviço instável'}
            </p>
          )}
          <button className="logout" onClick={onLogout}>
            <LogOut size={17} aria-hidden /> Sair da conta
          </button>
        </div>
      </div>
    </aside>
  );
}
