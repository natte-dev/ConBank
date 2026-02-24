import React, { useState, useEffect } from 'react'
import {
  Upload,
  Search,
  Download,
  X,
  FileText,
  CheckCircle,
  AlertCircle,
  DollarSign,
  Moon,
  Sun,
} from 'lucide-react'
import apiService from './services/api'
import type { Arquivo, Fornecedor, FornecedorDetalhado } from './services/api'

interface Resumo {
  total_fornecedores: number
  total_lancamentos: number
  fornecedores_quitados: number
  fornecedores_em_aberto: number
  fornecedores_adiantados: number
  fornecedores_com_divergencia: number
  valor_total_a_pagar: number
}

// Componente PaginaFornecedores removido - não estava sendo usado
// Referenciava componentes não definidos: FiltroParciaisPendentes, ListaFornedores

// CÓDIGO ORIGINAL DO COMPONENTE (removido):
// const PaginaFornecedores = () => {
//   const [fornecedores, setFornecedores] = useState([])
//   return (
//     <div>
//       <FiltroParciaisPendentes arquivoId={1} onFiltroAplicado={setFornecedores} />
//       <ListaFornedores data={fornecedores} />
//     </div>
//   )
// }

// Estilos CSS embutidos
const styles = `
  * {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  :root {
    --bg: #f8f9fa;
    --card: #ffffff;
    --text: #2c3e50;
    --muted: #64748b;
    --border: #e2e8f0;
    --soft: #f8fafc;
    --shadow: 0 2px 8px rgba(0,0,0,0.04);
  }

  body.dark {
    --bg: #0b1220;
    --card: #0f172a;
    --text: #e2e8f0;
    --muted: #94a3b8;
    --border: #243244;
    --soft: #0b1220;
    --shadow: 0 8px 24px rgba(0,0,0,0.35);
  }

  body.dark .logo {
    filter: brightness(0) invert(1);
    opacity: 0.9;  
  }

  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
    background: var(--bg);
    color: var(--text);
  }

  .container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 2rem;
  }

  .logo {
    width: 120px;
    height: auto;
    object-fit: contain;  
  }

  .header {
    background: var(--card);
    padding: 2rem;
    border-radius: 12px;
    box-shadow: var(--shadow);
    margin-bottom: 2rem;
  }

  .header h1 {
    font-size: 1.75rem;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 0.5rem;
  }

  .header p {
    color: var(--muted);
    font-size: 0.95rem;
  }

  .header-content {
    display: flex;
    align-items: center;
    gap: 15px;
  }

  .header-text h1 {
    font-size: 1.75rem;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 0.5rem;
  }

  .header-text p {
    color: var(--muted);
    font-size: 0.95rem;
  }

  .dark-toggle {
    margin-left: auto;
    white-space: nowrap;
  }

  .upload-section {
    background: var(--card);
    padding: 2rem;
    border-radius: 12px;
    box-shadow: var(--shadow);
    margin-bottom: 2rem;
  }

  .upload-area {
    border: 2px dashed var(--border);
    border-radius: 8px;
    padding: 2rem;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
    background: var(--soft);
  }

  .upload-area:hover {
    border-color: #3b82f6;
    background: rgba(59, 130, 246, 0.08);
  }

  .upload-icon {
    width: 48px;
    height: 48px;
    margin: 0 auto 1rem;
    color: #3b82f6;
  }

  .file-info {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(100, 116, 139, 0.10);
    padding: 1rem;
    border-radius: 8px;
    margin-top: 1rem;
  }

  .btn {
    padding: 0.75rem 1.5rem;
    border-radius: 8px;
    border: none;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.95rem;
  }

  .btn-primary {
    background: #3b82f6;
    color: white;
  }

  .btn-primary:hover {
    background: #2563eb;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
  }

  .btn-secondary {
    background: rgba(100, 116, 139, 0.12);
    color: var(--text);
  }

  .btn-secondary:hover {
    background: rgba(100, 116, 139, 0.18);
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1.5rem;
    margin-bottom: 2rem;
  }

  .stat-card {
    background: var(--card);
    padding: 1.75rem;
    border-radius: 12px;
    box-shadow: var(--shadow);
    transition: all 0.2s;
    position: relative;
    overflow: hidden;
  }

  .stat-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(0,0,0,0.18);
  }

  .stat-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, #3b82f6, #60a5fa);
  }

  .stat-card.success::before {
    background: linear-gradient(90deg, #10b981, #34d399);
  }

  .stat-card.warning::before {
    background: linear-gradient(90deg, #f59e0b, #fbbf24);
  }

  .stat-card.info::before {
    background: linear-gradient(90deg, #8b5cf6, #a78bfa);
  }

  .stat-icon {
    width: 40px;
    height: 40px;
    padding: 8px;
    border-radius: 8px;
    background: rgba(59, 130, 246, 0.12);
    color: #3b82f6;
    margin-bottom: 1rem;
  }

  .stat-card.success .stat-icon {
    background: rgba(16, 185, 129, 0.14);
    color: #10b981;
  }

  .stat-card.warning .stat-icon {
    background: rgba(245, 158, 11, 0.14);
    color: #f59e0b;
  }

  .stat-card.info .stat-icon {
    background: rgba(139, 92, 246, 0.14);
    color: #8b5cf6;
  }

  .stat-label {
    font-size: 0.875rem;
    color: var(--muted);
    margin-bottom: 0.5rem;
  }

  .stat-value {
    font-size: 1.75rem;
    font-weight: 600;
    color: var(--text);
  }

  .controls {
    background: var(--card);
    padding: 1.5rem;
    border-radius: 12px;
    box-shadow: var(--shadow);
    margin-bottom: 2rem;
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    align-items: center;
  }

  .search-box {
    flex: 1;
    min-width: 250px;
    position: relative;
  }

  .search-box input {
    width: 100%;
    padding: 0.75rem 1rem 0.75rem 2.75rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 0.95rem;
    transition: all 0.2s;
    background: var(--card);
    color: var(--text);
  }

  .search-box input:focus {
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }

  .search-icon {
    position: absolute;
    left: 0.875rem;
    top: 50%;
    transform: translateY(-50%);
    color: var(--muted);
    width: 18px;
    height: 18px;
  }

  .filter-select {
    padding: 0.75rem 1rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 0.95rem;
    background: var(--card);
    color: var(--text);
    cursor: pointer;
    transition: all 0.2s;
  }

  .filter-select:focus {
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }

  .export-section {
    display: flex;
    gap: 0.75rem;
    align-items: center;
    flex-wrap: wrap;
  }

  .export-label {
    font-size: 0.875rem;
    color: var(--muted);
    font-weight: 500;
  }

  .table-container {
    background: var(--card);
    border-radius: 12px;
    box-shadow: var(--shadow);
    overflow: hidden;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  thead {
    background: var(--soft);
    border-bottom: 1px solid var(--border);
  }

  th {
    padding: 1rem;
    text-align: left;
    font-weight: 600;
    font-size: 0.875rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  td {
    padding: 1rem;
    border-bottom: 1px solid var(--border);
    font-size: 0.95rem;
    color: var(--text);
  }

  tbody tr {
    transition: background 0.2s;
    cursor: pointer;
  }

  tbody tr:hover {
    background: rgba(100, 116, 139, 0.10);
  }

  .status-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.75rem;
    border-radius: 6px;
    font-size: 0.8125rem;
    font-weight: 500;
  }

  .status-badge.success {
    background: rgba(16, 185, 129, 0.18);
    color: #10b981;
  }

  .status-badge.warning {
    background: rgba(245, 158, 11, 0.18);
    color: #f59e0b;
  }

  .status-badge.info {
    background: rgba(59, 130, 246, 0.18);
    color: #3b82f6;
  }

  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    animation: fadeIn 0.2s;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  .modal {
    background: var(--card);
    border-radius: 16px;
    width: 90%;
    max-width: 800px;
    max-height: 85vh;
    overflow: hidden;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    animation: slideUp 0.3s;
    color: var(--text);
  }

  @keyframes slideUp {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .modal-header {
    padding: 1.75rem 2rem;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .modal-header h2 {
    font-size: 1.375rem;
    font-weight: 600;
    color: var(--text);
  }

  .modal-close {
    width: 32px;
    height: 32px;
    border-radius: 6px;
    border: none;
    background: rgba(100, 116, 139, 0.12);
    color: var(--text);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
  }

  .modal-close:hover {
    background: rgba(100, 116, 139, 0.18);
  }

  .modal-body {
    padding: 2rem;
    overflow-y: auto;
    max-height: calc(85vh - 140px);
  }

  .info-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1.5rem;
    margin-bottom: 2rem;
  }

  .info-item {
    background: rgba(100, 116, 139, 0.10);
    padding: 1.25rem;
    border-radius: 8px;
    border-left: 3px solid #3b82f6;
  }

  .info-item.success {
    border-left-color: #10b981;
  }

  .info-item.warning {
    border-left-color: #f59e0b;
  }

  .info-label {
    font-size: 0.8125rem;
    color: var(--muted);
    margin-bottom: 0.375rem;
    font-weight: 500;
  }

  .info-value {
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text);
  }

  .section-title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--text);
    margin: 2rem 0 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid var(--border);
  }

  .compra-item {
    background: rgba(100, 116, 139, 0.10);
    padding: 1.25rem;
    border-radius: 8px;
    margin-bottom: 0.75rem;
    border-left: 3px solid #f59e0b;
  }

  .compra-header {
    display: flex;
    justify-content: space-between;
    align-items: start;
    margin-bottom: 0.75rem;
  }

  .compra-info {
    flex: 1;
  }

  .compra-nf {
    font-weight: 600;
    color: var(--text);
    margin-bottom: 0.25rem;
  }

  .compra-data {
    font-size: 0.8125rem;
    color: var(--muted);
  }

  .compra-status {
    padding: 0.25rem 0.625rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.025em;
  }

  .compra-status.PARCIAL {
    background: rgba(245, 158, 11, 0.18);
    color: #f59e0b;
  }

  .compra-status.PENDENTE {
    background: rgba(239, 68, 68, 0.18);
    color: #ef4444;
  }

  .compra-valores {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--border);
  }

  .valor-item {
    text-align: center;
  }

  .valor-label {
    font-size: 0.75rem;
    color: var(--muted);
    margin-bottom: 0.25rem;
  }

  .valor-amount {
    font-weight: 600;
    color: var(--text);
    font-size: 0.9375rem;
  }

  .empty-state {
    text-align: center;
    padding: 4rem 2rem;
    color: var(--muted);
  }

  .empty-state svg {
    width: 64px;
    height: 64px;
    margin: 0 auto 1rem;
    opacity: 0.5;
  }

  .error {
    background: rgba(239, 68, 68, 0.18);
    color: #ef4444;
    padding: 1rem 1.5rem;
    border-radius: 8px;
    margin: 1rem 0;
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  @media (max-width: 768px) {
    .container {
      padding: 1rem;
    }

    .stats-grid {
      grid-template-columns: 1fr;
    }

    .controls {
      flex-direction: column;
      align-items: stretch;
    }

    .search-box {
      min-width: 100%;
    }

    table {
      font-size: 0.875rem;
    }

    th, td {
      padding: 0.75rem 0.5rem;
    }

    .modal {
      width: 95%;
      max-height: 90vh;
    }

    .info-grid {
      grid-template-columns: 1fr;
    }

    .compra-valores {
      grid-template-columns: 1fr;
    }

    .header-content {
      flex-wrap: wrap;
    }

    .dark-toggle {
      margin-left: 0;
      width: 100%;
      justify-content: center;
    }
  }
`

function App() {
  const [arquivos, setArquivos] = useState<Arquivo[]>([])
  const [arquivoSelecionado, setArquivoSelecionado] = useState<number | null>(null)
  const [resumo, setResumo] = useState<Resumo | null>(null)
  const [fornecedores, setFornecedores] = useState<Fornecedor[]>([])
  const [fornecedorDetalhado, setFornecedorDetalhado] = useState<FornecedorDetalhado | null>(null)
  const [uploading, setUploading] = useState(false)
  const [statusFiltro, setStatusFiltro] = useState<string>('')
  const [busca, setBusca] = useState('')
  const [erro, setErro] = useState<string | null>(null)

  // ✅ Dark mode com persistência
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('darkMode') === 'true')

  useEffect(() => {
    document.body.classList.toggle('dark', darkMode)
    localStorage.setItem('darkMode', String(darkMode))
  }, [darkMode])

  useEffect(() => {
    carregarArquivos()
  }, [])

  useEffect(() => {
    if (arquivoSelecionado !== null) {
      carregarResumo(arquivoSelecionado)
      carregarFornecedores(arquivoSelecionado)
    }
  }, [arquivoSelecionado, statusFiltro])

  const carregarArquivos = async () => {
    try {
      const data = await apiService.listarArquivos()
      setArquivos(data)
      if (data.length > 0 && !arquivoSelecionado) {
        setArquivoSelecionado(data[0].id)
      }
    } catch (error) {
      console.error('Erro ao carregar arquivos:', error)
    }
  }

  const carregarResumo = async (id: number) => {
    try {
      const data = await apiService.obterResumo(id)
      setResumo(data.estatisticas)
    } catch (error) {
      console.error('Erro ao carregar resumo:', error)
    }
  }

  const carregarFornecedores = async (id: number) => {
    try {
      const data = await apiService.listarFornecedores(id, statusFiltro)
      setFornecedores(data.fornecedores)
    } catch (error) {
      console.error('Erro ao carregar fornecedores:', error)
    }
  }

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    try {
      setUploading(true)
      setErro(null)
      await apiService.uploadArquivo(file)
      await carregarArquivos()
      event.target.value = ''
    } catch (error: any) {
      console.error('Erro no upload:', error)
      const errorDetail = error.response?.data?.detail || 'Erro desconhecido'
      setErro(errorDetail)
      event.target.value = ''
    } finally {
      setUploading(false)
    }
  }

  const handleVerDetalhes = async (id: number) => {
    try {
      const data = await apiService.obterFornecedorDetalhado(id)
      setFornecedorDetalhado(data)
    } catch (error) {
      console.error('Erro ao carregar detalhes:', error)
    }
  }

  const handleExportar = async (tipo: 'completo' | 'em_aberto' | 'divergencias') => {
    if (!arquivoSelecionado) return
    try {
      await apiService.exportarExcel(arquivoSelecionado, tipo)
    } catch (error) {
      alert('Erro ao exportar arquivo')
    }
  }

  const formatarMoeda = (valor: number) => {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
    }).format(valor)
  }

  const formatarData = (data: string | null) => {
    if (!data) return '-'
    return new Date(data).toLocaleDateString('pt-BR')
  }

  const fornecedoresFiltrados = fornecedores.filter(f =>
    f.nome_fornecedor.toLowerCase().includes(busca.toLowerCase()) ||
    f.codigo_conta.includes(busca)
  )

  return (
    <>
      <style>{styles}</style>

      <div className="container">
        <div className="header">
          <div className="header-content">
            {/* Logo temporariamente comentado - arquivo logo-41.png não encontrado */}
            {/* <img src={logo} alt="Logo 41 Contábil" className="logo" /> */}
            {/* Alternativa: colocar logo.png em frontend/public/ e usar: */}
            {/* <img src="/logo.png" alt="Logo 41 Contábil" className="logo" /> */}

            <div className="header-text">
              <h1>41 Contábil - Conciliador Bancário</h1>
              <p>ConcilPro</p>
            </div>

            <button
              className="btn btn-secondary dark-toggle"
              onClick={() => setDarkMode(v => !v)}
              type="button"
              title="Alternar tema"
            >
              {darkMode ? <Sun size={18} /> : <Moon size={18} />}
              {darkMode ? 'Claro' : 'Escuro'}
            </button>
          </div>
        </div>

        <div className="upload-section">
          <label htmlFor="fileInput" style={{ cursor: 'pointer' }}>
            <div className="upload-area">
              <Upload className="upload-icon" />
              <h3>Importar PDF</h3>
              <p>Clique para selecionar um arquivo</p>
            </div>
          </label>

          <input
            id="fileInput"
            type="file"
            accept=".pdf"
            onChange={handleUpload}
            disabled={uploading}
            style={{ display: 'none' }}
          />

          {erro && (
            <div className="error">
              <AlertCircle size={20} />
              <span>{erro}</span>
            </div>
          )}
        </div>

        {arquivos.length > 0 && (
          <>
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ fontSize: '0.875rem', color: 'var(--muted)', fontWeight: 500, marginBottom: '0.5rem', display: 'block' }}>
                Arquivo Importado
              </label>

              <select
                className="filter-select"
                style={{ width: '100%' }}
                value={arquivoSelecionado || ''}
                onChange={(e) => setArquivoSelecionado(Number(e.target.value))}
              >
                {arquivos.map((arquivo) => (
                  <option key={arquivo.id} value={arquivo.id}>
                    {arquivo.nome_arquivo} - {formatarData(arquivo.created_at)}
                  </option>
                ))}
              </select>
            </div>

            {resumo && (
              <div className="stats-grid">
                <div className="stat-card">
                  <FileText className="stat-icon" />
                  <div className="stat-label">Total Empresas</div>
                  <div className="stat-value">{resumo.total_fornecedores}</div>
                </div>

                <div className="stat-card success">
                  <CheckCircle className="stat-icon" />
                  <div className="stat-label">Quitados</div>
                  <div className="stat-value">{resumo.fornecedores_quitados}</div>
                </div>

                <div className="stat-card warning">
                  <AlertCircle className="stat-icon" />
                  <div className="stat-label">Em Aberto</div>
                  <div className="stat-value">{resumo.fornecedores_em_aberto}</div>
                </div>

                <div className="stat-card info">
                  <DollarSign className="stat-icon" />
                  <div className="stat-label">Total a Pagar</div>
                  <div className="stat-value">{formatarMoeda(resumo.valor_total_a_pagar)}</div>
                </div>
              </div>
            )}

            <div className="controls">
              <div className="search-box">
                <Search className="search-icon" />
                <input
                  type="text"
                  placeholder="Nome ou código..."
                  value={busca}
                  onChange={(e) => setBusca(e.target.value)}
                />
              </div>

              <label style={{ fontSize: '0.875rem', color: 'var(--muted)', fontWeight: 500 }}>
                Filtrar por Status
              </label>

              <select
                className="filter-select"
                value={statusFiltro}
                onChange={(e) => setStatusFiltro(e.target.value)}
              >
                <option value="">Todos</option>
                <option value="EM_ABERTO">Em Aberto</option>
                <option value="QUITADO">Quitados</option>
                <option value="ADIANTADO">Adiantados</option>
              </select>

              <div className="export-section">
                <span className="export-label">Exportar para Excel</span>
                <button className="btn btn-secondary" onClick={() => handleExportar('em_aberto')}>
                  <Download size={18} /> Em Aberto
                </button>
                <button className="btn btn-secondary" onClick={() => handleExportar('completo')}>
                  <Download size={18} /> Completo
                </button>
                <button className="btn btn-secondary" onClick={() => handleExportar('divergencias')}>
                  <Download size={18} /> Divergências
                </button>
              </div>
            </div>

            <div className="table-container">
              {fornecedoresFiltrados.length === 0 ? (
                <div className="empty-state">
                  <FileText />
                  <p>Nenhum fornecedor encontrado</p>
                </div>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Código</th>
                      <th>Empresa</th>
                      <th style={{ textAlign: 'right' }}>Total Créditos</th>
                      <th style={{ textAlign: 'right' }}>Total Débitos</th>
                      <th style={{ textAlign: 'right' }}>A Pagar</th>
                      <th style={{ textAlign: 'center' }}>Status</th>
                      <th style={{ textAlign: 'center' }}>NFs Pendentes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fornecedoresFiltrados.map((fornecedor) => (
                      <tr key={fornecedor.id} onClick={() => handleVerDetalhes(fornecedor.id)}>
                        <td>{fornecedor.codigo_conta}</td>
                        <td>{fornecedor.nome_fornecedor}</td>
                        <td style={{ textAlign: 'right' }}>{formatarMoeda(fornecedor.total_credito)}</td>
                        <td style={{ textAlign: 'right' }}>{formatarMoeda(fornecedor.total_debito)}</td>
                        <td style={{ textAlign: 'right', fontWeight: 600 }}>{formatarMoeda(fornecedor.valor_a_pagar)}</td>
                        <td style={{ textAlign: 'center' }}>
                          <span className={`status-badge ${
                            fornecedor.status_pagamento === 'QUITADO' ? 'success' :
                            fornecedor.status_pagamento === 'EM_ABERTO' ? 'warning' : 'info'
                          }`}>
                            {fornecedor.status_pagamento === 'QUITADO' && <CheckCircle size={14} />}
                            {fornecedor.status_pagamento === 'EM_ABERTO' && <AlertCircle size={14} />}
                            {fornecedor.status_pagamento === 'QUITADO' ? 'Quitado' : (fornecedor.status_pagamento || '').replace('_', ' ')}
                          </span>
                        </td>
                        <td style={{ textAlign: 'center' }}>{fornecedor.qtd_nfs_pendentes}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}

        {fornecedorDetalhado && (
          <div className="modal-overlay" onClick={() => setFornecedorDetalhado(null)}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <div>
                  <h2>{fornecedorDetalhado.fornecedor.nome_fornecedor}</h2>
                  <p style={{ color: 'var(--muted)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
                    Conta: {fornecedorDetalhado.fornecedor.codigo_conta} - {fornecedorDetalhado.fornecedor.conta_contabil}
                  </p>
                </div>
                <button className="modal-close" onClick={() => setFornecedorDetalhado(null)}>
                  <X size={18} />
                </button>
              </div>

              <div className="modal-body">
                <div className="info-grid">
                  <div className="info-item">
                    <div className="info-label">Total Créditos</div>
                    <div className="info-value">{formatarMoeda(fornecedorDetalhado.fornecedor.total_credito)}</div>
                  </div>

                  <div className="info-item success">
                    <div className="info-label">Total Débitos</div>
                    <div className="info-value">{formatarMoeda(fornecedorDetalhado.fornecedor.total_debito)}</div>
                  </div>

                  <div className="info-item warning">
                    <div className="info-label">Saldo a Pagar</div>
                    <div className="info-value">{formatarMoeda(fornecedorDetalhado.fornecedor.valor_a_pagar)}</div>
                  </div>
                </div>

                <h3 className="section-title">Créditos Pendentes</h3>

                {fornecedorDetalhado.compras_pendentes.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--muted)' }}>
                    <CheckCircle style={{ margin: '0 auto 0.5rem', opacity: 0.5 }} size={32} />
                    <p>Nenhum crédito pendente</p>
                  </div>
                ) : (
                  fornecedorDetalhado.compras_pendentes.map((compra, idx) => (
                    <div key={idx} className="compra-item">
                      <div className="compra-header">
                        <div className="compra-info">
                          <div className="compra-nf">
                            {compra.numero_nf ? `NF: ${compra.numero_nf}` : 'Sem número de NF'}
                          </div>
                          <div className="compra-data">
                            {formatarData(compra.data_lancamento)}
                          </div>
                        </div>
                        <span className={`compra-status ${compra.status_pagamento}`}>
                          {compra.status_pagamento}
                        </span>
                      </div>

                      <div className="compra-valores">
                        <div className="valor-item">
                          <div className="valor-label">Valor Total</div>
                          <div className="valor-amount">{formatarMoeda(compra.valor_total)}</div>
                        </div>
                        <div className="valor-item">
                          <div className="valor-label">Pago</div>
                          <div className="valor-amount">{formatarMoeda(compra.valor_pago_parcial)}</div>
                        </div>
                        <div className="valor-item">
                          <div className="valor-label">Pendente</div>
                          <div className="valor-amount" style={{ color: '#f59e0b', fontWeight: 700 }}>
                            {formatarMoeda(compra.valor_saldo)}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  )
}

export default App