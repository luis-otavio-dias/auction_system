import assert from 'node:assert/strict'

const API_URL = (process.env.E2E_API_URL ?? 'http://127.0.0.1:8002').replace(/\/+$/, '')
const WS_ORIGIN = process.env.E2E_WS_ORIGIN ?? 'http://localhost:5173'
const DEMO_PASSWORD = process.env.DEMO_PASSWORD ?? 'demo-password-123'
const RUN_ID = Date.now().toString(36)
const SNAPSHOT_TIMEOUT_MS = 10000
const SETTLEMENT_TIMEOUT_MS = 45000

const exchanges = []
const completed = []
let activeStep = ''

const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds))

function money(value) {
  return Number(value).toFixed(2)
}

function recordExchange(exchange) {
  exchanges.push(exchange)
  if (exchanges.length > 60) {
    exchanges.shift()
  }
}

function evidence() {
  const recent = exchanges.slice(-6)
  return recent.map(item => `${item.method} ${item.path} -> ${item.status}\n${JSON.stringify(item.response, null, 2)}`).join('\n')
}

async function step(name, run) {
  activeStep = name
  process.stdout.write(`- ${name} ... `)
  try {
    const value = await run()
    process.stdout.write('ok\n')
    completed.push({ name, ok: true })
    return value
  } catch (error) {
    process.stdout.write('FAIL\n')
    completed.push({ name, ok: false })
    const message = error instanceof Error ? error.message : String(error)
    console.error(`\n[${name}] ${message}`)
    console.error(`Evidence:\n${evidence()}\n`)
    throw error
  }
}

class CookieSession {
  constructor(label) {
    this.label = label
    this.cookies = new Map()
  }

  cookieHeader() {
    return [...this.cookies.entries()].map(([name, value]) => `${name}=${value}`).join('; ')
  }

  storeCookies(response) {
    const headers = response.headers
    const setCookies = typeof headers.getSetCookie === 'function' ? headers.getSetCookie() : []
    for (const raw of setCookies) {
      const pair = raw.split(';', 1)[0]
      const separator = pair.indexOf('=')
      if (separator <= 0) {
        continue
      }
      const name = pair.slice(0, separator)
      const value = pair.slice(separator + 1)
      const expired = /max-age=0/i.test(raw) || /expires=thu, 01 jan 1970/i.test(raw)
      if (expired || value === '') {
        this.cookies.delete(name)
      } else {
        this.cookies.set(name, value)
      }
    }
  }

  async request(path, options = {}) {
    const method = options.method ?? 'GET'
    const headers = { Accept: 'application/json' }
    if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json'
    }
    if (options.auth !== false && this.cookies.size > 0) {
      headers.Cookie = this.cookieHeader()
    }
    const response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })
    this.storeCookies(response)
    const text = await response.text()
    let body = null
    if (text !== '') {
      try {
        body = JSON.parse(text)
      } catch {
        body = text
      }
    }
    recordExchange({
      session: this.label,
      method,
      path,
      status: response.status,
      response: body,
    })
    return { status: response.status, body, headers: response.headers }
  }
}

async function expect(response, expected, label) {
  if (response.status !== expected) {
    throw new Error(`${label}: esperado HTTP ${expected}, recebido ${response.status}.`)
  }
  return response.body
}

async function getJson(session, path, expected = 200, options = {}) {
  const response = await session.request(path, options)
  return expect(response, expected, `GET ${path}`)
}

async function postJson(session, path, body, expected = 200, options = {}) {
  const response = await session.request(path, { ...options, method: 'POST', body })
  return { status: response.status, body: await expect(response, expected, `POST ${path}`) }
}

async function login(label, email) {
  const session = new CookieSession(label)
  const response = await session.request('/api/auth/token/', {
    method: 'POST',
    body: { email, password: DEMO_PASSWORD },
  })
  await expect(response, 200, `login ${email}`)
  assert.match(session.cookieHeader(), /access_token=/, `login ${email} sem cookie access_token`)
  return session
}

function assertPage(body, label) {
  assert.equal(typeof body.count, 'number', `${label} sem count`)
  assert.ok(Array.isArray(body.results), `${label} sem results`)
}

function assertMoneyString(value, label) {
  assert.equal(typeof value, 'string', `${label} deve ser string decimal`)
  assert.match(value, /^\d+\.\d{2}$/, `${label} fora do formato decimal`)
}

function assertNoPii(value, label) {
  const serialized = JSON.stringify(value)
  assert.ok(!serialized.includes('@'), `${label} expõe email`)
  assert.ok(!serialized.includes('"bidder_id"'), `${label} expõe bidder_id`)
  assert.ok(!serialized.includes('"user_id"'), `${label} expõe user_id`)
  assert.ok(!serialized.includes('"winner_id"'), `${label} expõe winner_id`)
  assert.ok(!serialized.includes('"email"'), `${label} expõe email`)
}

async function openLotSnapshot(session, lotId) {
  const ticket = await postJson(session, '/api/auth/ws-ticket', undefined, 200)
  assert.equal(typeof ticket.body.ticket, 'string')
  const wsUrl = `${API_URL.replace(/^http/, 'ws')}/ws/lots/${lotId}/?ticket=${encodeURIComponent(ticket.body.ticket)}`
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(wsUrl, { headers: { origin: WS_ORIGIN } })
    let settled = false
    const timer = setTimeout(() => {
      settled = true
      try {
        socket.close()
      } catch {
        undefined
      }
      reject(new Error(`WebSocket sem snapshot em ${SNAPSHOT_TIMEOUT_MS}ms`))
    }, SNAPSHOT_TIMEOUT_MS)
    socket.onmessage = event => {
      if (settled) {
        return
      }
      settled = true
      clearTimeout(timer)
      try {
        resolve(JSON.parse(String(event.data)))
      } catch {
        reject(new Error('WebSocket enviou payload não JSON'))
      }
      socket.close()
    }
    socket.onerror = () => {
      if (!settled) {
        settled = true
        clearTimeout(timer)
        reject(new Error('Falha no handshake WebSocket'))
      }
    }
    socket.onclose = event => {
      if (!settled) {
        settled = true
        clearTimeout(timer)
        reject(new Error(`WebSocket fechado sem snapshot (código ${event.code})`))
      }
    }
  })
}

async function openNotificationStream(session) {
  const ticket = await postJson(session, '/api/auth/ws-ticket', undefined, 200)
  const wsUrl = `${API_URL.replace(/^http/, 'ws')}/ws/notifications/?ticket=${encodeURIComponent(ticket.body.ticket)}`
  const events = []
  const socket = new WebSocket(wsUrl, { headers: { origin: WS_ORIGIN } })
  socket.onmessage = event => {
    try {
      events.push(JSON.parse(String(event.data)))
    } catch {
      undefined
    }
  }
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('WebSocket de notificações sem conexão')), SNAPSHOT_TIMEOUT_MS)
    socket.onopen = () => {
      clearTimeout(timer)
      resolve()
    }
    socket.onerror = () => {
      clearTimeout(timer)
      reject(new Error('Falha no handshake do WebSocket de notificações'))
    }
  })
  return {
    async next(kind, timeoutMs = SNAPSHOT_TIMEOUT_MS) {
      const deadline = Date.now() + timeoutMs
      while (Date.now() < deadline) {
        const index = events.findIndex(item => item.event === kind || item.type === kind)
        if (index >= 0) {
          return events.splice(index, 1)[0]
        }
        await sleep(100)
      }
      throw new Error(`Notificação ${kind} não recebida em ${timeoutMs}ms`)
    },
    close() {
      socket.close()
    },
  }
}

async function waitForWin(session, lotId, lotCode) {
  const deadline = Date.now() + SETTLEMENT_TIMEOUT_MS
  let attempts = 0
  while (Date.now() < deadline) {
    attempts += 1
    await session.request(`/api/lots/${lotId}`)
    const wins = await session.request('/api/me/wins')
    if (wins.status === 200 && Array.isArray(wins.body)) {
      const win = wins.body.find(item => item.lot_code === lotCode)
      if (win !== undefined) {
        return win
      }
    }
    await sleep(2000)
  }
  throw new Error(`Lote ${lotCode} não liquidou em ${SETTLEMENT_TIMEOUT_MS}ms (${attempts} tentativas)`)
}

async function main() {
  console.log(`E2E API: ${API_URL}`)
  console.log(`E2E WS origin: ${WS_ORIGIN}`)
  console.log(`Run: ${RUN_ID}\n`)

  const health = await step('health do backend', async () => {
    const response = await new CookieSession('anon').request('/health/', { auth: false })
    return expect(response, 200, 'health')
  })
  assert.equal(health.status, 'ok')

  await step('login demo rejeita senha incorreta sem criar conta', async () => {
    const anonymous = new CookieSession('anon')
    const response = await anonymous.request('/api/auth/token/', {
      method: 'POST',
      body: { email: 'leiloeiro@demo.com', password: `${DEMO_PASSWORD}-incorreta` },
    })
    assert.equal(response.status, 401)
    assert.equal(anonymous.cookies.size, 0)
  })

  const seller = await step('login demo real do leiloeiro', () => login('seller', 'leiloeiro@demo.com'))
  const cliente1 = await step('login de cliente1', () => login('cliente1', 'cliente1@demo.com'))
  const cliente2 = await step('login de cliente2', () => login('cliente2', 'cliente2@demo.com'))

  const meSeller = await step('GET /api/auth/me/ do leiloeiro', () => getJson(seller, '/api/auth/me/'))
  const me1 = await step('GET /api/auth/me/ de cliente1', () => getJson(cliente1, '/api/auth/me/'))
  const me2 = await step('GET /api/auth/me/ de cliente2', () => getJson(cliente2, '/api/auth/me/'))
  assert.equal(meSeller.role, 'SELLER')
  assert.equal(me1.role, 'BIDDER')
  assert.equal(me2.role, 'BIDDER')
  assert.equal(me1.email, 'cliente1@demo.com')
  assert.equal(me2.email, 'cliente2@demo.com')

  await step('carteira e extrato do leiloeiro', async () => {
    const wallet = await getJson(seller, '/api/wallet')
    assertMoneyString(wallet.balance, 'balance do leiloeiro')
    assertMoneyString(wallet.committed, 'committed do leiloeiro')
    assertMoneyString(wallet.available, 'available do leiloeiro')
    const transactions = await getJson(seller, '/api/wallet/transactions?page=1')
    assertPage(transactions, 'extrato do leiloeiro')
  })

  await step('POST /api/wallet não permite depósito ao leiloeiro', async () => {
    const response = await seller.request('/api/wallet', {
      method: 'POST',
      body: { amount: '10.00', idempotency_key: `e2e-seller-${RUN_ID}` },
    })
    assert.equal(response.status, 405)
  })

  const livePage = await step('GET /api/lots paginado', () => getJson(cliente1, '/api/lots?tab=live&page=1'))
  assertPage(livePage, 'lotes')
  assert.ok(livePage.results.length > 0, 'vitrine ao vivo vazia')
  const firstLot = livePage.results[0]
  assert.equal(typeof firstLot.state_version, 'number')
  assertMoneyString(firstLot.minimum_bid, 'minimum_bid da vitrine')

  await step('GET /api/lots/{id} com posição pessoal', async () => {
    const detail = await getJson(cliente1, `/api/lots/${firstLot.id}`)
    assert.equal(detail.id, firstLot.id)
    assert.equal(typeof detail.server_time, 'string')
    assert.ok(detail.my_position === null || typeof detail.my_position === 'object')
  })

  const walletBefore = await step('GET /api/wallet e extrato de cliente1', async () => {
    const wallet = await getJson(cliente1, '/api/wallet')
    assertMoneyString(wallet.balance, 'balance')
    assertMoneyString(wallet.committed, 'committed')
    assertMoneyString(wallet.available, 'available')
    const transactions = await getJson(cliente1, '/api/wallet/transactions?page=1')
    assertPage(transactions, 'extrato')
    return wallet
  })

  await step('depósito simulado idempotente em cliente1', async () => {
    const amount = '125.50'
    const key = `e2e-deposit-${RUN_ID}`
    const first = await postJson(cliente1, '/api/wallet/deposits', { amount, idempotency_key: key }, 201)
    assertMoneyString(first.body.balance, 'balance após depósito')
    assert.equal(money(Number(walletBefore.balance) + Number(amount)), money(first.body.balance))
    const replayResponse = await cliente1.request('/api/wallet/deposits', {
      method: 'POST',
      body: { amount, idempotency_key: key },
    })
    assert.equal(replayResponse.status, 200)
    assert.equal(replayResponse.headers.get('Idempotent-Replayed'), 'true')
    assert.equal(replayResponse.body.balance, first.body.balance)
  })

  const catalogItem = await step('busca de item no catálogo do leiloeiro', async () => {
    const search = await getJson(seller, '/api/catalog/search?q=6565&limit=5')
    assert.equal(typeof search.count, 'number')
    assert.ok(Array.isArray(search.results))
    assert.ok(search.results.length > 0, 'catálogo em cache sem item 6565')
    return search.results[0]
  })

  const now = Date.now()
  const mainLot = await step('criação de lote pelo leiloeiro', async () => {
    const response = await postJson(seller, '/api/lots', {
      catalog_item_id: catalogItem.id,
      starts_at: new Date(now - 60_000).toISOString(),
      ends_at: new Date(now + 3_600_000).toISOString(),
      starting_bid: '100.00',
      min_increment: '10.00',
    }, 201)
    const lot = response.body
    assert.equal(lot.status, 'live')
    assertMoneyString(lot.starting_bid, 'starting_bid')
    assertMoneyString(lot.minimum_bid, 'minimum_bid')
    return lot
  })

  const clientBidId = crypto.randomUUID()
  await step('cliente1 envia o primeiro lance exato', async () => {
    const bid = await postJson(cliente1, `/api/lots/${mainLot.id}/bids`, {
      amount: '100.00',
      client_bid_id: clientBidId,
    }, 201)
    assert.equal(bid.body.sequence, 1)
    assert.equal(bid.body.amount, '100.00')
    assert.equal(typeof bid.body.bidder_alias, 'string')
    const detail = await getJson(cliente1, `/api/lots/${mainLot.id}`)
    assert.equal(detail.my_position.status, 'leading')
    assert.equal(detail.my_position.is_leading, true)
    assert.equal(detail.my_position.last_amount, '100.00')
    assert.equal(detail.minimum_bid, '110.00')
  })

  await step('server_time atualizado mantém a estabilidade do countdown', async () => {
    const first = await getJson(cliente1, `/api/lots/${mainLot.id}`)
    await sleep(1200)
    const second = await getJson(cliente1, `/api/lots/${mainLot.id}`)
    const firstRemaining = new Date(first.ends_at).getTime() - new Date(first.server_time).getTime()
    const secondRemaining = new Date(second.ends_at).getTime() - new Date(second.server_time).getTime()
    assert.ok(Number.isFinite(firstRemaining), 'server_time inicial inválido')
    assert.ok(Number.isFinite(secondRemaining), 'server_time atualizado inválido')
    assert.ok(
      Math.abs(firstRemaining - secondRemaining) <= 1500,
      `countdown derivou ${firstRemaining - secondRemaining}ms entre leituras`,
    )
  })

  const notificationStream = await step('WebSocket de notificações do cliente1', () => openNotificationStream(cliente1))

  await step('cliente2 cobre com o próximo valor exato', async () => {
    const bid = await postJson(cliente2, `/api/lots/${mainLot.id}/bids`, {
      amount: '110.00',
      client_bid_id: crypto.randomUUID(),
    }, 201)
    assert.equal(bid.body.sequence, 2)
    assert.equal(bid.body.amount, '110.00')
    const detail = await getJson(cliente1, `/api/lots/${mainLot.id}`)
    assert.equal(detail.my_position.status, 'outbid')
    assert.equal(detail.my_position.is_leading, false)
    assert.equal(detail.my_position.last_amount, '100.00')
    assert.equal(detail.minimum_bid, '120.00')
    const wallet = await getJson(cliente1, '/api/wallet')
    assert.equal(wallet.committed, '0.00', 'cliente1 deveria ter a reserva liberada')
  })

  await step('notificação user.outbid traz lot_id do lote', async () => {
    const notification = await notificationStream.next('user.outbid')
    assert.equal(notification.lot_id, mainLot.id)
    assert.equal(notification.lot_code, mainLot.code)
    notificationStream.close()
  })

  await step('GET /api/me/bids identifica o lote de cada lance', async () => {
    const myBids = await getJson(cliente2, '/api/me/bids?page=1')
    assertPage(myBids, 'meus lances')
    const bid = myBids.results.find(item => item.lot_id === mainLot.id)
    assert.ok(bid !== undefined, 'lance do cliente2 não referencia o lote')
    assert.equal(bid.lot_code, mainLot.code)
    assert.equal(bid.lot_title, mainLot.title)
    assertMoneyString(bid.amount, 'amount do meu lance')
  })

  await step('repetição idempotente do mesmo client_bid_id', async () => {
    const walletBeforeRetry = await getJson(cliente1, '/api/wallet')
    const historyBefore = await getJson(cliente1, '/api/wallet/transactions?page=1')
    const replayResponse = await cliente1.request(`/api/lots/${mainLot.id}/bids`, {
      method: 'POST',
      body: { amount: '100.00', client_bid_id: clientBidId },
    })
    assert.equal(replayResponse.status, 200)
    assert.equal(replayResponse.headers.get('Idempotent-Replayed'), 'true')
    const replay = { body: replayResponse.body }
    assert.equal(replay.body.sequence, 1)
    assert.equal(replay.body.amount, '100.00')
    const bids = await getJson(cliente1, `/api/lots/${mainLot.id}/bids?page=1`)
    assertPage(bids, 'histórico')
    assert.equal(bids.count, 2, 'repetição criou lance duplicado')
    const walletAfterRetry = await getJson(cliente1, '/api/wallet')
    const historyAfter = await getJson(cliente1, '/api/wallet/transactions?page=1')
    assert.equal(walletAfterRetry.balance, walletBeforeRetry.balance)
    assert.equal(walletAfterRetry.committed, walletBeforeRetry.committed)
    assert.equal(historyAfter.count, historyBefore.count, 'repetição criou lançamento duplicado')
  })

  await step('erro de valor incorreto sem criar lance', async () => {
    const response = await cliente1.request(`/api/lots/${mainLot.id}/bids`, {
      method: 'POST',
      body: { amount: '121.00', client_bid_id: crypto.randomUUID() },
    })
    assert.equal(response.status, 422)
    assert.equal(response.body.code, 'BID_AMOUNT_MISMATCH')
    const bids = await getJson(cliente1, `/api/lots/${mainLot.id}/bids?page=1`)
    assert.equal(bids.count, 2)
  })

  const fundsLot = await step('criação de lote para saldo insuficiente', async () => {
    const response = await postJson(seller, '/api/lots', {
      catalog_item_id: catalogItem.id,
      starts_at: new Date(now - 60_000).toISOString(),
      ends_at: new Date(now + 3_600_000).toISOString(),
      starting_bid: '2000000.00',
      min_increment: '1.00',
    }, 201)
    return response.body
  })

  await step('saldo insuficiente retorna INSUFFICIENT_FUNDS', async () => {
    const response = await cliente1.request(`/api/lots/${fundsLot.id}/bids`, {
      method: 'POST',
      body: { amount: '2000000.00', client_bid_id: crypto.randomUUID() },
    })
    assert.equal(response.status, 409)
    assert.equal(response.body.code, 'INSUFFICIENT_FUNDS')
    assertMoneyString(response.body.available, 'available do erro de saldo')
    assertMoneyString(response.body.minimum_bid, 'minimum_bid do erro de saldo')
    await postJson(seller, `/api/lots/${fundsLot.id}/cancel`, { reason: 'smoke e2e' }, 200)
  })

  const antiNow = Date.now()
  const antiLot = await step('criação de lote com encerramento em menos de 2 minutos', async () => {
    const response = await postJson(seller, '/api/lots', {
      catalog_item_id: catalogItem.id,
      starts_at: new Date(antiNow - 60_000).toISOString(),
      ends_at: new Date(antiNow + 45_000).toISOString(),
      starting_bid: '200.00',
      min_increment: '10.00',
    }, 201)
    return response.body
  })

  let antiEndsAt = antiLot.ends_at
  await step('anti-sniping estende o lote para now+2min', async () => {
    const originalEndsAt = new Date(antiLot.ends_at).getTime()
    await postJson(cliente1, `/api/lots/${antiLot.id}/bids`, {
      amount: '200.00',
      client_bid_id: crypto.randomUUID(),
    }, 201)
    const detail = await getJson(cliente1, `/api/lots/${antiLot.id}`)
    const extendedEndsAt = new Date(detail.ends_at).getTime()
    const remaining = extendedEndsAt - Date.now()
    assert.ok(extendedEndsAt > originalEndsAt, 'ends_at não foi estendido')
    assert.equal(detail.extension_count, 1)
    assert.ok(remaining >= 110_000 && remaining <= 135_000, `extensão inesperada: ${remaining}ms`)
    antiEndsAt = detail.ends_at
  })

  await step('cliente2 cobre o lote anti-sniping', async () => {
    const bid = await postJson(cliente2, `/api/lots/${antiLot.id}/bids`, {
      amount: '210.00',
      client_bid_id: crypto.randomUUID(),
    }, 201)
    assert.equal(bid.body.sequence, 2)
    const detail = await getJson(cliente2, `/api/lots/${antiLot.id}`)
    assert.equal(detail.my_position.status, 'leading')
    assert.equal(detail.current_bid, '210.00')
    assert.ok(detail.extension_count >= 1)
    antiEndsAt = detail.ends_at
  })

  await step('GET /api/lots/{id}/bids sem PII', async () => {
    const anonymous = new CookieSession('anon')
    const bids = await getJson(anonymous, `/api/lots/${antiLot.id}/bids?page=1`, 200, { auth: false })
    assertPage(bids, 'histórico público')
    assert.equal(bids.count, 2)
    for (const bid of bids.results) {
      assert.deepEqual(Object.keys(bid).sort(), ['amount', 'bidder_alias', 'lot_code', 'lot_id', 'lot_title', 'placed_at', 'sequence'])
      assert.equal(bid.lot_id, antiLot.id)
      assert.equal(bid.lot_code, antiLot.code)
    }
    assertNoPii(bids, 'histórico público')
  })

  await step('GET /api/seller/lots e /api/seller/summary', async () => {
    const lots = await getJson(seller, '/api/seller/lots?page=1')
    assertPage(lots, 'lotes do leiloeiro')
    assert.ok(lots.results.some(lot => lot.id === mainLot.id))
    assert.ok(lots.results.some(lot => lot.id === antiLot.id))
    const summary = await getJson(seller, '/api/seller/summary')
    assertMoneyString(summary.total_received, 'total_received')
    assert.equal(typeof summary.settled_count, 'number')
    assert.equal(typeof summary.unsold_count, 'number')
    assert.ok(Array.isArray(summary.results_by_lot), 'resumo sem resultado por lote')
    assert.ok(Array.isArray(summary.unsold_lots), 'resumo sem lotes não arrematados')
    assert.ok(Array.isArray(summary.blocked_lots))
  })

  await step('WebSocket da sala entrega snapshot', async () => {
    const snapshot = await openLotSnapshot(cliente1, mainLot.id)
    assert.equal(snapshot.event, 'lot.snapshot')
    assert.equal(snapshot.lot_id, mainLot.id)
    assert.equal(typeof snapshot.state_version, 'number')
    assert.equal(typeof snapshot.minimum_bid, 'string')
    assert.equal(snapshot.my_position.status, 'outbid')
  })

  const waitMs = Math.max(0, new Date(antiEndsAt).getTime() - Date.now() + 5000)
  console.log(`- aguardando liquidação do lote ${antiLot.code} (~${Math.ceil(waitMs / 1000)}s) ...`)
  await sleep(waitMs)

  const win = await step('liquidação e GET /api/me/wins de cliente2', () =>
    waitForWin(cliente2, antiLot.id, antiLot.code),
  )
  assert.equal(win.final_price, '210.00')
  assert.equal(typeof win.receipt_token, 'string')
  assert.equal(typeof win.title, 'string')
  assert.equal(typeof win.issued_at, 'string')
  assert.equal(typeof win.share_url, 'string')
  assert.ok(win.share_url.endsWith(`/comprovantes/${win.receipt_token}`), 'share_url do arremate diverge do token')

  await step('GET /api/receipts/{token} público', async () => {
    const anonymous = new CookieSession('anon')
    const receipt = await getJson(anonymous, `/api/receipts/${win.receipt_token}`, 200, { auth: false })
    assert.equal(receipt.token, win.receipt_token)
    assert.equal(receipt.lot_code, antiLot.code)
    assert.equal(receipt.final_price, '210.00')
    assert.equal(receipt.winner_alias, me2.public_alias)
    assert.equal(typeof receipt.audit_head, 'string')
    assertNoPii(receipt)
  })

  await step('GET /api/receipts/{token}/verify público', async () => {
    const anonymous = new CookieSession('anon')
    const verification = await getJson(anonymous, `/api/receipts/${win.receipt_token}/verify`, 200, { auth: false })
    assert.equal(verification.receipt_valid, true)
    assert.equal(verification.history_valid, true)
    assert.equal(verification.head_matches, true)
    assert.equal(verification.bid_count, 2)
  })

  await step('GET /api/lots/{id}/audit público', async () => {
    const anonymous = new CookieSession('anon')
    const audit = await getJson(anonymous, `/api/lots/${antiLot.id}/audit`, 200, { auth: false })
    assert.equal(audit.valid, true)
    assert.equal(audit.bid_count, 2)
    assert.equal(audit.failures.length, 0)
    assert.equal(typeof audit.head_hash, 'string')
    assert.ok(audit.limitations.length > 0)
    assertNoPii(audit)
  })

  await step('resumo do leiloeiro reflete a liquidação por lote', async () => {
    const summary = await getJson(seller, '/api/seller/summary')
    assert.ok(Number(summary.total_received) >= 210)
    assert.ok(summary.settled_count >= 1)
    const result = summary.results_by_lot.find(item => item.lot_id === antiLot.id)
    assert.ok(result !== undefined, 'resultado por lote ausente após liquidação')
    assert.equal(result.code, antiLot.code)
    assert.equal(result.title, antiLot.title)
    assertMoneyString(result.final_price, 'final_price do resultado por lote')
    assert.equal(result.winner_alias, me2.public_alias)
    assert.equal(typeof result.settled_at, 'string')
    const lots = await getJson(seller, '/api/seller/lots?page=1')
    const settled = lots.results.find(lot => lot.id === antiLot.id)
    assert.ok(settled !== undefined)
    assert.equal(settled.status, 'ended')
  })

  const failed = completed.filter(item => !item.ok)
  console.log(`\nE2E concluído: ${completed.length - failed.length}/${completed.length} etapas ok.`)
  console.log(`Lote principal: ${mainLot.id} (${mainLot.code})`)
  console.log(`Lote liquidado: ${antiLot.id} (${antiLot.code}) com recibo ${win.receipt_token}`)
  if (failed.length > 0) {
    process.exitCode = 1
  }
}

main().catch(error => {
  console.error(`\nFalha na etapa "${activeStep}": ${error instanceof Error ? error.message : String(error)}`)
  process.exitCode = 1
})
