import { useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Announcement from '../Announcement'
import SiteFooter from './SiteFooter'
import SiteHeader from './SiteHeader'

export default function SiteLayout() {
  const location = useLocation()
  useEffect(() => {
    if (location.hash === '') {
      window.scrollTo(0, 0)
      return
    }
    const target = document.getElementById(location.hash.slice(1))
    target?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [location.pathname, location.hash])
  return (
    <div className="site-shell">
      <a className="skip-link" href="#conteudo">Ir para o conteúdo</a>
      <Announcement />
      <SiteHeader />
      <main id="conteudo">
        <Outlet />
      </main>
      <SiteFooter />
    </div>
  )
}
