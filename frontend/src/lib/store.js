/**
 * API-backed user preferences store.
 *
 * Replaces the localStorage-based store. On module load, fetches identity
 * (GET /api/me) and preferences (GET /api/prefs) from the server.
 *
 * Public API (backward-compatible where possible):
 *   authUser   — readable: { authenticated, login, avatar_url }
 *   preferences — store with { starred: Set<number>, ignored: Set<number>, notes: Map<number,string> }
 *   githubUsername — derived: login string or null (for backward compat)
 *   refreshPrefs() — re-fetch prefs from server (used after migration)
 *
 * Mutation methods on preferences:
 *   starPR(number), unstarPR(number)
 *   ignorePR(number), unignorePR(number)
 *   setNote(number, text), deleteNote(number)
 *   clearStarred(), clearOrphanedNotes()  ← no-ops or simple server calls
 */

import { writable, derived, get } from 'svelte/store'
import {
  getMe,
  getPrefs,
  starPR as apiStarPR,
  unstarPR as apiUnstarPR,
  ignorePR as apiIgnorePR,
  unignorePR as apiUnignorePR,
  setNote as apiSetNote,
  deleteNote as apiDeleteNote,
} from './api.js'

// ── Auth user store ────────────────────────────────────────────────────────────

const _authUser = writable({ authenticated: false, login: null, avatar_url: null })
export const authUser = { subscribe: _authUser.subscribe }

// ── Preferences store ──────────────────────────────────────────────────────────

/**
 * Internal shape:
 * {
 *   starred: number[],   // PR numbers
 *   ignored: number[],   // PR numbers
 *   notes: { [prNumber: string]: string },
 * }
 */
const _defaultPrefs = { starred: [], ignored: [], notes: {} }
const _prefs = writable({ ..._defaultPrefs })

// ── Initialisation ─────────────────────────────────────────────────────────────

let _initialised = false

async function _init() {
  if (_initialised) return
  _initialised = true
  try {
    const me = await getMe()
    _authUser.set(me)
    if (me.authenticated) {
      const prefs = await getPrefs()
      _prefs.set(prefs)
    }
  } catch {
    // Non-fatal — user just sees unauthenticated state
  }
}

// Run immediately on module load (Svelte store initialisation is synchronous,
// but the fetch is async; components read reactively so updates propagate).
_init()

// ── Public refreshPrefs ────────────────────────────────────────────────────────

export async function refreshPrefs() {
  try {
    const prefs = await getPrefs()
    _prefs.set(prefs)
  } catch {
    // Swallow errors — prefs just stay stale
  }
}

// ── Backward-compat githubUsername derived store ───────────────────────────────

export const githubUsername = derived(_authUser, $u => $u.login ?? null)

// ── Preferences store with mutation methods ────────────────────────────────────

function createPreferencesStore() {
  const { subscribe } = _prefs

  return {
    subscribe,

    async starPR(number) {
      await apiStarPR(number)
      _prefs.update(p => ({ ...p, starred: [...new Set([...p.starred, number])] }))
    },

    async unstarPR(number) {
      await apiUnstarPR(number)
      _prefs.update(p => ({ ...p, starred: p.starred.filter(n => n !== number) }))
    },

    async ignorePR(number) {
      await apiIgnorePR(number)
      _prefs.update(p => ({ ...p, ignored: [...new Set([...p.ignored, number])] }))
    },

    async unignorePR(number) {
      await apiUnignorePR(number)
      _prefs.update(p => ({ ...p, ignored: p.ignored.filter(n => n !== number) }))
    },

    async setNote(number, text) {
      if (!text || !text.trim()) {
        await apiDeleteNote(number)
        _prefs.update(p => {
          const notes = { ...p.notes }
          delete notes[String(number)]
          return { ...p, notes }
        })
      } else {
        await apiSetNote(number, text)
        _prefs.update(p => ({ ...p, notes: { ...p.notes, [String(number)]: text } }))
      }
    },

    async deleteNote(number) {
      await apiDeleteNote(number)
      _prefs.update(p => {
        const notes = { ...p.notes }
        delete notes[String(number)]
        return { ...p, notes }
      })
    },

    async clearStarred() {
      const current = get(_prefs)
      await Promise.all(current.starred.map(n => apiUnstarPR(n)))
      _prefs.update(p => ({ ...p, starred: [] }))
    },

    async clearIgnored() {
      const current = get(_prefs)
      await Promise.all(current.ignored.map(n => apiUnignorePR(n)))
      _prefs.update(p => ({ ...p, ignored: [] }))
    },

    // No-op: server-side there are no orphaned notes; notes are independent of stars.
    clearOrphanedNotes() {},
  }
}

export const preferences = createPreferencesStore()
