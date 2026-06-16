/** Fetch helpers for all dashboard API endpoints. */

const BASE = '/api'

async function fetchJSON(url, options) {
  const res = await fetch(url, options)
  if (!res.ok) throw new Error(`API error ${res.status}: ${url}`)
  // Some endpoints return 200 with no JSON body (e.g. DELETE → {ok:true})
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) return res.json()
  return null
}

/**
 * @param {{ team?: string, status?: 'needs_review'|'blocked'|'all', limit?: number, offset?: number, roles?: string[], unreviewed?: boolean }} opts
 * @returns {Promise<{results: Array, total: number}>}
 */
export function getPRs({ team, status = 'needs_review', limit = 50, offset = 0, roles = [], unreviewed = false } = {}) {
  const params = new URLSearchParams({ status, limit, offset })
  if (team) params.set('team', team)
  if (roles.length > 0) params.set('roles', roles.join(','))
  if (unreviewed) params.set('unreviewed', 'true')
  return fetchJSON(`${BASE}/prs?${params}`)
}

/**
 * @param {{ roles?: string[], unreviewed?: boolean }} opts
 * @returns {Promise<Array<{name: string, needs_review_count: number, blocked_count: number}>>}
 */
export function getTeams({ roles = [], unreviewed = false } = {}) {
  const params = new URLSearchParams()
  if (roles.length > 0) params.set('roles', roles.join(','))
  if (unreviewed) params.set('unreviewed', 'true')
  const qs = params.toString()
  return fetchJSON(`${BASE}/teams${qs ? '?' + qs : ''}`)
}

/** @returns {Promise<{total_open: number, needs_review: number, blocked: number, by_team: Array}>} */
export function getStats() {
  return fetchJSON(`${BASE}/stats`)
}

/** @param {number} number */
export function getPR(number) {
  return fetchJSON(`${BASE}/prs/${number}`)
}

/**
 * @param {'30d'|'90d'|'1y'|'3y'} period
 * @param {string|null} team
 */
export function getScoreboard(period, team = null) {
  const params = new URLSearchParams({ period })
  if (team) params.set('team', team)
  return fetchJSON(`${BASE}/scoreboard?${params}`)
}

/**
 * Fetch exactly the given open PRs by number (for the starred filter).
 * Merged/closed PRs in the list are silently omitted by the backend.
 * @param {number[]} numbers
 */
export function getStarredPRs(numbers) {
  const params = new URLSearchParams({ numbers: numbers.join(',') })
  return fetchJSON(`${BASE}/prs?${params}`)
}

// ── Identity ──────────────────────────────────────────────────────────────────

/** @returns {Promise<{authenticated: boolean, login: string|null, avatar_url: string|null}>} */
export function getMe() {
  return fetchJSON(`${BASE}/me`)
}

// ── Preferences ───────────────────────────────────────────────────────────────

/** @returns {Promise<{starred: number[], ignored: number[], notes: Record<string,string>}>} */
export function getPrefs() {
  return fetchJSON(`${BASE}/prefs`)
}

/** @param {number} n */
export function starPR(n) {
  return fetchJSON(`${BASE}/prefs/star/${n}`, { method: 'PUT' })
}

/** @param {number} n */
export function unstarPR(n) {
  return fetchJSON(`${BASE}/prefs/star/${n}`, { method: 'DELETE' })
}

/** @param {number} n */
export function ignorePR(n) {
  return fetchJSON(`${BASE}/prefs/ignore/${n}`, { method: 'PUT' })
}

/** @param {number} n */
export function unignorePR(n) {
  return fetchJSON(`${BASE}/prefs/ignore/${n}`, { method: 'DELETE' })
}

/**
 * @param {number} n
 * @param {string} text
 */
export function setNote(n, text) {
  return fetchJSON(`${BASE}/prefs/note/${n}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
}

/** @param {number} n */
export function deleteNote(n) {
  return fetchJSON(`${BASE}/prefs/note/${n}`, { method: 'DELETE' })
}

/**
 * Migrate an srdb-preferences localStorage blob to the server.
 * @param {object} blob
 */
export function migrateLocalStorage(blob) {
  return fetchJSON(`${BASE}/prefs/migrate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(blob),
  })
}

// ── Utilities ─────────────────────────────────────────────────────────────────

/**
 * Format an ISO date string as "N days" waiting duration.
 * @param {string|null} isoDate
 */
export function daysWaiting(isoDate) {
  if (!isoDate) return '?'
  const ms = Date.now() - new Date(isoDate).getTime()
  const days = Math.floor(ms / (1000 * 60 * 60 * 24))
  if (days === 0) return 'today'
  return days === 1 ? '1 day' : `${days} days`
}
