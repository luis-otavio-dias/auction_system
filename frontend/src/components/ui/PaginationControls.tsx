export default function PaginationControls({ page, hasNext, hasPrevious, onNext, onPrevious }: {
  page: number
  hasNext: boolean
  hasPrevious: boolean
  onNext: () => void
  onPrevious: () => void
}) {
  return (
    <nav className="pagination" aria-label="Paginação">
      <button onClick={onPrevious} disabled={!hasPrevious}>Anterior</button>
      <span className="current-page" aria-current="page">Página {String(page).padStart(2, '0')}</span>
      <button onClick={onNext} disabled={!hasNext}>Próximo</button>
    </nav>
  )
}
