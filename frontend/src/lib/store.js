/** Persistent user preferences store backed by localStorage. */

import { writable } from 'svelte/store'

const KEY = 'srdb-preferences'

const DEFAULT_PREFS = {
  version: 2,
  profile: { githubUsername: null },
  // starred.prs is a dict keyed by PR number (string) → full PR object.
  // The PR object is cached so starring/unstarring never needs a network round-trip.
  starred: { prs: {} },
}

function migrate(raw) {
  if (raw.version === 2) return raw
  if (raw.version === 1) {
    // v1 stored prs as an array of numbers; promote to an empty-object dict
    // (we can't recover the full PR objects, so we just drop the old numbers).
    return {
      ...raw,
      version: 2,
      starred: { prs: {} },
    }
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
