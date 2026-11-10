import React from 'react';
import { TrendingUp, AlertTriangle, FileText, CheckCircle2 } from 'lucide-react';
import { Empresa } from '../types';

interface DashboardProps {
  empresa: Empresa | null;
  onNavigateToAssistente: () => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ empresa, onNavigateToAssistente }) => {
  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Alerta de Status Fiscal / Semáforo */}
      <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 flex items-start justify-between">
        <div className="flex gap-3">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
          <div>
            <h3 className="text-sm font-semibold text-emerald-900">
              Situação Fiscal Regular — Simples Nacional
            </h3>
            <p className="text-xs text-emerald-700 mt-0.5">
              Nenhuma pendência impeditiva no e-CAC ou Dívida Ativa da União para o CNPJ{' '}
              <span className="font-mono">{empresa?.cnpj || '45.123.890/0001-44'}</span>.
            </p>
          </div>
        </div>
        <button
          onClick={onNavigateToAssistente}
          className="text-xs font-semibold text-emerald-800 hover:text-emerald-950 bg-emerald-100 hover:bg-emerald-200 px-3 py-1.5 rounded-lg transition-colors shrink-0"
        >
          Consultar Copiloto
        </button>
      </div>

      {/* Cards de Métricas Principais */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="text-xs font-medium text-slate-500">Regime Vigente</div>
          <div className="text-lg font-bold text-slate-900 mt-1">Anexo III (Simples)</div>
          <div className="text-[11px] text-emerald-600 mt-1 flex items-center gap-1">
            <TrendingUp className="w-3.5 h-3.5" /> Fator R = 30.0% (Beneficiado)
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="text-xs font-medium text-slate-500">Alíquota Efetiva Atual</div>
          <div className="text-lg font-bold text-slate-900 mt-1">8,08%</div>
          <div className="text-[11px] text-slate-500 mt-1">
            Economia de R$ 2.105/mês vs. Anexo V
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="text-xs font-medium text-slate-500">Próxima Guia DAS</div>
          <div className="text-lg font-bold text-slate-900 mt-1">R$ 2.020,00</div>
          <div className="text-[11px] text-slate-500 mt-1">
            Vencimento: 20 do próximo mês
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
          <div className="text-xs font-medium text-slate-500">Faturamento Acumulado 12m</div>
          <div className="text-lg font-bold text-slate-900 mt-1">R$ 300.000,00</div>
          <div className="text-[11px] text-slate-500 mt-1">
            Folha de Pagamento 12m: R$ 90.000,00
          </div>
        </div>
      </div>

      {/* Próximas Obrigações & Prazos */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3 mb-4">
            <h4 className="text-sm font-bold text-slate-900">Agenda Fiscal & Obrigações</h4>
            <span className="text-xs text-slate-400">Competência Corrente</span>
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 rounded-lg bg-slate-50 border border-slate-200/60">
              <div className="flex items-center gap-3">
                <FileText className="w-4 h-4 text-slate-500" />
                <div>
                  <div className="text-xs font-semibold text-slate-800">Guia DAS Simples Nacional</div>
                  <div className="text-[11px] text-slate-500">Apuração mensal PGDAS-D</div>
                </div>
              </div>
              <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-100 text-emerald-800">
                Em dia
              </span>
            </div>

            <div className="flex items-center justify-between p-3 rounded-lg bg-slate-50 border border-slate-200/60">
              <div className="flex items-center gap-3">
                <FileText className="w-4 h-4 text-slate-500" />
                <div>
                  <div className="text-xs font-semibold text-slate-800">Declaração DEFIS Anual</div>
                  <div className="text-[11px] text-slate-500">Prestação de informações socioeconômicas</div>
                </div>
              </div>
              <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-700">
                Prazo: 31/Mar
              </span>
            </div>
          </div>
        </div>

        {/* Alerta de Fronteira Ética & CRC */}
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 text-amber-600 mb-2">
              <AlertTriangle className="w-4 h-4" />
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                Aviso Regulatório & Fronteira Ética (CRC)
              </h4>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              O <strong>Sócio Digital</strong> atua exclusivamente no letramento, simulação determinística e organização das obrigações do seu negócio. As simulações não substituem a escrituração contábil formal nem a apuração oficial privativa de profissionais registrados no CRC (Decreto-Lei nº 9.295/1946).
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-200/80 text-[11px] text-slate-500 flex justify-between items-center">
            <span>Base normativa: LC 123/2006 & CGSN 140</span>
            <span className="font-semibold text-slate-700">Auditado por RAG Factual</span>
          </div>
        </div>
      </div>
    </div>
  );
};
