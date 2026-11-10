import React, { useState } from 'react';
import { Send, Bot, User, BookOpen, AlertCircle, Sparkles } from 'lucide-react';
import { Empresa, MensagemAssistente } from '../types';
import { api } from '../services/api';

interface AssistenteProps {
  empresa: Empresa | null;
}

export const Assistente: React.FC<AssistenteProps> = ({ empresa }) => {
  const [mensagens, setMensagens] = useState<MensagemAssistente[]>([
    {
      id: '1',
      remetente: 'copiloto',
      conteudo: `Olá! Sou seu copiloto fiscal do Sócio Digital. Como posso ajudar com o enquadramento, Fator R ou obrigações da sua empresa (${empresa?.razao_social || 'TecnoSoft'}) hoje?`,
      timestamp: 'Agora',
      fontes: [
        {
          norma: 'Lei Complementar nº 123/2006',
          artigo: 'Art. 18',
          trecho: 'Regulamentação das tabelas e alíquotas nominais/efetivas do Simples Nacional.',
        },
      ],
    },
  ]);
  const [inputPergunta, setInputPergunta] = useState('');
  const [carregando, setCarregando] = useState(false);

  const enviarPergunta = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputPergunta.trim() || carregando) return;

    const texto = inputPergunta;
    setInputPergunta('');

    const novaMsgUsuario: MensagemAssistente = {
      id: Date.now().toString(),
      remetente: 'usuario',
      conteudo: texto,
      timestamp: 'Agora',
    };

    setMensagens((prev) => [...prev, novaMsgUsuario]);
    setCarregando(true);

    try {
      const empresaId = empresa?.id || 'empresa-demo';
      const data = await api.perguntarAssistente(empresaId, texto);

      const novaMsgCopiloto: MensagemAssistente = {
        id: (Date.now() + 1).toString(),
        remetente: 'copiloto',
        conteudo: (data as any)?.diagnostico || 'Consulta processada com sucesso contra o acervo oficial.',
        timestamp: 'Agora',
        fontes: (data as any)?.fontes_citadas || [],
        calculo: (data as any)?.calculo,
      };

      setMensagens((prev) => [...prev, novaMsgCopiloto]);
    } catch (err: any) {
      const msgErro: MensagemAssistente = {
        id: (Date.now() + 1).toString(),
        remetente: 'copiloto',
        conteudo: `Houve uma instabilidade na consulta: ${err?.message || 'Serviço temporariamente indisponível'}.`,
        timestamp: 'Agora',
      };
      setMensagens((prev) => [...prev, msgErro]);
    } finally {
      setCarregando(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-slate-50">
      {/* Lista de Mensagens */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 max-w-4xl mx-auto w-full">
        {mensagens.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.remetente === 'usuario' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.remetente === 'copiloto' && (
              <div className="w-8 h-8 rounded-lg bg-emerald-500 text-slate-950 flex items-center justify-center shrink-0 mt-1 shadow-sm font-bold">
                <Bot className="w-4 h-4" />
              </div>
            )}

            <div
              className={`max-w-2xl rounded-2xl p-4 text-xs leading-relaxed space-y-3 ${
                msg.remetente === 'usuario'
                  ? 'bg-slate-900 text-white rounded-tr-none'
                  : 'bg-white border border-slate-200 text-slate-800 rounded-tl-none shadow-sm'
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.conteudo}</p>

              {/* Bloco de Citações / Fontes Oficiais */}
              {msg.fontes && msg.fontes.length > 0 && (
                <div className="pt-3 border-t border-slate-100 space-y-1.5">
                  <div className="flex items-center gap-1.5 font-bold text-[11px] text-emerald-700">
                    <BookOpen className="w-3.5 h-3.5" />
                    <span>Fontes Oficiais Verificadas (Grounding RAG):</span>
                  </div>
                  {msg.fontes.map((f, i) => (
                    <div key={i} className="bg-slate-50 p-2 rounded border border-slate-200/60 text-[11px]">
                      <span className="font-semibold text-slate-900">{f.norma}</span> ({f.artigo}): {f.trecho}
                    </div>
                  ))}
                </div>
              )}

              {/* Disclaimer do CRC */}
              {msg.remetente === 'copiloto' && (
                <div className="pt-2 text-[10px] text-slate-400 border-t border-slate-100 flex items-center gap-1">
                  <AlertCircle className="w-3 h-3 text-amber-500 shrink-0" />
                  <span>Orientação com base na LC 123/2006. Não substitui escrituração contábil formal (CRC).</span>
                </div>
              )}
            </div>

            {msg.remetente === 'usuario' && (
              <div className="w-8 h-8 rounded-lg bg-slate-800 text-white flex items-center justify-center shrink-0 mt-1 font-bold">
                <User className="w-4 h-4" />
              </div>
            )}
          </div>
        ))}

        {carregando && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-lg bg-emerald-500 text-slate-950 flex items-center justify-center shrink-0 mt-1">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-none p-4 text-xs text-slate-500 flex items-center gap-2 shadow-sm">
              <Sparkles className="w-4 h-4 text-emerald-500 animate-spin" />
              Consultando acervo oficial e executando motor determinístico...
            </div>
          </div>
        )}
      </div>

      {/* Caixa de Entrada de Texto */}
      <div className="p-4 bg-white border-t border-slate-200">
        <form onSubmit={enviarPergunta} className="max-w-4xl mx-auto flex gap-3">
          <input
            type="text"
            value={inputPergunta}
            onChange={(e) => setInputPergunta(e.target.value)}
            placeholder="Ex: Como calcular o Fator R com folha de 28% no Simples Nacional?"
            className="flex-1 px-4 py-2.5 rounded-xl border border-slate-200 text-xs focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all"
          />
          <button
            type="submit"
            disabled={!inputPergunta.trim() || carregando}
            className="px-4 py-2.5 bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50 text-slate-950 font-bold rounded-xl transition-all flex items-center gap-2 text-xs"
          >
            <Send className="w-3.5 h-3.5" />
            Enviar
          </button>
        </form>
      </div>
    </div>
  );
};
