import { Landing } from './pages/Landing';
import { useEffect, useState } from 'react';
import { Header, Brand } from './components/Header';
import { Sidebar, titles } from './components/Sidebar';
import { Dashboard } from './pages/Dashboard';
import { Assistente } from './pages/Assistente';
import { Fiscal } from './pages/Fiscal';
import { Tarefas } from './pages/Tarefas';
import { Biblioteca } from './pages/Biblioteca';
import { Leitor } from './pages/Leitor';
import { Obrigacoes } from './pages/Obrigacoes';
import { Ajuda } from './pages/Ajuda';
import { Empresas } from './pages/Empresas';
import { clearChatDrafts } from './services/chatDrafts';
import { RecuperarSenha } from './pages/RecuperarSenha';
import { Login } from './pages/Login';
import { api, ApiError } from './services/api';
import type { Account, Company } from './types';

function Workspace({ user, onEnd }: { user: Account; onEnd: () => void }) {
  const [companies, setCompanies] = useState<Company[] | null>(null);
  const [request, setRequest] = useState(0),
    [error, setError] = useState('');
  const [id, setId] = useState(
    () => sessionStorage.getItem('company:' + user.id) || '',
  );
  const [hash, setHash] = useState(location.hash);
  useEffect(() => {
    const sync = () => setHash(location.hash);
    window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    api
      .getEmpresas(controller.signal)
      .then((rows) => {
        if (!controller.signal.aborted) setCompanies(rows);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, [request]);
  const company = companies?.find((c) => c.id === id) || companies?.[0];
  const [route, search = ''] = hash.slice(1).split('?');
  const page =
    company && Object.prototype.hasOwnProperty.call(titles, route)
      ? route
      : company
        ? 'assistente'
        : 'cadastro';
  const params = new URLSearchParams(search);
  useEffect(() => {
    document.title = titles[page] + ' | Sócio Digital';
  }, [page]);
  function select(value: string) {
    sessionStorage.setItem('company:' + user.id, value);
    setId(value);
    location.hash = 'assistente';
  }
  function saved(updated: Company) {
    setCompanies((old) =>
      old?.some((c) => c.id === updated.id)
        ? old.map((c) => (c.id === updated.id ? updated : c))
        : [...(old || []), updated],
    );
    if (page === 'cadastro') select(updated.id);
  }
  async function logout() {
    try {
      await api.logout();
      onEnd();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) onEnd();
      else setError('Não foi possível encerrar a sessão. Tente novamente.');
    }
  }
  if (!companies)
    return (
      <main className="boot">
        <Brand />
        {error ? (
          <>
            <p role="alert">{error}</p>
            <button
              className="primary"
              onClick={() => {
                setError('');
                setRequest((v) => v + 1);
              }}
            >
              Tentar novamente
            </button>
            <button onClick={logout}>Sair</button>
          </>
        ) : (
          <p role="status">Abrindo o painel da empresa…</p>
        )}
      </main>
    );
  const props = company ? { company, params } : null;
  return (
    <div className="workspace">
      <Sidebar
        page={page}
        companies={companies}
        company={company}
        onSelect={select}
        onLogout={logout}
      />
      <div className="workspace-body">
        <Header title={titles[page]} email={user.email} />
        <main className="page-body" key={company?.id}>
          {error && (
            <p className="notice" role="alert">
              {error}
            </p>
          )}
          {page === 'cadastro' && (
            <Empresas
              key="novo"
              onSave={saved}
              onCancel={
                company
                  ? () => {
                      location.hash = 'assistente';
                    }
                  : undefined
              }
            />
          )}
          {page === 'perfil' && company && (
            <Empresas
              key={company.id}
              company={company}
              onSave={saved}
              onCancel={() => {
                location.hash = 'assistente';
              }}
            />
          )}
          {page === 'dashboard' && props && <Dashboard {...props} />}
          {page === 'fiscal' && props && <Fiscal {...props} />}
          {page === 'tarefas' && props && <Tarefas {...props} />}
          {page === 'obrigacoes' && props && <Obrigacoes {...props} />}
          {page === 'ajuda' && <Ajuda />}
          {page === 'assistente' && company && (
            <Assistente accountId={user.id} company={company} params={params} />
          )}
          {page === 'normas' && <Biblioteca params={params} />}
          {page === 'leitor' && <Leitor params={params} />}
        </main>
      </div>
    </div>
  );
}
function protectedRoute(hash: string | null) {
  if (!hash?.startsWith('#')) return '';
  return Object.prototype.hasOwnProperty.call(titles, hash.slice(1).split('?')[0]) ? hash : '';
}

export function App() {
  const [publicRoute, setPublicRoute] = useState(location.hash);
  useEffect(() => {
    const navigate = () => setPublicRoute(location.hash);
    window.addEventListener('hashchange', navigate);
    return () => window.removeEventListener('hashchange', navigate);
  }, []);
  const isLanding = ['', '#inicio', '#recursos', '#duvidas'].includes(
    publicRoute,
  );
  useEffect(() => {
    if (isLanding) {
      document.title = 'Sócio Digital | Sua rotina fiscal, em ordem';
      requestAnimationFrame(() =>
        document
          .getElementById(publicRoute.slice(1) || 'inicio')
          ?.scrollIntoView(),
      );
    }
  }, [isLanding, publicRoute]);
  const [account, setAccount] = useState<Account | null | undefined>(undefined),
    [notice, setNotice] = useState('');
  useEffect(() => {
    let live = true;
    api
      .getMe()
      .then((a) => {
        if (live) setAccount(a);
      })
      .catch((e) => {
        if (live) {
          if (e instanceof ApiError && e.status === 401) clearChatDrafts();
          setAccount(null);
          if (!(e instanceof ApiError && e.status === 401))
            setNotice(
              'Serviço de acesso indisponível. Tente entrar novamente.',
            );
        }
      });
    const end = () => {
      const destination = protectedRoute(location.hash);
      clearChatDrafts();
      setAccount(null);
      if (!destination) return;
      setNotice('Sua sessão expirou. Entre novamente.');
      location.replace('#entrar?' + new URLSearchParams({ destino: destination }));
    };
    window.addEventListener('session-expired', end);
    return () => {
      live = false;
      window.removeEventListener('session-expired', end);
    };
  }, []);
  const [action, query = ''] = publicRoute.slice(1).split('?');
  const params = new URLSearchParams(query);
  const destination = protectedRoute(publicRoute) || protectedRoute(params.get('destino'));
  if (action === 'recuperar-senha' || action === 'redefinir-senha') {
    return <RecuperarSenha key={publicRoute} token={action === 'redefinir-senha' ? params.get('token') || '' : undefined} />;
  }
  if (isLanding) return <Landing signedIn={!!account} />;
  if (account === undefined)
    return (
      <main className="boot">
        <Brand />
        <p role="status">Verificando sessão…</p>
      </main>
    );
  return account ? (
    <Workspace
      key={account.id}
      user={account}
      onEnd={() => {
        clearChatDrafts();
        setAccount(null);
        setNotice('');
        location.hash = '';
      }}
    />
  ) : (
    <Login
      key={publicRoute}
      register={action === 'criar-conta'}
      destination={destination}
      notice={notice}
      onLoginSuccess={(a) => {
        setNotice('');
        location.replace(destination || '#assistente');
        setAccount(a);
      }}
    />
  );
}
export default App;
