import {
  BookOpen,
  CalendarClock,
  Landmark,
  LayoutDashboard,
  ListChecks,
  MessagesSquare,
} from 'lucide-react';

const areas = [
  ['assistente', MessagesSquare, 'Assistente fiscal', 'Faça perguntas sobre MEI e Simples Nacional. Cada resposta cita a norma que a sustenta.'],
  ['dashboard', LayoutDashboard, 'Visão geral', 'Resumo da situação da empresa, pendências e simulação de valores.'],
  ['fiscal', Landmark, 'Situação fiscal', 'Registre guias, comprovantes e certidões para manter as evidências em dia.'],
  ['obrigacoes', CalendarClock, 'Obrigações', 'Acompanhe o vencimento do DAS, da DASN e de outras guias da empresa.'],
  ['tarefas', ListChecks, 'Tarefas', 'Transforme os próximos passos do assistente em tarefas com prazo.'],
  ['normas', BookOpen, 'Biblioteca de normas', 'Consulte as leis e resoluções vigentes usadas nas respostas.'],
] as const;

export function Ajuda() {
  return (
    <div className="stack max-w-4xl">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Ajuda</h1>
        <p className="text-ink-muted">O que cada área do Sócio Digital faz e como o assistente responde.</p>
      </div>
      <section aria-labelledby="ajuda-areas" className="space-y-3">
        <h2 id="ajuda-areas" className="text-xl font-bold">Áreas do sistema</h2>
        <ul className="grid gap-3 sm:grid-cols-2">
          {areas.map(([href, Icon, title, text]) => (
            <li key={href}>
              <a href={'#' + href} className="panel flex h-full items-start gap-3 hover:border-link">
                <Icon size={20} aria-hidden className="mt-0.5 shrink-0 text-link" />
                <span>
                  <strong className="block">{title}</strong>
                  <span className="text-sm text-ink-muted">{text}</span>
                </span>
              </a>
            </li>
          ))}
        </ul>
      </section>
      <section aria-labelledby="ajuda-respostas" className="panel space-y-2">
        <h2 id="ajuda-respostas" className="text-xl font-bold">Como o assistente responde</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>Usa só normas publicadas e vigentes da Biblioteca; os números entre colchetes, como [1], abrem o trecho citado.</li>
          <li>Quando não encontra norma suficiente, avisa em vez de arriscar uma resposta sem fonte.</li>
          <li>Se faltar um dado, como a competência ou o regime, pede antes de responder.</li>
          <li>Valores de imposto vêm do motor de cálculo, nunca do modelo de linguagem.</li>
          <li>A situação de pagamento só aparece como verificada com comprovante registrado.</li>
        </ul>
      </section>
      <p className="notice text-sm">
        Orientação informativa. Valide decisões fiscais e a escrituração com um profissional registrado no CRC.
      </p>
    </div>
  );
}
