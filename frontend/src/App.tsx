import { BrowserRouter, Route, Routes } from 'react-router-dom'
import RequireAuth from './components/RequireAuth'
import SiteLayout from './components/layout/SiteLayout'
import AuthProvider from './context/AuthProvider'
import NotificationsProvider from './context/NotificationsProvider'
import { ThemeProvider } from './context/ThemeProvider'
import ToastProvider from './context/ToastProvider'
import AuditPage from './pages/Audit/AuditPage'
import LoginPage from './pages/Auth/LoginPage'
import RegisterPage from './pages/Auth/RegisterPage'
import CatalogPage from './pages/Catalog/CatalogPage'
import NotFoundPage from './pages/NotFoundPage'
import ReceiptPage from './pages/Receipt/ReceiptPage'
import LotRoomPage from './pages/Room/LotRoomPage'
import SellerPage from './pages/Seller/SellerPage'
import WalletPage from './pages/Wallet/WalletPage'
import WinsPage from './pages/Wins/WinsPage'
import './pages/Home/Home.css'
import './styles/app.css'

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          <ToastProvider>
            <NotificationsProvider>
              <Routes>
                <Route element={<SiteLayout />}>
                  <Route index element={<CatalogPage />} />
                  <Route path="lotes/:id" element={<LotRoomPage />} />
                  <Route path="lotes/:id/auditoria" element={<AuditPage />} />
                  <Route path="comprovantes/:token" element={<ReceiptPage />} />
                  <Route path="login" element={<LoginPage />} />
                  <Route path="cadastro" element={<RegisterPage />} />
                  <Route path="carteira" element={<RequireAuth><WalletPage /></RequireAuth>} />
                  <Route path="meus-arremates" element={<RequireAuth><WinsPage /></RequireAuth>} />
                  <Route path="painel" element={<RequireAuth roles={['SELLER']}><SellerPage /></RequireAuth>} />
                  <Route path="*" element={<NotFoundPage />} />
                </Route>
              </Routes>
            </NotificationsProvider>
          </ToastProvider>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  )
}
