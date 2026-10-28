import { useState } from 'react'
import { Link } from 'react-router-dom'
import Icon from '../Icon'
import { useAuth } from '../../context/auth-context'
import { useNotifications } from '../../context/notifications-context'

export default function NotificationBell() {
  const { user } = useAuth()
  const { notifications, unread, connection, markAllRead, clear } = useNotifications()
  const [open, setOpen] = useState(false)
  const toggle = () => {
    setOpen(current => {
      if (!current) {
        markAllRead()
      }
      return !current
    })
  }
  return (
    <div className="notification-wrap">
      <button
        className="icon-button notifications"
        aria-label={unread > 0 ? `Notificações, ${unread} não lidas` : 'Notificações'}
        aria-expanded={open}
        onClick={toggle}
      >
        <Icon name="bell" />
        {unread > 0 && <i aria-hidden="true" />}
      </button>
      {open && (
        <div className="notification-panel" role="dialog" aria-label="Notificações">
          <div className="notification-head">
            <div>
              <p className="eyebrow">Notificações</p>
              <span className={`connection-dot connection-${connection}`} aria-hidden="true" />
            </div>
            {notifications.length > 0 && <button className="text-button" onClick={clear}>Limpar</button>}
          </div>
          {user === null
            ? <p className="notification-empty">Entre na sua conta para acompanhar lances e arremates.</p>
            : notifications.length === 0
              ? <p className="notification-empty">Nenhuma notificação por enquanto.</p>
              : (
                <ul>
                  {notifications.map(item => (
                    <li key={item.id}>
                      {item.href && item.href.startsWith('http')
                        ? <a href={item.href} target="_blank" rel="noreferrer" onClick={() => setOpen(false)}>{item.title}<span>{item.message}</span></a>
                        : item.href
                          ? <Link to={item.href} onClick={() => setOpen(false)}>{item.title}<span>{item.message}</span></Link>
                          : <div>{item.title}<span>{item.message}</span></div>}
                      {item.lot_href && item.lot_href !== item.href && (
                        <Link className="cell-note" to={item.lot_href} onClick={() => setOpen(false)}>Ver lote</Link>
                      )}
                      {item.receipt_href && item.receipt_href !== item.href && (
                        item.receipt_href.startsWith('http')
                          ? <a className="cell-note" href={item.receipt_href} target="_blank" rel="noreferrer" onClick={() => setOpen(false)}>Comprovante</a>
                          : <Link className="cell-note" to={item.receipt_href} onClick={() => setOpen(false)}>Comprovante</Link>
                      )}
                    </li>
                  ))}
                </ul>
              )}
        </div>
      )}
    </div>
  )
}
