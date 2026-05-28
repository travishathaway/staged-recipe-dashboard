<script>
  import { onMount, onDestroy } from 'svelte'
  import { Router, Route, link } from 'svelte-routing'
  import Overview from './routes/Overview.svelte'
  import Team from './routes/Team.svelte'
  import Scoreboard from './routes/Scoreboard.svelte'
  import Profile from './routes/Profile.svelte'
  import { preferences } from './lib/store.js'

  export let url = ''

  let currentPath = window.location.pathname

  function onPopState() {
    currentPath = window.location.pathname
  }

  // svelte-routing uses history.pushState; we need to also catch those.
  // Patch pushState so we get notified on programmatic navigation.
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

  $: username = $preferences.profile.githubUsername
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

  <!-- Profile avatar dropdown -->
  <div class="dropdown">
    <button
      class="btn btn-link p-0 border-0 text-light d-flex align-items-center"
      data-bs-toggle="dropdown"
      aria-expanded="false"
      aria-label="Profile menu"
    >
      {#if username}
        <img
          src="https://github.com/{username}.png?size=128"
          alt="@{username}"
          width="32"
          height="32"
          class="rounded-circle"
          style="object-fit:cover"
        />
      {:else}
        <i class="bi bi-person-circle" style="font-size:1.75rem"></i>
      {/if}
    </button>
    <ul class="dropdown-menu dropdown-menu-end">
      {#if username}
        <li><span class="dropdown-item-text fw-semibold">@{username}</span></li>
        <li><hr class="dropdown-divider" /></li>
      {:else}
        <li><span class="dropdown-item-text text-secondary small">Set up your profile</span></li>
      {/if}
      <li><a class="dropdown-item" href="/profile" use:link>Profile</a></li>
    </ul>
  </div>
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
