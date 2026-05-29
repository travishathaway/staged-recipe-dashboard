/** Persistent user preferences store backed by localStorage. */

import { writable, derived } from 'svelte/store'

const KEY = 'srdb-preferences'

const DEFAULT_PREFS = {
  version: 3,
  profile: { githubUsername: null },
  // starred.prs is a dict keyed by PR number (string) → full PR object.
  // The PR object is cached so starring/unstarring never needs a network round-trip.
  starred:  { prs: {} },
  // ignored.prs is a dict keyed by PR number (string) → true.
  ignored:  { prs: {} },
  // notes.prs is a dict keyed by PR number (string) → note text string.
  notes:    { prs: {} },
}

function migrate(raw) {
  if (raw.version === 3) return raw
  if (raw.version === 2) {
    return {
      ...raw,
      version: 3,
      ignored: { prs: {} },
      notes:   { prs: {} },
    }
  }
  if (raw.version === 1) {
    // v1 stored prs as an array of numbers; promote to an empty-object dict
    // (we can't recover the full PR objects, so we just drop the old numbers).
    const v2 = {
      ...raw,
      version: 2,
      starred: { prs: {} },
    }
    return migrate(v2)  // recurse to v2→v3
  }
  // Future versions: add upgrade functions here
  return structuredClone(DEFAULT_PREFS)
}

function loadPrefs() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY))
    if (!raw || typeof raw.version !== 'number') return structuredClone(DEFAULT_PREFS)
    return migrate(raw)
  } catch {
    return structuredClone(DEFAULT_PREFS)
  }
}

function createPreferencesStore() {
  const { subscribe, update, set } = writable(loadPrefs())

  function persist(fn) {
    update(prefs => {
      const next = fn(prefs)
      localStorage.setItem(KEY, JSON.stringify(next))
      return next
    })
  }

  return {
    subscribe,

    setUsername(username) {
      persist(p => ({ ...p, profile: { ...p.profile, githubUsername: username || null } }))
    },

    /** Star a PR. `prObject` must be the full PR object so it can be cached locally. */
    starPR(prObject) {
      persist(p => {
        const key = String(prObject.number)
        if (p.starred.prs[key]) return p
        return { ...p, starred: { prs: { ...p.starred.prs, [key]: prObject } } }
      })
    },

    unstarPR(number) {
      persist(p => {
        const { [String(number)]: _removed, ...rest } = p.starred.prs
        return { ...p, starred: { prs: rest } }
      })
    },

    clearStarred() {
      persist(p => ({ ...p, starred: { prs: {} } }))
    },

    ignorePR(number) {
      persist(p => ({
        ...p,
        ignored: { prs: { ...p.ignored.prs, [String(number)]: true } },
      }))
    },

    unignorePR(number) {
      persist(p => {
        const { [String(number)]: _removed, ...rest } = p.ignored.prs
        return { ...p, ignored: { prs: rest } }
      })
    },

    setNote(number, text) {
      const key = String(number)
      persist(p => {
        if (!text || !text.trim()) {
          const { [key]: _removed, ...rest } = p.notes.prs
          return { ...p, notes: { prs: rest } }
        }
        return { ...p, notes: { prs: { ...p.notes.prs, [key]: text } } }
      })
    },

    clearOrphanedNotes() {
      persist(p => {
        const starredKeys = new Set(Object.keys(p.starred.prs))
        const filtered = Object.fromEntries(
          Object.entries(p.notes.prs).filter(([k]) => starredKeys.has(k))
        )
        return { ...p, notes: { prs: filtered } }
      })
    },

    exportJSON() {
      const data = JSON.parse(localStorage.getItem(KEY) || JSON.stringify(DEFAULT_PREFS))
      const blob = new Blob(
        [JSON.stringify({ ...data, exportedAt: new Date().toISOString() }, null, 2)],
        { type: 'application/json' }
      )
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'staged-recipe-dashboard-settings.json'
      a.click()
      URL.revokeObjectURL(url)
    },

    importJSON(jsonString) {
      const parsed = JSON.parse(jsonString)
      if (typeof parsed.version !== 'number') throw new Error('Invalid settings file: missing version')
      const migrated = migrate(parsed)
      localStorage.setItem(KEY, JSON.stringify(migrated))
      set(migrated)
    },

    reset() {
      localStorage.removeItem(KEY)
      set(structuredClone(DEFAULT_PREFS))
    },
  }
}

export const preferences = createPreferencesStore()

/**
 * Derived store that emits only when githubUsername actually changes.
 * Use this in reactive fetch statements to avoid spurious refetches when
 * other preferences (notes, stars, ignore) are mutated.
 */
export const githubUsername = derived(preferences, $p => $p.profile.githubUsername)
