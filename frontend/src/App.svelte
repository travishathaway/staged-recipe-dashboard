<script>
  import { Router, Route, link } from 'svelte-routing'
  import Overview from './routes/Overview.svelte'
  import Team from './routes/Team.svelte'
  import Scoreboard from './routes/Scoreboard.svelte'

  export let url = ''
</script>

<nav>
  <a href="/" class="brand" use:link>conda-forge / staged-recipes</a>
  <span class="subtitle">Review Dashboard</span>
  <div class="nav-links">
    <a href="/" use:link class="nav-link">Overview</a>
    <a href="/scoreboard" use:link class="nav-link">Scoreboard</a>
  </div>
</nav>

<main>
  <Router {url}>
    <Route path="/" component={Overview} />
    <Route path="/scoreboard" component={Scoreboard} />
    <Route path="/team/:name" let:params>
      <Team name={params.name} />
    </Route>
  </Router>
</main>

<style>
  nav {
    background: #2d2d2d;
    color: #fff;
    padding: 12px 24px;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .brand {
    color: #fff;
    font-weight: 700;
    font-size: 1.1rem;
    text-decoration: none;
    font-family: monospace;
  }
  .brand:hover { color: #adb5bd; }
  .subtitle {
    color: #adb5bd;
    font-size: 0.9rem;
    flex: 1;
  }
  .nav-links {
    display: flex;
    gap: 16px;
    margin-left: auto;
  }
  .nav-link {
    color: #adb5bd;
    font-size: 0.88rem;
    text-decoration: none;
    padding: 4px 8px;
    border-radius: 4px;
    transition: color 0.12s, background 0.12s;
  }
  .nav-link:hover {
    color: #fff;
    background: rgba(255,255,255,0.1);
  }
  main {
    max-width: 1100px;
    margin: 0 auto;
    padding: 24px 16px;
  }
</style>
