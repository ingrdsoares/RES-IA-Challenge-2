export interface Empresa {
  id: string;
  cnpj: string;
  razao_social: string;
  nome_fantasia?: string;
  porte: 'MEI' | 'ME' | 'EPP';
  cnae_principal: string;
  municipio: string;
  uf: string;
  regime: 'SIMPLES_NACIONAL' | 'SIMEI' | 'LUCRO_PRESUMIDO';
  faturamento_anual?: number;
  folha_anual?: number;
  created_at: string;
}

export interface UserAccount {
  id: string;
  email: string;
  nome: string;
  created_at: string;
}

export interface MensagemAssistente {
  id: string;
  remetente: 'usuario' | 'copiloto';
  conteudo: string;
  timestamp: string;
  fontes?: Array<{
    norma: string;
    artigo: string;
    trecho: string;
  }>;
  calculo?: {
    anexo_aplicado: string;
    aliquota_efetiva: number;
    das_mensal: number;
    fator_r?: number;
  };
}

export interface TarefaFiscal {
  id: string;
  titulo: string;
  competencia: string;
  data_vencimento: string;
  status: 'PENDENTE' | 'CONCLUIDA' | 'ATRASADA';
  tipo: 'OBRIGACAO_PRINCIPAL' | 'OBRIGACAO_ACESSORIA';
  valor?: number;
}
