import { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { Dashboard } from './pages/Dashboard';
import { Assistente } from './pages/Assistente';
import { Empresas } from './pages/Empresas';
import { Login } from './pages/Login';
import { Empresa, UserAccount } from './types';

export function App() {
  const [autenticado, setAutenticado] = useState(true); // default true para protótipo/desenvolvimento
  const [currentTab, setCurrentTab] = useState('dashboard');
  const [usuario] = useState<UserAccount>({
    id: 'user-demo',
    nome: 'Carlos Empreendedor',
    email: 'carlos@tecnosoft.com.br',
    created_at: '2026-01-01',
  });
  const [empresaAtiva, setEmpresaAtiva] = useState<Empresa>({
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
  });

  if (!autenticado) {
    return (
      <Login
        onLoginSuccess={() => {
          setAutenticado(true);
        }}
      />
    );
  }

  const getTituloPagina = () => {
    switch (currentTab) {
      case 'dashboard':
        return 'Visão Geral & Tributos';
      case 'assistente':
        return 'Copiloto Fiscal Tributário';
      case 'empresas':
        return 'Gestão de Empresas & CNPJs';
      case 'tarefas':
        return 'Obrigações & Prazos Fiscais';
      case 'normas':
        return 'Biblioteca de Legislação & Manuais';
      default:
        return 'Sócio Digital';
    }
  };

  return (
    <div className="flex h-screen bg-[#f8fafc] overflow-hidden">
      <Sidebar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        empresaAtiva={empresaAtiva}
        onLogout={() => setAutenticado(false)}
      />

      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Header usuario={usuario} titulo={getTituloPagina()} />

        <main className="flex-1">
          {currentTab === 'dashboard' && (
            <Dashboard
              empresa={empresaAtiva}
              onNavigateToAssistente={() => setCurrentTab('assistente')}
            />
          )}

          {currentTab === 'assistente' && <Assistente empresa={empresaAtiva} />}

          {currentTab === 'empresas' && (
            <Empresas
              empresaAtiva={empresaAtiva}
              onSelecionarEmpresa={(emp) => setEmpresaAtiva(emp)}
            />
          )}

          {currentTab === 'tarefas' && (
            <div className="p-8 text-center text-slate-500 text-xs">
              Módulo de Tarefas & Obrigações Fiscais em execução com o backend.
            </div>
          )}

          {currentTab === 'normas' && (
            <div className="p-8 text-center text-slate-500 text-xs">
              Módulo de Biblioteca de Normas (LC 123/2006, CGSN 140/2018).
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
