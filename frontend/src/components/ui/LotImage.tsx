import { useState } from 'react'

export default function LotImage({ src, alt, className = 'lot-artwork' }: { src: string; alt: string; className?: string }) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null)
  const failed = src === '' || failedSrc === src
  return (
    <div className={className}>
      {failed
        ? <div className="image-placeholder">Sem imagem disponível</div>
        : <img src={src} alt={alt} loading="lazy" width="800" height="600" onError={() => setFailedSrc(src)} />}
    </div>
  )
}
