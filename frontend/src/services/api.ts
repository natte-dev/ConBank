import axios from 'axios';

// VITE_API_URL é injetado em tempo de build pelo Vite.
// Configure no EasyPanel → App (frontend) → Build Args:
//   VITE_API_URL=https://seu-backend.easypanel.host
// Se vazio, o axios usa caminhos relativos (frontend e backend no mesmo domínio).
const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120_000, // 2 min — uploads de PDF podem demorar
});

// ─── Tipos ────────────────────────────────────────────────────────────────────

export interface Arquivo {
  id: number;
  nome_arquivo: string;
  status: string;
  total_fornecedores: number;
  total_lancamentos: number;
  periodo_inicio: string | null;
  periodo_fim: string | null;
  created_at: string;
}

export interface Resumo {
  arquivo: {
    id: number;
    nome: string;
    periodo_inicio: string | null;
    periodo_fim: string | null;
  };
  estatisticas: {
    total_fornecedores: number;
    total_lancamentos: number;
    fornecedores_quitados: number;
    fornecedores_em_aberto: number;
    fornecedores_adiantados: number;
    fornecedores_com_divergencia: number;
    valor_total_a_pagar: number;
  };
}

export interface Fornecedor {
  id: number;
  codigo_conta: string;
  conta_contabil: string;
  nome_fornecedor: string;
  total_credito: number;
  total_debito: number;
  saldo_final: number;
  valor_a_pagar: number;
  status_pagamento: string;
  qtd_nfs_pendentes: number;
  qtd_nfs_parciais: number;
  divergencia_calculo: boolean;
}

export interface FornecedorDetalhado {
  fornecedor: Fornecedor & {
    cnpj: string | null;
    saldo_anterior: number;
  };
  compras_pendentes: Array<{
    id: number;
    data_lancamento: string;
    numero_nf: string | null;
    historico: string;
    valor_total: number;
    valor_pago_parcial: number;
    valor_saldo: number;
    status_pagamento: string;
  }>;
  todos_lancamentos: Array<{
    id: number;
    data: string;
    lote: string | null;
    historico: string;
    tipo_operacao: string;
    valor_debito: number;
    valor_credito: number;
    saldo_apos: number;
  }>;
}

export interface Divergencia {
  id: number;
  fornecedor_id: number;
  tipo: string;
  severidade: string;
  descricao: string;
  diferenca: number;
  created_at: string;
}

export interface ListaFornecedoresResponse {
  fornecedores: Fornecedor[];
  total?: number;
}

// ─── Serviços ─────────────────────────────────────────────────────────────────

export const apiService = {

  uploadArquivo: async (file: File) => {
    const form = new FormData();
    form.append('file', file);
    const { data } = await api.post('/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  listarArquivos: async (): Promise<Arquivo[]> => {
    const { data } = await api.get('/arquivos');
    return data;
  },

  obterResumo: async (arquivoId: number): Promise<Resumo> => {
    const { data } = await api.get(`/resumo/${arquivoId}`);
    return data;
  },

  listarFornecedores: async (
    arquivoId: number,
    status?: string,
    skip = 0,
    limit = 100,
  ): Promise<ListaFornecedoresResponse> => {
    const { data } = await api.get('/fornecedores', {
      params: { arquivo_id: arquivoId, status, skip, limit },
    });
    return Array.isArray(data) ? { fornecedores: data } : data;
  },

  obterFornecedorDetalhado: async (fornecedorId: number): Promise<FornecedorDetalhado> => {
    const { data } = await api.get(`/fornecedores/${fornecedorId}`);
    return data;
  },

  listarDivergencias: async (arquivoId: number): Promise<Divergencia[]> => {
    const { data } = await api.get('/divergencias', {
      params: { arquivo_id: arquivoId },
    });
    return data;
  },

  exportarExcel: async (arquivoId: number, tipo: 'completo' | 'em_aberto' | 'divergencias') => {
    const { data } = await api.get(`/export/excel/${arquivoId}`, {
      params: { tipo },
      responseType: 'blob',
    });
    const url  = window.URL.createObjectURL(new Blob([data]));
    const link = document.createElement('a');
    link.href  = url;
    link.setAttribute('download', `conciliacao_${tipo}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
};

export default apiService;
