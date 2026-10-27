import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import Icon from './Icon'

export default function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const dialog = ref.current!
    dialog.showModal()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = previousOverflow; dialog.close() }
  }, [])
  return <dialog ref={ref} className="modal" aria-label={title} onCancel={onClose} onClick={event => { if (event.target === event.currentTarget) onClose() }}>
    <button className="icon-button modal-close" onClick={onClose} aria-label="Fechar"><Icon name="close" /></button>
    {children}
  </dialog>
}
