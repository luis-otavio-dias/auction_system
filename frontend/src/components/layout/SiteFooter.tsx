import { Link } from 'react-router-dom'

export default function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="container footer-inner">
        <div>
          <p className="brand footer-brand">Leilões</p>
          <p>Plataforma demonstrativa com lances auditáveis e liquidação registrada.</p>
        </div>
        <div className="footer-links">
          <Link to="/">Vitrine</Link>
          <Link to="/carteira">Carteira</Link>
          <Link to="/meus-arremates">Meus arremates</Link>
        </div>
      </div>
    </footer>
  )
}
