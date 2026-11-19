import { useEffect, useState } from 'react';
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Building2,
  Calculator,
  Check,
  ChevronDown,
  Circle,
  FileCheck2,
  FileText,
  FolderOpen,
  LayoutDashboard,
  ListChecks,
  Lock,
  MessageSquareText,
  Paperclip,
  Pause,
  Play,
  Scale,
  ShieldCheck,
} from 'lucide-react';
import { Brand } from '../components/Header';
import './landing.css';

const views = [
  { name: 'Painel', title: 'Visão geral', icon: LayoutDashboard },
  { name: 'Tarefas', title: 'Tarefas da empresa', icon: ListChecks },
  { name: 'Fontes', title: 'Fontes da consulta', icon: BookOpen },
] as const;

const previewInterval = 6500;
const reducedMotion = '(prefers-reduced-motion: reduce)';

function Preview() {
  const [view, setView] = useState(0);
  const [done, setDone] = useState(false);
  const [playing, setPlaying] = useState(
    () => !window.matchMedia(reducedMotion).matches && !document.hidden,
  );

  useEffect(() => {
    const media = window.matchMedia(reducedMotion);
    const stopForPreference = () => {
      if (media.matches) setPlaying(false);
    };
    const stopIfHidden = () => {
      if (document.hidden) setPlaying(false);
    };
    media.addEventListener('change', stopForPreference);
    document.addEventListener('visibilitychange', stopIfHidden);
    return () => {
      media.removeEventListener('change', stopForPreference);
      document.removeEventListener('visibilitychange', stopIfHidden);
    };
  }, []);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setTimeout(() => {
      setView((current) => (current + 1) % views.length);
    }, previewInterval);
    return () => window.clearTimeout(timer);
  }, [playing, view]);
  return (
    <section className="lp-preview" aria-label="Demonstração da plataforma">
      <div className="lp-preview-label">
        <span className="lp-dot" aria-hidden="true" /> Prévia interativa · Dados ilustrativos
        <button
          className="lp-preview-play"
          type="button"
          aria-label={playing ? 'Pausar prévia' : 'Reproduzir prévia'}
          onClick={() => setPlaying((current) => !current)}
        >
          {playing ? <Pause size={20} aria-hidden="true" /> : <Play size={20} aria-hidden="true" />}
        </button>
      </div>
      <div className="lp-folder">
        <div className="lp-tab" aria-hidden="true">
          <FolderOpen size={17} /> Pasta fiscal
        </div>
        <div
          className="lp-paper"
          onFocus={() => setPlaying(false)}
          onPointerDown={() => setPlaying(false)}
        >
          <div className="lp-paper-meta">
            <span>Empresa de exemplo</span>
            <Building2 size={16} />
          </div>
          <div key={view} className="lp-preview-screen">
            <h2>{views[view].title}</h2>
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
            type="button"
            onClick={() => {
              setPlaying(false);
              setView(i);
            }}
          >
            <Icon size={15} />
            {name}
          </button>
        ))}
      </div>
      <div className="lp-preview-progress" aria-hidden="true">
        {playing && <span key={view} style={{ animationDuration: previewInterval + 'ms' }} />}
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
    'Crie uma conta com e-mail e senha. Depois, informe CNPJ, CNAE, porte, regime tributário e município para abrir o assistente fiscal.',
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

const trustBadges = [
  {
    icon: Scale,
    title: 'Fontes Normativas Oficiais',
    desc: 'RAG alimentado com publicações atualizadas da Receita Federal, CGSN, Planalto e Diário Oficial da União.',
  },
  {
    icon: Lock,
    title: 'Privacidade de Dados & LGPD',
    desc: 'Seus dados fiscais e cadastrais permanecem confidenciais. A telemetria analítica não armazena dados sensíveis da sua empresa.',
  },
  {
    icon: ShieldCheck,
    title: 'Rastreabilidade e Citação Jurídica',
    desc: 'Cada resposta do assistente referencia os artigos, incisos e leis vigentes para conferência direta na fonte.',
  },
];

function TrustSection() {
  return (
    <section className="border-t border-b border-border-subtle bg-white py-14">
      <div className="lp-wrap">
        <div className="mx-auto mb-10 max-w-2xl text-center">
          <p className="mb-2 text-xs font-bold uppercase tracking-wider text-link">
            Segurança & Conformidade
          </p>
          <h2 className="text-2xl font-bold tracking-tight md:text-3xl">
            Transparência jurídica e dados protegidos
          </h2>
        </div>
        <div className="grid gap-6 md:grid-cols-3">
          {trustBadges.map(({ icon: Icon, title, desc }) => (
            <div
              key={title}
              className="rounded-xl border border-slate-200 bg-surface-muted/30 p-6"
            >
              <span className="mb-3 inline-flex rounded-lg bg-info/10 p-2.5 text-link">
                <Icon size={22} />
              </span>
              <h3 className="mb-2 text-base font-bold text-ink">{title}</h3>
              <p className="text-xs leading-relaxed text-slate-600">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function PublicSimulator({ action }: { action: string }) {
  const [regime, setRegime] = useState<'mei' | 'simples'>('mei');
  const [meiActivity, setMeiActivity] = useState<
    'comercio' | 'servico' | 'misto'
  >('servico');
  const [monthlyRevenue, setMonthlyRevenue] = useState(15000);
  const [simplesType, setSimplesType] = useState<
    'comercio' | 'servico_anexo3' | 'servico_anexo5'
  >('servico_anexo3');

  const money = new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  });

  const meiValues = {
    comercio: { amount: 75.6, desc: 'INSS (R$ 74,60) + ICMS (R$ 1,00)' },
    servico: { amount: 79.6, desc: 'INSS (R$ 74,60) + ISS (R$ 5,00)' },
    misto: {
      amount: 80.6,
      desc: 'INSS (R$ 74,60) + ICMS (R$ 1,00) + ISS (R$ 5,00)',
    },
  };

  const simplesRates = {
    comercio: {
      rate: 0.04,
      label: 'Anexo I (Comércio - alíquota inicial ~4%)',
    },
    servico_anexo3: {
      rate: 0.06,
      label: 'Anexo III (Serviços com Fator R ≥ 28% - alíquota inicial ~6%)',
    },
    servico_anexo5: {
      rate: 0.155,
      label: 'Anexo V (Serviços sem Fator R - alíquota inicial ~15,5%)',
    },
  };

  const calculatedSimples = monthlyRevenue * simplesRates[simplesType].rate;

  return (
    <section id="simulador" className="lp-wrap my-16">
      <div className="rounded-2xl border border-border-subtle bg-surface-muted/60 p-6 shadow-sm md:p-10">
        <div className="mb-8 max-w-2xl">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-info/10 px-3 py-1 text-xs font-semibold text-link">
            <Calculator size={14} /> Simulação Instantânea Pública
          </div>
          <h2 className="text-2xl font-bold tracking-tight md:text-3xl">
            Descubra quanto você paga de imposto mensal
          </h2>
          <p className="mt-2 text-sm text-ink-muted">
            Calcule uma estimativa do DAS para a sua atividade e conheça os
            direitos garantidos pelo seu recolhimento em dia.
          </p>
        </div>

        <div className="grid items-start gap-8 lg:grid-cols-2">
          <div className="space-y-5 rounded-xl border border-border-subtle bg-white p-6">
            <div>
              <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">
                1. Escolha o regime tributário
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setRegime('mei')}
                  className={
                    'rounded-lg px-3 py-2.5 text-sm font-semibold transition-colors ' +
                    (regime === 'mei'
                      ? 'bg-slate-900 text-white'
                      : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50')
                  }
                >
                  MEI (Até R$ 81 mil/ano)
                </button>
                <button
                  type="button"
                  onClick={() => setRegime('simples')}
                  className={
                    'rounded-lg px-3 py-2.5 text-sm font-semibold transition-colors ' +
                    (regime === 'simples'
                      ? 'bg-slate-900 text-white'
                      : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50')
                  }
                >
                  Simples Nacional
                </button>
              </div>
            </div>

            {regime === 'mei' ? (
              <div className="space-y-4">
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-500">
                  2. Atividade exercida
                </label>
                <div className="space-y-2">
                  {[
                    { id: 'comercio' as const, label: 'Comércio ou Indústria' },
                    { id: 'servico' as const, label: 'Prestação de Serviços' },
                    {
                      id: 'misto' as const,
                      label: 'Comércio e Serviços (Misto)',
                    },
                  ].map((act) => (
                    <label
                      key={act.id}
                      className={
                        'flex cursor-pointer items-center gap-3 rounded-lg border p-3 text-sm font-medium transition-colors ' +
                        (meiActivity === act.id
                          ? 'border-link bg-info/10 text-ink'
                          : 'border-slate-200 hover:bg-slate-50')
                      }
                    >
                      <input
                        type="radio"
                        name="meiActivity"
                        checked={meiActivity === act.id}
                        onChange={() => setMeiActivity(act.id)}
                        className="text-link"
                      />
                      <span>{act.label}</span>
                    </label>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <div className="mb-2 flex justify-between text-xs font-bold uppercase tracking-wider text-slate-500">
                    <span>2. Faturamento mensal estimado</span>
                    <span className="font-bold text-ink">
                      {money.format(monthlyRevenue)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="3000"
                    max="100000"
                    step="1000"
                    value={monthlyRevenue}
                    onChange={(e) => setMonthlyRevenue(Number(e.target.value))}
                    className="w-full cursor-pointer accent-slate-900"
                  />
                </div>
                <div>
                  <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">
                    3. Tipo de atividade e enquadramento
                  </label>
                  <select
                    value={simplesType}
                    onChange={(e) =>
                      setSimplesType(
                        e.target.value as
                          | 'comercio'
                          | 'servico_anexo3'
                          | 'servico_anexo5',
                      )
                    }
                    className="w-full rounded-lg border border-slate-200 bg-white p-2.5 text-sm"
                  >
                    <option value="comercio">
                      {simplesRates.comercio.label}
                    </option>
                    <option value="servico_anexo3">
                      {simplesRates.servico_anexo3.label}
                    </option>
                    <option value="servico_anexo5">
                      {simplesRates.servico_anexo5.label}
                    </option>
                  </select>
                </div>
              </div>
            )}
          </div>

          <div className="flex h-full flex-col justify-between rounded-xl border border-border-subtle bg-white p-6 shadow-sm">
            <div>
              <span className="mb-1 block text-xs font-bold uppercase tracking-wider text-slate-500">
                Estimativa mensal do DAS
              </span>
              <div className="my-2 text-4xl font-extrabold text-ink">
                {regime === 'mei'
                  ? money.format(meiValues[meiActivity].amount)
                  : money.format(calculatedSimples)}
                <span className="text-sm font-normal text-slate-500">
                  {' '}
                  /mês
                </span>
              </div>
              <p className="mb-4 text-xs text-slate-600">
                {regime === 'mei'
                  ? `Composição: ${meiValues[meiActivity].desc}. Valor fixo independente do faturamento mensal.`
                  : `Estimativa para faturamento de ${money.format(monthlyRevenue)}. Alíquota efetiva calculada conforme o faturamento acumulado.`}
              </p>

              <div className="space-y-2 border-t border-slate-100 pt-4 text-xs">
                <strong className="block text-slate-800">
                  Direitos e benefícios garantidos:
                </strong>
                <ul className="space-y-1.5 text-slate-600">
                  <li className="flex items-center gap-2">
                    <Check size={14} className="shrink-0 text-emerald-600" />
                    <span>Aposentadoria por idade e invalidez</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <Check size={14} className="shrink-0 text-emerald-600" />
                    <span>Auxílio por incapacidade temporária e maternidade</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <Check size={14} className="shrink-0 text-emerald-600" />
                    <span>Emissão regular de notas fiscais de venda/serviço</span>
                  </li>
                </ul>
              </div>
            </div>

            <div className="mt-6 border-t border-slate-100 pt-4">
              <a href={action} className="lp-btn w-full justify-center">
                Cadastrar e Acompanhar Minhas Guias <ArrowRight size={16} />
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export function Landing({ signedIn }: { signedIn: boolean }) {
  const action = signedIn ? '#assistente' : '#criar-conta';
  return (
    <div className="lp" id="inicio">
      <header className="lp-header">
        <div className="lp-wrap lp-nav">
          <Brand />
          <nav aria-label="Sobre o Sócio Digital">
            <a href="#recursos">Recursos</a>
            <a href="#simulador">Simulador</a>
            <a href="#duvidas">Dúvidas</a>
          </nav>
          <div className="lp-nav-actions">
            {!signedIn && <a href="#entrar">Entrar</a>}
            <a className="lp-btn" href={action}>
              {signedIn ? 'Abrir assistente' : 'Criar conta'}
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
                {signedIn ? 'Acessar meu assistente' : 'Criar minha conta'}{' '}
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
        <PublicSimulator action={action} />
        <TrustSection />
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
