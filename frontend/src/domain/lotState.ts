import type { LotDetail, LotEvent, LotSnapshot } from '../types/api'

export interface SnapshotDecision {
  accept: boolean
  gap: boolean
  stale: boolean
}

export type LotStreamEvent = Exclude<LotEvent, { type: 'lot.snapshot' }>

export function evaluateSnapshot(currentVersion: number, incomingVersion: number): SnapshotDecision {
  if (incomingVersion < currentVersion) {
    return { accept: false, gap: false, stale: true }
  }
  if (incomingVersion === currentVersion) {
    return { accept: incomingVersion === 0, gap: false, stale: !(incomingVersion === 0) }
  }
  return {
    accept: true,
    gap: currentVersion > 0 && incomingVersion > currentVersion + 1,
    stale: false,
  }
}

export function evaluateEvent(currentVersion: number, incomingVersion: number): SnapshotDecision {
  if (incomingVersion <= currentVersion) {
    return { accept: false, gap: false, stale: true }
  }
  if (currentVersion > 0 && incomingVersion > currentVersion + 1) {
    return { accept: false, gap: true, stale: false }
  }
  return { accept: true, gap: false, stale: false }
}

export function mergeLotSnapshot(lot: LotDetail, snapshot: LotSnapshot): LotDetail {
  return {
    ...lot,
    code: snapshot.code || lot.code,
    title: snapshot.title || lot.title,
    status: snapshot.status,
    current_bid: snapshot.current_bid,
    minimum_bid: snapshot.minimum_bid,
    ends_at: snapshot.ends_at || lot.ends_at,
    bids_count: snapshot.bids_count,
    state_version: snapshot.state_version,
    server_time: snapshot.server_time || lot.server_time,
    my_position: snapshot.my_position ?? lot.my_position,
  }
}

export function mergeLotEvent(lot: LotDetail, event: LotStreamEvent): LotDetail {
  if (event.type === 'bid.accepted') {
    const currentBid = event.current_bid ?? lot.current_bid
    const minimumBid =
      event.minimum_bid
      ?? (currentBid !== null ? (Number(currentBid) + Number(lot.min_increment)).toFixed(2) : lot.minimum_bid)
    return {
      ...lot,
      current_bid: currentBid,
      minimum_bid: minimumBid,
      bids_count: event.bids_count ?? lot.bids_count,
      ends_at: event.ends_at ?? lot.ends_at,
      state_version: event.state_version,
    }
  }
  if (event.type === 'lot.extended') {
    return {
      ...lot,
      ends_at: event.ends_at ?? lot.ends_at,
      server_time: event.server_time ?? lot.server_time,
      state_version: event.state_version,
    }
  }
  if (event.type === 'lot.closed') {
    return {
      ...lot,
      status: 'ended',
      current_bid: event.final_price ?? lot.current_bid,
      state_version: event.state_version,
    }
  }
  return {
    ...lot,
    status: 'cancelled',
    state_version: event.state_version,
  }
}
