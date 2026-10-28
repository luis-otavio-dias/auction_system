import Icon from './Icon'

export default function Toast({ message, title = 'Lance Registrado', onDismiss }: { message: string; title?: string; onDismiss: () => void }) {
  return <div className="toast" role="status"><span className="live-dot" /><div><strong>{title}</strong><p>{message}</p></div><button className="icon-button" aria-label="Dispensar aviso" onClick={onDismiss}><Icon name="close" /></button></div>
}
