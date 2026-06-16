<script>
  import { onMount, onDestroy } from 'svelte'
  import { Router, Route, link } from 'svelte-routing'
  import Overview from './routes/Overview.svelte'
  import Team from './routes/Team.svelte'
  import Scoreboard from './routes/Scoreboard.svelte'
  import Profile from './routes/Profile.svelte'
  import { authUser, preferences, refreshPrefs } from './lib/store.js'
  import { migrateLocalStorage } from './lib/api.js'

  export let url = ''

  let currentPath = window.location.pathname

  function onPopState() {
    currentPath = window.location.pathname
  }

  // svelte-routing uses history.pushState; we need to also catch those.
  const _origPushState = history.pushState.bind(history)
  history.pushState = function (...args) {
    _origPushState(...args)
    currentPath = window.location.pathname
  }

  onMount(() => {
    window.addEventListener('popstate', onPopState)
  })

  onDestroy(() => {
    window.removeEventListener('popstate', onPopState)
    history.pushState = _origPushState
  })

  // ── Migration modal ────────────────────────────────────────────────────────

  const LS_KEY = 'srdb-preferences'

  let showMigrationModal = false
  let migrationBlob = null
  let migrationCounts = { starred: 0, ignored: 0, notes: 0 }
  let migrating = false

  function _parseLocalStorage() {
    try {
      const raw = JSON.parse(localStorage.getItem(LS_KEY))
      if (!raw || typeof raw.version !== 'number') return null
      return raw
    } catch {
      return null
    }
  }

  function _hasLocalData(blob) {
    if (!blob) return false
    const starred = Object.keys(blob.starred?.prs ?? {}).length
    const ignored = Object.keys(blob.ignored?.prs ?? {}).length
    const notes = Object.keys(blob.notes?.prs ?? {}).length
    return starred > 0 || ignored > 0 || notes > 0
  }

  function _serverPrefsEmpty(prefs) {
    return (
      (prefs.starred?.length ?? 0) === 0 &&
      (prefs.ignored?.length ?? 0) === 0 &&
      Object.keys(prefs.notes ?? {}).length === 0
    )
  }

  // Watch for first authenticated login + empty server prefs + non-empty localStorage
  let _prevAuthenticated = false
  $: if ($authUser.authenticated && !_prevAuthenticated) {
    _prevAuthenticated = true
    const blob = _parseLocalStorage()
    if (_hasLocalData(blob) && _serverPrefsEmpty($preferences)) {
      migrationBlob = blob
      migrationCounts = {
        starred: Object.keys(blob.starred?.prs ?? {}).length,
        ignored: Object.keys(blob.ignored?.prs ?? {}).length,
        notes: Object.keys(blob.notes?.prs ?? {}).length,
      }
      showMigrationModal = true
    }
  }

  async function doMigrate() {
    migrating = true
    try {
      await migrateLocalStorage(migrationBlob)
      await refreshPrefs()
      localStorage.removeItem(LS_KEY)
    } finally {
      migrating = false
      showMigrationModal = false
    }
  }

  function skipMigrate() {
    localStorage.removeItem(LS_KEY)
    showMigrationModal = false
  }
</script>

<nav class="navbar navbar-expand-lg navbar-dark bg-dark px-3">
  <a class="navbar-brand font-monospace me-4" href="/" use:link>conda-forge / staged-recipes</a>

  <div class="navbar-nav flex-row gap-1 me-auto">
    <a href="/" use:link
      class="nav-link px-2"
      class:active={currentPath === '/'}
    >Overview</a>
    <a href="/scoreboard" use:link
      class="nav-link px-2"
      class:active={currentPath === '/scoreboard'}
    >Scoreboard</a>
  </div>

  <!-- Auth nav: login button or avatar dropdown -->
  {#if $authUser.authenticated}
    <div class="dropdown">
      <button
        class="btn btn-link p-0 border-0 text-light d-flex align-items-center"
        data-bs-toggle="dropdown"
        aria-expanded="false"
        aria-label="Profile menu"
      >
        <img
          src={$authUser.avatar_url}
          alt="@{$authUser.login}"
          width="32"
          height="32"
          class="rounded-circle"
          style="object-fit:cover"
        />
      </button>
      <ul class="dropdown-menu dropdown-menu-end">
        <li><span class="dropdown-item-text fw-semibold">@{$authUser.login}</span></li>
        <li><hr class="dropdown-divider" /></li>
        <li><a class="dropdown-item" href="/profile" use:link>Profile</a></li>
        <li><a class="dropdown-item" href="/auth/logout">Logout</a></li>
      </ul>
    </div>
  {:else}
    <a href="/auth/login" class="btn btn-outline-light btn-sm">
      <i class="bi bi-github"></i> Login with GitHub
    </a>
  {/if}
</nav>

<div class="container-sm py-4">
  <Router {url}>
    <Route path="/" component={Overview} />
    <Route path="/scoreboard" component={Scoreboard} />
    <Route path="/profile" component={Profile} />
    <Route path="/team/:name" let:params>
      <Team name={params.name} />
    </Route>
  </Router>
</div>

<!-- Migration modal -->
{#if showMigrationModal}
  <div class="modal d-block" tabindex="-1" style="background: rgba(0,0,0,0.5)">
    <div class="modal-dialog modal-dialog-centered">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">Import your local preferences?</h5>
        </div>
        <div class="modal-body">
          <p>We found preferences stored on this device:</p>
          <ul>
            {#if migrationCounts.starred > 0}
              <li><strong>{migrationCounts.starred}</strong> starred PR{migrationCounts.starred === 1 ? '' : 's'}</li>
            {/if}
            {#if migrationCounts.ignored > 0}
              <li><strong>{migrationCounts.ignored}</strong> ignored PR{migrationCounts.ignored === 1 ? '' : 's'}</li>
            {/if}
            {#if migrationCounts.notes > 0}
              <li><strong>{migrationCounts.notes}</strong> note{migrationCounts.notes === 1 ? '' : 's'}</li>
            {/if}
          </ul>
          <p class="mb-0">Import them to your account so they sync across all your devices?</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline-secondary" on:click={skipMigrate} disabled={migrating}>
            Start fresh
          </button>
          <button class="btn btn-primary" on:click={doMigrate} disabled={migrating}>
            {#if migrating}
              <span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
              Importing…
            {:else}
              Import
            {/if}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}
