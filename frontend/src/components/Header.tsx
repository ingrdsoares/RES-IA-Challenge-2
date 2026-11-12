import React from 'react';
import { Bell, ShieldCheck } from 'lucide-react';
import { UserAccount } from '../types';

interface HeaderProps {
  usuario: UserAccount | null;
  titulo: string;
}

export const Header: React.FC<HeaderProps> = ({ usuario, titulo }) => {
  return (
    <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between shrink-0">
      <div className="flex items-center gap-3">
        <h1 className="text-base font-bold text-slate-800">{titulo}</h1>
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
          Conformidade Ativa
        </span>
      </div>

      <div className="flex items-center gap-4">
        <button className="relative p-2 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors">
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-emerald-500"></span>
        </button>

        <div className="h-4 w-px bg-slate-200"></div>

        <div className="flex items-center gap-2.5 text-xs">
          <div className="w-7 h-7 rounded-full bg-slate-800 text-white flex items-center justify-center font-bold text-[11px]">
            {usuario?.nome ? usuario.nome.slice(0, 2).toUpperCase() : 'SD'}
          </div>
          <div>
            <div className="font-semibold text-slate-800 leading-tight">
              {usuario?.nome || 'Empreendedor'}
            </div>
            <div className="text-[10px] text-slate-400 font-mono">
              {usuario?.email || 'admin@sociodigital.com.br'}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
