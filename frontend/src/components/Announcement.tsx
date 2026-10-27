export default function Announcement() {
  return (
    <aside className="announcement">
      <div>
        <span className="announcement-title">Nenhum leilão em andamento</span>
        <span className="announcement-detail">• <span>Informações do leilão indisponíveis</span></span>
      </div>
      <div className="exchange">
        <span className="next-hammer">Próximo encerramento: <strong>—</strong></span>
        <span className="currency">Moeda: —</span>
      </div>
    </aside>
  )
}
