import { useState } from 'react';
import {
  LayoutDashboard,
  MessagesSquare,
  Landmark,
  ListChecks,
  BookOpen,
  Building2,
  LogOut,
  Menu,
  X,
  Plus,
} from 'lucide-react';
import { Brand } from './Header';
import type { Company } from '../types';

const links = [
  ['assistente', 'Assistente fiscal', MessagesSquare],
  ['dashboard', 'Visão geral', LayoutDashboard],
  ['fiscal', 'Situação fiscal', Landmark],
  ['tarefas', 'Tarefas', ListChecks],
  ['normas', 'Biblioteca de normas', BookOpen],
  ['perfil', 'Perfil da empresa', Building2],
] as const;
export const titles: Record<string, string> = {
  ...Object.fromEntries(links.map(([id, label]) => [id, label])),
  cadastro: 'Cadastro da empresa',
  leitor: 'Leitor da norma',
};
export function formatCnpj(id: string) {
  return id.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5');
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
            <select
              id="company"
              value={company.id}
              onChange={(e) => {
                onSelect(e.target.value);
                setOpen(false);
              }}
            >
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {formatCnpj(c.cnpj)}
                </option>
              ))}
            </select>
          ) : (
            <strong>Primeiro cadastro</strong>
          )}
          <a href="#cadastro" onClick={() => setOpen(false)}>
            <Plus size={14} /> Cadastrar empresa
          </a>
        </div>
        <nav aria-label="Navegação principal">
          {company &&
            links.map(([key, label, Icon]) => (
              <a
                key={key}
                href={'#' + key}
                aria-current={
                  key === page || (key === 'normas' && page === 'leitor')
                    ? 'page'
                    : undefined
                }
                onClick={() => setOpen(false)}
              >
                <Icon size={18} />
                {label}
              </a>
            ))}
        </nav>
        <button className="logout" onClick={onLogout}>
          <LogOut size={17} /> Sair da conta
        </button>
      </div>
    </aside>
  );
}
