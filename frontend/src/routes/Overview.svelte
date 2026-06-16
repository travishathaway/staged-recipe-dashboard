<script>
  import { onMount } from 'svelte'
  import { navigate } from 'svelte-routing'
  import { Offcanvas } from 'bootstrap'
  import { getTeams, getPRs, getStarredPRs } from '../lib/api.js'
  import { preferences, authUser, githubUsername } from '../lib/store.js'
  import PRCard from '../lib/components/PRCard.svelte'
  import TreeMap from '../lib/components/TreeMap.svelte'

  let teams = []
  let teamsLoaded = false
  let error = null

  const PAGE_SIZE = 20

  // Initialize state from URL so the first fetch uses the correct values.
  const _init = new URLSearchParams(window.location.search)
  let selectedTeam = _init.get('team') || null
  let currentPage = Math.max(1, parseInt(_init.get('page') ?? '1', 10) || 1)
  let showStarred = _init.get('starred') === 'true'
  const _rolesParam = _init.get('roles')
  let selectedRoles = new Set(_rolesParam ? _rolesParam.split(',').filter(Boolean) : [])
  let showUnreviewed = _init.get('unreviewed') === 'true'

  let teamPRs = []
  let teamPRsLoading = false
  let teamPRsError = null
  let filteredTotal = 0
  let lastUpdatedAt = null

  const logoMap = {
    python:     ['/logos/python.svg'],
    rust:       ['/logos/rust.svg'],
    r:          ['/logos/r.svg'],
    go:         ['/logos/go.svg'],
    java:       ['/logos/java.svg'],
    nodejs:     ['/logos/nodejs.svg'],
    perl:       ['/logos/perl.svg'],
    fortran:    ['/logos/fortran.svg'],
    'c-cpp':    ['/logos/c.svg', '/logos/cplusplus.svg'],
    'python-c': ['/logos/python.svg', '/logos/c.svg'],
  }

  function getLogos(name) {
    return logoMap[name] ?? []
  }

  function timeAgo(isoString) {
    if (!isoString) return null
    const ms = Date.now() - new Date(isoString).getTime()
    const minutes = Math.floor(ms / 60_000)
    if (minutes < 1) return 'just now'
    if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
    const days = Math.floor(hours / 24)
    return `${days} day${days === 1 ? '' : 's'} ago`
  }

  $: totalWaiting = teams.reduce((sum, t) => sum + t.needs_review_count, 0)
  $: loading = !teamsLoaded

  $: starredCount = ($preferences.starred || []).length

  async function fetchTeamPRs(team, page, starred, username, roles, unreviewed) {
    teamPRsLoading = true
    teamPRsError = null
    try {
      if (starred) {
        const starredNumbers = $preferences.starred || []
        if (starredNumbers.length === 0) {
          teamPRs = []
          return
        }
        let results = await getStarredPRs(starredNumbers)
        results = results?.results ?? results ?? []
        if (team) results = results.filter(pr => (pr.labels || []).includes(team))
        teamPRs = results
      } else {
        const params = { status: 'needs_review', limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }
        if (team) params.team = team
        if (roles && roles.size > 0) params.roles = [...roles]
        if (unreviewed) params.unreviewed = true
        const data = await getPRs(params)
        teamPRs = data.results ?? []
        filteredTotal = data.total ?? 0
        if (data.last_updated_at && !lastUpdatedAt) {
          lastUpdatedAt = data.last_updated_at
        }
      }
    } catch (e) {
      teamPRsError = e.message
      teamPRs = []
    } finally {
      teamPRsLoading = false
    }
  }

  async function fetchTeams(username, roles, unreviewed, starred) {
    if (starred) {
      teamsLoaded = true
      return
    }
    try {
      teams = await getTeams({
        roles: roles && roles.size > 0 ? [...roles] : [],
        unreviewed,
      })
    } catch (e) {
      // Non-fatal — sidebar counts degrade gracefully
    } finally {
      teamsLoaded = true
    }
  }

  // When in starred mode, re-fetch from server when the starred list changes.
  let _prevStarredKeys = null
  $: if (showStarred) {
    const starredNumbers = $preferences.starred || []
    const currentKeys = [...starredNumbers].sort().join(',')
    if (_prevStarredKeys !== null && currentKeys !== _prevStarredKeys) {
      fetchTeamPRs(selectedTeam, currentPage, showStarred, $githubUsername, selectedRoles, showUnreviewed)
    }
    _prevStarredKeys = currentKeys
  }

  function syncURL(team, page, starred, roles, unreviewed) {
    const params = new URLSearchParams()
    if (team) params.set('team', team)
    if (page > 1) params.set('page', String(page))
    if (starred) params.set('starred', 'true')
    if (roles && roles.size > 0) params.set('roles', [...roles].join(','))
    if (unreviewed) params.set('unreviewed', 'true')
    const search = params.toString()
    navigate(search ? `/?${search}` : '/', { replace: true })
  }

  function selectTeam(name) {
    selectedTeam = name
    currentPage = 1
    const el = document.getElementById('teamsSidebar')
    if (el) {
      const oc = Offcanvas.getInstance(el)
      if (oc) oc.hide()
    }
  }

  function goToPage(page) {
    currentPage = page
  }

  function toggleStarred() {
    showStarred = !showStarred
    currentPage = 1
  }

  function toggleRole(role) {
    if (selectedRoles.has(role)) {
      selectedRoles.delete(role)
    } else {
      selectedRoles.add(role)
    }
    selectedRoles = selectedRoles  // trigger Svelte reactivity
    currentPage = 1
  }

  function toggleUnreviewed() {
    showUnreviewed = !showUnreviewed
    currentPage = 1
  }

  $: totalCount = selectedTeam
    ? (teams.find(t => t.name === selectedTeam)?.needs_review_count ?? 0)
    : totalWaiting
  $: activeTotal = (selectedRoles.size > 0 || showUnreviewed) ? filteredTotal : totalCount
  $: totalPages = Math.max(1, Math.ceil(activeTotal / PAGE_SIZE))

  $: syncURL(selectedTeam, currentPage, showStarred, selectedRoles, showUnreviewed)
  $: fetchTeamPRs(selectedTeam, currentPage, showStarred, $githubUsername, selectedRoles, showUnreviewed)
  $: fetchTeams($githubUsername, selectedRoles, showUnreviewed, showStarred)

  onMount(() => {
    // Teams are loaded reactively via fetchTeams above.
    // onMount is kept for any future imperative setup needs.
  })
</script>

{#if loading}
  <p class="text-secondary py-4">Loading…</p>
{:else if error}
  <p class="text-danger py-4">Error: {error}</p>
{:else}
  <!-- Stats + TreeMap -->
  <div class="row mb-4">
    <div class="col-md-3">
      <h3>Reviews requested: <br />
        <span style="font-size:4rem">{totalWaiting}</span>
      </h3>
      {#if lastUpdatedAt}
        <p class="text-secondary small mb-0">Last updated: {timeAgo(lastUpdatedAt)}</p>
      {/if}
    </div>
    <div class="col-md-9">
      <TreeMap {teams} />
    </div>
  </div>

  <!-- Offcanvas sidebar (mobile) -->
  <div class="offcanvas offcanvas-start" tabindex="-1" id="teamsSidebar" aria-labelledby="teamsSidebarLabel">
    <div class="offcanvas-header">
      <h4 class="offcanvas-title" id="teamsSidebarLabel">Review Teams</h4>
      <button type="button" class="btn-close" data-bs-dismiss="offcanvas" aria-label="Close"></button>
    </div>
    <div class="offcanvas-body p-2">
      <nav class="nav flex-column nav-pills">
        <button type="button"
          class="nav-link d-flex align-items-center gap-2 text-start w-100"
          class:active={selectedTeam === null}
          on:click={() => selectTeam(null)}
        >
          <i class="bi bi-people-fill fs-5"></i>
          <span>All teams</span>
          <span class="badge rounded-pill text-bg-light ms-auto">{totalWaiting}</span>
        </button>
        {#each teams as team}
          <button type="button"
            class="nav-link d-flex align-items-center gap-2 text-start w-100"
            class:active={selectedTeam === team.name}
            on:click={() => selectTeam(team.name)}
          >
            <span class="d-flex gap-1 flex-shrink-0">
              {#each getLogos(team.name) as logo}
                <img src={logo} alt="" width="20" height="20" />
              {/each}
              {#if getLogos(team.name).length === 0}
                <span style="font-size:0.7rem;width:20px;height:20px;display:inline-flex;align-items:center;justify-content:center;background:var(--bs-secondary-bg);border-radius:50%">
                  {(team.name[0] ?? '?').toUpperCase()}
                </span>
              {/if}
            </span>
            <span>{team.name}</span>
            <span class="badge rounded-pill text-bg-light ms-auto">{team.needs_review_count}</span>
          </button>
        {/each}
      </nav>
    </div>
  </div>

  <hr />

  <!-- Main content row -->
  <div class="row">
    <!-- Desktop sidebar -->
    <div class="col-md-3 d-none d-md-block">
      <h4 class="fw-semibold mb-3">Review Teams</h4>
      <nav class="nav flex-column nav-pills">
        <button type="button"
          class="nav-link d-flex align-items-center gap-2 text-start w-100"
          class:active={selectedTeam === null}
          on:click={() => selectTeam(null)}
        >
          <i class="bi bi-people-fill fs-5"></i>
          <span>All teams</span>
          <span class="badge rounded-pill text-bg-light ms-auto">{totalWaiting}</span>
        </button>
        {#each teams as team}
          <button type="button"
            class="nav-link d-flex align-items-center gap-2 text-start w-100"
            class:active={selectedTeam === team.name}
            on:click={() => selectTeam(team.name)}
          >
            <span class="d-flex gap-1 flex-shrink-0">
              {#each getLogos(team.name) as logo}
                <img src={logo} alt="" width="20" height="20" />
              {/each}
              {#if getLogos(team.name).length === 0}
                <span style="font-size:0.7rem;width:20px;height:20px;display:inline-flex;align-items:center;justify-content:center;background:var(--bs-secondary-bg);border-radius:50%">
                  {(team.name[0] ?? '?').toUpperCase()}
                </span>
              {/if}
            </span>
            <span>{team.name}</span>
            <span class="badge rounded-pill text-bg-light ms-auto">{team.needs_review_count}</span>
          </button>
        {/each}
      </nav>
    </div>

    <!-- PR panel -->
    <div class="col-12 col-md-9">
      <!-- Mobile hamburger -->
      <button
        class="btn btn-outline-secondary d-md-none mb-3"
        data-bs-toggle="offcanvas"
        data-bs-target="#teamsSidebar"
        aria-controls="teamsSidebar"
      >
        <i class="bi bi-list"></i> Teams
      </button>

      <!-- Filters bar -->
      <div class="d-flex align-items-center gap-2 mb-3 flex-wrap">
        <button
          class="btn btn-sm"
          class:btn-warning={showStarred}
          class:btn-outline-secondary={!showStarred}
          on:click={toggleStarred}
        >
          <i class="bi" class:bi-star-fill={showStarred} class:bi-star={!showStarred}></i>
          Starred
          {#if starredCount > 0}
            <span class="badge text-bg-light ms-1">{starredCount}</span>
          {/if}
        </button>

        <button
          class="btn btn-sm"
          class:btn-info={showUnreviewed}
          class:btn-outline-secondary={!showUnreviewed}
          on:click={toggleUnreviewed}
        >
          <i class="bi bi-eye-slash"></i>
          No reviews yet
        </button>

        {#if $authUser.authenticated}
          <span class="text-secondary small">Your roles:</span>
          {#each ['author', 'reviewer', 'commenter'] as role}
            <div class="form-check form-check-inline mb-0">
              <input
                class="form-check-input"
                type="checkbox"
                id="role-{role}"
                checked={selectedRoles.has(role)}
                on:change={() => toggleRole(role)}
              />
              <label class="form-check-label small" for="role-{role}">
                {role.charAt(0).toUpperCase() + role.slice(1)}
              </label>
            </div>
          {/each}
        {/if}
      </div>

      {#if teamPRsLoading}
        <div class="d-flex align-items-center gap-2 text-secondary py-4">
          <div class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></div>
          <span>Loading…</span>
        </div>
      {:else if teamPRsError}
        <p class="text-danger py-4">Error loading PRs: {teamPRsError}</p>
      {:else if teamPRs.length === 0}
        {#if showStarred}
          <p class="text-secondary">No starred PRs are currently open.</p>
        {:else}
          <p class="text-secondary">No PRs currently awaiting review.</p>
        {/if}
      {:else}
        <ul class="list-group list-group-flush mb-2">
          {#each teamPRs as pr}
            <PRCard {pr} />
          {/each}
        </ul>

        {#if !showStarred && totalPages > 1}
          <nav aria-label="PR pagination" class="mt-4">
            <ul class="pagination justify-content-center">
              <li class="page-item" class:disabled={currentPage === 1}>
                <button class="page-link" on:click={() => goToPage(currentPage - 1)} disabled={currentPage === 1}>
                  &laquo;
                </button>
              </li>
              {#each Array.from({ length: totalPages }, (_, i) => i + 1) as page}
                <li class="page-item" class:active={page === currentPage}>
                  <button class="page-link" on:click={() => goToPage(page)}>{page}</button>
                </li>
              {/each}
              <li class="page-item" class:disabled={currentPage === totalPages}>
                <button class="page-link" on:click={() => goToPage(currentPage + 1)} disabled={currentPage === totalPages}>
                  &raquo;
                </button>
              </li>
            </ul>
          </nav>
        {/if}
      {/if}
    </div>
  </div>
{/if}
