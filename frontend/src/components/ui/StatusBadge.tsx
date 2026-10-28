import type { LotStatus } from '../../types/api'
import { statusLabel } from '../../utils/format'

export default function StatusBadge({ status }: { status: LotStatus }) {
  return <span className={`status-badge status-${status}`}>{statusLabel(status)}</span>
}
