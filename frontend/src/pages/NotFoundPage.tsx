import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="container page-section">
      <div className="empty-state">
        <p className="eyebrow gold">404</p>
        <h2>Página não encontrada.</h2>
        <p>O endereço acessado não existe ou o lote foi removido da vitrine.</p>
        <Link className="text-link" to="/">Voltar para a vitrine <span aria-hidden="true">→</span></Link>
      </div>
    </div>
  )
}
