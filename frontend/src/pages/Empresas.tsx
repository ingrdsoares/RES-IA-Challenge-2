import React, { useState } from 'react';
import { Plus, Check } from 'lucide-react';
import { Empresa } from '../types';

interface EmpresasProps {
  empresaAtiva: Empresa | null;
  onSelecionarEmpresa: (empresa: Empresa) => void;
}

export const Empresas: React.FC<EmpresasProps> = ({ empresaAtiva, onSelecionarEmpresa }) => {
  const [empresas] = useState<Empresa[]>([
    {
      id: 'emp-1',
      cnpj: '45.123.890/0001-44',
      razao_social: 'TecnoSoft Tecnologia Ltda',
      porte: 'ME',
      cnae_principal: '6201-5/01 - Desenvolvimento de programas de computador',
      municipio: 'Brasília',
      uf: 'DF',
      regime: 'SIMPLES_NACIONAL',
      faturamento_anual: 300000,
      folha_anual: 90000,
      created_at: '2026-01-15',
    },
    {
      id: 'emp-2',
      cnpj: '12.345.678/0001-99',
      razao_social: 'Studio Beleza & Estética MEI',
      porte: 'MEI',
      cnae_principal: '9602-5/01 - Cabeleireiros, manicure e pedicure',
      municipio: 'Brasília',
      uf: 'DF',
      regime: 'SIMEI',
      faturamento_anual: 60000,
      created_at: '2026-02-10',
    },
  ]);

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-900">Minhas Empresas</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Gerencie os negócios vinculados à sua conta com total isolamento multi-tenant.
          </p>
        </div>
        <button className="flex items-center gap-2 px-3 py-2 bg-emerald-500 hover:bg-emerald-600 text-slate-950 font-bold rounded-lg text-xs transition-colors shadow-sm">
          <Plus className="w-4 h-4" />
          Adicionar Empresa
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {empresas.map((emp) => {
          const selecionada = empresaAtiva?.id === emp.id;
          return (
            <div
              key={emp.id}
              className={`p-5 rounded-xl border bg-white shadow-sm transition-all flex flex-col justify-between ${
                selecionada ? 'border-emerald-500 ring-1 ring-emerald-500/20' : 'border-slate-200'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] font-mono text-slate-400">{emp.cnpj}</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                    {emp.porte}
                  </span>
                </div>
                <h3 className="text-sm font-bold text-slate-900">{emp.razao_social}</h3>
                <p className="text-xs text-slate-500 mt-1 line-clamp-1">{emp.cnae_principal}</p>
                <div className="mt-3 text-xs text-slate-600 flex items-center gap-4">
                  <span>Regime: <strong>{emp.regime}</strong></span>
                  <span>Local: <strong>{emp.municipio}/{emp.uf}</strong></span>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                <span className="text-[11px] text-slate-400">
                  {selecionada ? 'Empresa atualmente ativa' : 'Clique para alternar'}
                </span>
                <button
                  onClick={() => onSelecionarEmpresa(emp)}
                  disabled={selecionada}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors ${
                    selecionada
                      ? 'bg-emerald-50 text-emerald-700 cursor-default'
                      : 'bg-slate-100 hover:bg-slate-200 text-slate-800'
                  }`}
                >
                  {selecionada ? (
                    <>
                      <Check className="w-3.5 h-3.5" /> Ativa
                    </>
                  ) : (
                    'Selecionar'
                  )}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
