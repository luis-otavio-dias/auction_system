export type IconName =
  | 'search'
  | 'bell'
  | 'tune'
  | 'close'
  | 'menu'
  | 'sun'
  | 'moon'
  | 'wallet'
  | 'gavel'
  | 'check'
  | 'alert'
  | 'copy'
  | 'logout'
  | 'user'
  | 'arrow-right'
  | 'shield'
  | 'clock'
  | 'receipt'
  | 'external'

export default function Icon({ name }: { name: IconName }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {name === 'search' ? <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4.5 4.5" /></> : null}
      {name === 'bell' ? <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" /></> : null}
      {name === 'tune' ? <><path d="M4 6h16M4 12h16M4 18h16" /><path d="M8 4v4M16 10v4M10 16v4" /></> : null}
      {name === 'menu' ? <path d="M3 6h18M3 12h18M3 18h18" /> : null}
      {name === 'close' ? <path d="m6 6 12 12M18 6 6 18" /> : null}
      {name === 'sun' ? <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" /></> : null}
      {name === 'moon' ? <path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5 8.5 8.5 0 1 0 20.5 14.5Z" /> : null}
      {name === 'wallet' ? <><path d="M4 7h15a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a2 2 0 0 1 2-2h12" /><path d="M16 13h1.5" /></> : null}
      {name === 'gavel' ? <><path d="m14 4 6 6M17 7l-7 7M4 20l7-7M12 4l-8 8M9 7l8 8" /></> : null}
      {name === 'check' ? <path d="m4 12 5 5L20 6" /> : null}
      {name === 'alert' ? <><path d="M12 3 2 21h20L12 3Z" /><path d="M12 9v5M12 17h.01" /></> : null}
      {name === 'copy' ? <><rect x="8" y="8" width="12" height="12" rx="1" /><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3" /></> : null}
      {name === 'logout' ? <><path d="M9 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h4" /><path d="m15 8 5 4-5 4M20 12H9" /></> : null}
      {name === 'user' ? <><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 3.5-7 8-7s8 3 8 7" /></> : null}
      {name === 'arrow-right' ? <path d="M4 12h16m-6-6 6 6-6 6" /> : null}
      {name === 'shield' ? <><path d="M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6l-7-3Z" /><path d="m9 12 2 2 4-4" /></> : null}
      {name === 'clock' ? <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></> : null}
      {name === 'receipt' ? <><path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z" /><path d="M9 8h6M9 12h6M9 16h3" /></> : null}
      {name === 'external' ? <><path d="M14 4h6v6M20 4 10 14" /><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></> : null}
    </svg>
  )
}
