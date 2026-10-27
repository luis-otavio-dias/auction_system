import Icon from './Icon'

export default function Toast({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  return <div className="toast" role="status"><span className="live-dot" /><div><strong>Lance Registrado</strong><p>{message}</p></div><button className="icon-button" aria-label="Dispensar aviso" onClick={onDismiss}><Icon name="close" /></button></div>
}
