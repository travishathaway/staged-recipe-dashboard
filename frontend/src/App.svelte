<script>
  import { Router, Route } from 'svelte-routing'
  import Overview from './routes/Overview.svelte'
  import Team from './routes/Team.svelte'

  export let url = ''
</script>

<nav>
  <a href="/" class="brand">conda-forge / staged-recipes</a>
  <span class="subtitle">Review Dashboard</span>
</nav>

<main>
  <Router {url}>
    <Route path="/" component={Overview} />
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
  }
  main {
    max-width: 1100px;
    margin: 0 auto;
    padding: 24px 16px;
  }
</style>
