/** Fetch helpers for all dashboard API endpoints. */

const BASE = '/api'

async function fetchJSON(url) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API error ${res.status}: ${url}`)
  return res.json()
}

/**
 * @param {{ team?: string, status?: 'needs_review'|'blocked'|'all', limit?: number, offset?: number, username?: string|null, roles?: string[], unreviewed?: boolean }} opts
 * @returns {Promise<{results: Array, total: number}>}
 */
export function getPRs({ team, status = 'needs_review', limit = 50, offset = 0, username = null, roles = [], unreviewed = false } = {}) {
  const params = new URLSearchParams({ status, limit, offset })
  if (team) params.set('team', team)
  if (username) params.set('username', username)
  if (roles.length > 0) params.set('roles', roles.join(','))
  if (unreviewed) params.set('unreviewed', 'true')
  return fetchJSON(`${BASE}/prs?${params}`)
}

/** @returns {Promise<Array<{name: string, needs_review_count: number, blocked_count: number}>>} */
export function getTeams() {
  return fetchJSON(`${BASE}/teams`)
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
