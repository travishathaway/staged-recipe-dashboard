/** Fetch helpers for all dashboard API endpoints. */

const BASE = '/api'

async function fetchJSON(url) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API error ${res.status}: ${url}`)
  return res.json()
}

/**
 * @param {{ team?: string, status?: 'needs_review'|'blocked'|'all', limit?: number, offset?: number }} opts
 */
export function getPRs({ team, status = 'needs_review', limit = 50, offset = 0 } = {}) {
  const params = new URLSearchParams({ status, limit, offset })
  if (team) params.set('team', team)
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
