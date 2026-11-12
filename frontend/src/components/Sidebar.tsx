import React from 'react';
import { LayoutDashboard, MessageSquareText, Building2, CheckSquare, ShieldCheck, LogOut } from 'lucide-react';
import { Empresa } from '../types';

interface SidebarProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
  empresaAtiva: Empresa | null;
  onLogout: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  empresaAtiva,
  onLogout,
}) => {
  const navItems = [
    { id: 'dashboard', label: 'Visão Geral', icon: LayoutDashboard },
    { id: 'assistente', label: 'Copiloto Fiscal', icon: MessageSquareText },
    { id: 'tarefas', label: 'Obrigações & Tarefas', icon: CheckSquare },
    { id: 'empresas', label: 'Empresas', icon: Building2 },
    { id: 'normas', label: 'Biblioteca de Normas', icon: ShieldCheck },
  ];

  return (
    <aside className="w-full md:w-64 bg-slate-900 text-slate-300 flex flex-col justify-between shrink-0 border-r border-slate-800 h-screen sticky top-0">
      <div>
        {/* Marca & Identidade */}
        <div className="h-16 flex items-center px-6 border-b border-slate-800/80 gap-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-500 text-slate-950 font-black flex items-center justify-center text-base shadow-sm">
            S
          </div>
          <div>
            <span className="text-sm font-bold text-white tracking-tight">Sócio Digital</span>
            <span className="block text-[10px] font-medium text-slate-400">Copiloto Fiscal & MEI</span>
          </div>
        </div>

        {/* Seletor de Empresa Ativa */}
        <div className="p-4 mx-3 my-3 rounded-xl bg-slate-800/60 border border-slate-700/60 space-y-1">
          <div className="flex items-center justify-between text-[11px] text-slate-400">
            <span>Empresa Ativa</span>
            <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-[10px] font-medium border border-emerald-500/30">
              {empresaAtiva?.porte || 'ME'}
            </span>
          </div>
          <div className="text-xs font-bold text-white truncate">
            {empresaAtiva?.razao_social || 'TecnoSoft Tecnologia Ltda'}
          </div>
          <div className="text-[11px] font-mono text-slate-400">
            {empresaAtiva?.cnpj || '45.123.890/0001-44'}
          </div>
        </div>

        {/* Menu de Navegação */}
        <nav className="px-3 space-y-1 text-xs font-medium">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left ${
                  active
                    ? 'bg-emerald-500/10 text-emerald-400 font-semibold border border-emerald-500/20 shadow-sm'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/50 border border-transparent'
                }`}
              >
                <Icon className={`w-4 h-4 ${active ? 'text-emerald-400' : 'text-slate-400'}`} />
                {item.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Rodapé do Menu */}
      <div className="p-4 border-t border-slate-800/80">
        <button
          onClick={onLogout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-800/50 transition-all text-xs"
        >
          <LogOut className="w-4 h-4" />
          Encerrar Sessão
        </button>
      </div>
    </aside>
  );
};
