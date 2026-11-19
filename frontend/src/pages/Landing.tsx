import { useState } from 'react';
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Building2,
  Check,
  ChevronDown,
  Circle,
  FileCheck2,
  FileText,
  FolderOpen,
  LayoutDashboard,
  ListChecks,
  MessageSquareText,
  Paperclip,
} from 'lucide-react';
import { Brand } from '../components/Header';
import './landing.css';

const views = [
  { name: 'Painel', icon: LayoutDashboard },
  { name: 'Tarefas', icon: ListChecks },
  { name: 'Fontes', icon: BookOpen },
] as const;

function Preview() {
  const [view, setView] = useState(0);
  const [done, setDone] = useState(false);
  return (
    <section className="lp-preview" aria-label="Demonstração da plataforma">
      <div className="lp-preview-label">
        <span className="lp-dot" /> Prévia interativa · Dados ilustrativos
      </div>
      <div className="lp-folder">
        <div className="lp-tab" aria-hidden="true">
          <FolderOpen size={17} /> Pasta fiscal
        </div>
        <div className="lp-paper">
          <div className="lp-paper-meta">
            <span>Empresa de exemplo</span>
            <Building2 size={16} />
          </div>
          <h2>
            {['Visão geral', 'Tarefas da empresa', 'Fontes da consulta'][view]}
          </h2>
          <div className="lp-paper-content">
            {view === 0 && (
              <>
                <div className="lp-record">
                  <span className="lp-record-icon">
                    <FileCheck2 />
                  </span>
                  <div>
                    <strong>Cadastro da empresa</strong>
                    <small>Origem dos dados</small>
                  </div>
                  <span className="lp-status">Declarado</span>
                </div>
                <div className="lp-record">
                  <span className="lp-record-icon">
                    <ListChecks />
                  </span>
                  <div>
                    <strong>Conferir guia do mês</strong>
                    <small>Próxima tarefa</small>
                  </div>
                  <span className={'lp-status ' + (!done ? 'pending' : '')}>
                    {done ? 'Concluída' : 'Pendente'}
                  </span>
                </div>
              </>
            )}
            {view === 1 && (
              <>
                <p>Conferir guia do mês</p>
                <small>
                  Compare os dados da guia com a competência registrada.
                </small>
                <button
                  className="lp-demo-action"
                  onClick={() => setDone(!done)}
                >
                  {done ? <Check size={17} /> : <Circle size={17} />}{' '}
                  {done ? 'Reabrir tarefa' : 'Marcar como concluída'}
                </button>
              </>
            )}
            {view === 2 && (
              <>
                <p>
                  <BookOpen size={18} /> Lei Complementar nº 123/2006
                </p>
                <small>
                  Uma citação do assistente identifica a norma e a versão
                  consultada.
                </small>
                <a
                  className="lp-demo-action"
                  href="https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp123.htm"
                  target="_blank"
                  rel="noreferrer"
                >
                  Ver publicação oficial <ArrowUpRight size={16} />
                </a>
              </>
            )}
          </div>
          <div className="lp-binding" aria-hidden="true" />
        </div>
      </div>
      <div
        className="lp-switch"
        role="group"
        aria-label="Escolha a tela da prévia"
      >
        {views.map(({ name, icon: Icon }, i) => (
          <button
            key={name}
            aria-pressed={view === i}
            onClick={() => setView(i)}
          >
            <Icon size={15} />
            {name}
          </button>
        ))}
      </div>
    </section>
  );
}

const features = [
  {
    icon: MessageSquareText,
    name: 'Assistente fiscal',
    text: 'Pergunte no contexto da sua empresa. Quando houver base para a resposta, abra a norma citada e confira o trecho.',
  },
  {
    icon: Paperclip,
    name: 'Situação fiscal',
    text: 'Reúna guias, declarações e comprovantes. Veja a origem e a validade das evidências de cada obrigação.',
  },
  {
    icon: ListChecks,
    name: 'Tarefas e prazos',
    text: 'Transforme orientações em tarefas, registre a conclusão e acompanhe o que falta fazer.',
  },
];
const questions = [
  [
    'Para quem é o Sócio Digital?',
    'Para MEIs e pequenos negócios que querem organizar documentos, acompanhar obrigações e entender melhor suas dúvidas fiscais.',
  ],
  [
    'O que preciso para começar?',
    'Crie uma conta com e-mail e senha. Depois, informe CNPJ, CNAE, porte, regime tributário e município para abrir o painel da empresa.',
  ],
  [
    'A plataforma confirma que uma guia foi paga?',
    'O painel mostra as evidências registradas e a origem dos dados. Anexar uma guia ou concluir uma tarefa não confirma pagamento.',
  ],
  [
    'O assistente substitui meu contador?',
    'O assistente ajuda a entender normas e a organizar os próximos passos. Decisões tributárias e escrituração devem ser validadas com o profissional contábil responsável.',
  ],
];

export function Landing({ signedIn }: { signedIn: boolean }) {
  const action = signedIn ? '#dashboard' : '#criar-conta';
  return (
    <div className="lp" id="inicio">
      <header className="lp-header">
        <div className="lp-wrap lp-nav">
          <Brand />
          <nav aria-label="Sobre o Sócio Digital">
            <a href="#recursos">Recursos</a>
            <a href="#duvidas">Dúvidas</a>
          </nav>
          <div className="lp-nav-actions">
            {!signedIn && <a href="#entrar">Entrar</a>}
            <a className="lp-btn" href={action}>
              {signedIn ? 'Abrir painel' : 'Criar conta'}
              <ArrowUpRight size={16} />
            </a>
          </div>
        </div>
      </header>
      <main>
        <div className="lp-wrap lp-hero">
          <div className="lp-intro">
            <p className="lp-audience">
              <span /> Para MEIs e pequenas empresas
            </p>
            <h1>
              Sua rotina fiscal,
              <br />
              em ordem.
            </h1>
            <p className="lp-lead">
              Tire dúvidas com o assistente fiscal, organize seus documentos e
              acompanhe as obrigações da sua empresa em um só lugar.
            </p>
            <div className="lp-hero-actions">
              <a href={action} className="lp-btn">
                {signedIn ? 'Acessar meu painel' : 'Criar minha conta'}{' '}
                <ArrowRight size={18} />
              </a>
              <a className="lp-textlink" href="#recursos">
                Conhecer os recursos <ArrowDown size={16} />
              </a>
            </div>
          </div>
          <Preview />
        </div>
        <section id="recursos" className="lp-resources">
          <div className="lp-wrap">
            <h2>
              Da dúvida fiscal
              <br />à próxima tarefa.
            </h2>
            <div className="lp-features">
              {features.map(({ icon: Icon, name, text }) => (
                <article key={name}>
                  <Icon size={26} strokeWidth={1.6} />
                  <h3>{name}</h3>
                  <p>{text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>
        <section id="duvidas" className="lp-wrap lp-faq">
          <div>
            <FileText size={27} strokeWidth={1.6} />
            <h2>Dúvidas frequentes</h2>
          </div>
          <div>
            {questions.map(([q, a]) => (
              <details key={q}>
                <summary>
                  {q}
                  <ChevronDown size={18} />
                </summary>
                <p>{a}</p>
              </details>
            ))}
          </div>
        </section>
      </main>
      <footer>
        <div className="lp-wrap">
          <Brand />
          <a href="#inicio">Voltar ao início ↑</a>
        </div>
      </footer>
    </div>
  );
}
