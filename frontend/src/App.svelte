<script>
  import { Router, Route, link } from 'svelte-routing'
  import Overview from './routes/Overview.svelte'
  import Team from './routes/Team.svelte'
  import Scoreboard from './routes/Scoreboard.svelte'

  export let url = ''
</script>

<nav class="navbar navbar-expand-lg navbar-dark bg-dark px-3">
  <a class="navbar-brand font-monospace" href="/" use:link>conda-forge / staged-recipes</a>
  <span class="text-secondary small ms-2 d-none d-md-inline">Review Dashboard</span>
  <div class="navbar-nav ms-auto flex-row gap-1">
    <a href="/" use:link class="nav-link px-2">Overview</a>
    <a href="/scoreboard" use:link class="nav-link px-2">Scoreboard</a>
  </div>
</nav>

<div class="container-sm py-4">
  <Router {url}>
    <Route path="/" component={Overview} />
    <Route path="/scoreboard" component={Scoreboard} />
    <Route path="/team/:name" let:params>
      <Team name={params.name} />
    </Route>
  </Router>
</div>
