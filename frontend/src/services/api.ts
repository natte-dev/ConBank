import axios from 'axios';

const API_ORIGIN = import.meta.env.VITE_API_ORIGIN || '';

if (!API_ORIGIN) {
  console.warn('VITE_API_ORIGIN não definido no build do frontend');
}

export const api = axios.create({
  baseURL: API_ORIGIN,
});

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

export const apiService = {
  // Upload de arquivo
  uploadArquivo: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Listar arquivos
  listarArquivos: async (): Promise<Arquivo[]> => {
    const response = await api.get('/arquivos');
    return response.data;
  },

  // Obter resumo
  obterResumo: async (arquivoId: number): Promise<Resumo> => {
    const response = await api.get(`/resumo/${arquivoId}`);
    return response.data;
  },

  // Listar fornecedores
  listarFornecedores: async (
    arquivoId: number,
    status?: string,
    skip: number = 0,
    limit: number = 100
  ): Promise<ListaFornecedoresResponse> => {
    const response = await api.get('/fornecedores', {
      params: { arquivo_id: arquivoId, status, skip, limit },
    });

    const data = response.data;

    // Se veio array direto, embrulha
    if (Array.isArray(data)) {
      return { fornecedores: data };
    }

    // Se já veio no formato esperado, retorna como está
    return data;
  },

  // Obter fornecedor detalhado
  obterFornecedorDetalhado: async (fornecedorId: number): Promise<FornecedorDetalhado> => {
    const response = await api.get(`/fornecedores/${fornecedorId}`);
    return response.data;
  },

  // Listar divergências
  listarDivergencias: async (arquivoId: number): Promise<Divergencia[]> => {
    const response = await api.get('/divergencias', {
      params: { arquivo_id: arquivoId },
    });
    return response.data;
  },

  // Exportar para Excel
  exportarExcel: async (arquivoId: number, tipo: 'completo' | 'em_aberto' | 'divergencias') => {
    const response = await api.get(`/export/excel/${arquivoId}`, {
      params: { tipo },
      responseType: 'blob',
    });
    
    // Criar link para download
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `conciliacao_fornecedores_${tipo}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
  },
};

export default apiService;
