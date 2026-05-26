<script>
  import { onMount } from 'svelte'
  import { getTeams, getScoreboard } from '../lib/api.js'

  const PERIODS = ['30d', '90d', '1y', '3y']
  const PERIOD_LABELS = { '30d': '30 days', '90d': '90 days', '1y': '1 year', '3y': '3 years' }

  let period = '90d'
  let selectedTeam = null
  let teams = []
  let scoreboard = null
  let loading = true
  let error = null
  let botsOpen = false

  onMount(async () => {
    try {
      teams = await getTeams()
    } catch (e) {
      // non-fatal: team filter just won't be populated
    }
    await fetchScoreboard()
  })

  async function fetchScoreboard() {
    loading = true
    error = null
    try {
      scoreboard = await getScoreboard(period, selectedTeam)
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
  }

  function onPeriodChange(p) {
    period = p
    fetchScoreboard()
  }

  function onTeamChange(e) {
    selectedTeam = e.target.value || null
    fetchScoreboard()
  }

  function relativeTime(iso) {
    if (!iso) return '—'
    const ms = Date.now() - new Date(iso).getTime()
    const mins = Math.floor(ms / 60000)
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    const days = Math.floor(hrs / 24)
    if (days < 30) return `${days}d ago`
    const weeks = Math.floor(days / 7)
    if (weeks < 8) return `${weeks}w ago`
    return `${Math.floor(days / 30)}mo ago`
  }
</script>

<div style="max-width:900px">
  <h1 class="h4 fw-bold mb-4">Reviewer Scoreboard</h1>

  <div class="d-flex align-items-center gap-4 mb-4 flex-wrap">
    <div class="btn-group btn-group-sm" role="group" aria-label="Time period">
      {#each PERIODS as p}
        <button
          type="button"
          class="btn"
          class:btn-dark={period === p}
          class:btn-outline-secondary={period !== p}
          on:click={() => onPeriodChange(p)}
        >{PERIOD_LABELS[p]}</button>
      {/each}
    </div>

    <label class="d-flex align-items-center gap-2 small text-secondary">
      Team:
      <select class="form-select form-select-sm" style="width:auto" on:change={onTeamChange}>
        <option value="">All teams</option>
        {#each teams as team}
          <option value={team.name}>{team.name}</option>
        {/each}
      </select>
    </label>
  </div>

  {#if loading}
    <p class="text-secondary py-3">Loading…</p>
  {:else if error}
    <p class="text-danger py-3">Error: {error}</p>
  {:else if scoreboard}
    <section class="mb-4">
      <h2 class="h6 fw-semibold mb-3">Human Reviewers</h2>
      {#if scoreboard.human_reviewers.length === 0}
        <p class="text-secondary">No review activity in this period.</p>
      {:else}
        <div class="table-responsive">
          <table class="table table-hover table-sm">
            <thead class="table-light">
              <tr>
                <th>Reviewer</th>
                <th title="Formal reviews: approved + changes requested + dismissed">Reviews</th>
                <th title="Approved"><i class="bi bi-check-lg text-success"></i></th>
                <th title="Changes requested"><i class="bi bi-arrow-return-left text-warning"></i></th>
                <th title="Dismissed"><i class="bi bi-x-lg text-secondary"></i></th>
                <th title="Inline code review comments + comment-only reviews">Comments</th>
                <th>Last active</th>
              </tr>
            </thead>
            <tbody>
              {#each scoreboard.human_reviewers as r}
                <tr>
                  <td class="login">
                    <a href="https://github.com/{r.login}" target="_blank" rel="noreferrer">{r.login}</a>
                  </td>
                  <td class="num total">{r.formal_reviews}</td>
                  <td class="num approved">{r.approved}</td>
                  <td class="num changes">{r.changes_requested}</td>
                  <td class="num dismissed">{r.dismissed}</td>
                  <td class="num comments">{r.review_comments}</td>
                  <td class="ts">{relativeTime(r.last_active)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </section>

    {#if scoreboard.bots.length > 0}
      <section class="mt-2">
        <button class="btn btn-link btn-sm text-secondary text-decoration-none fw-semibold ps-0"
          on:click={() => (botsOpen = !botsOpen)}>
          <i class="bi {botsOpen ? 'bi-chevron-down' : 'bi-chevron-right'} me-1"></i>
          Bots ({scoreboard.bots.length})
        </button>
        {#if botsOpen}
          <div class="table-responsive mt-2">
            <table class="table table-hover table-sm">
              <thead class="table-light">
                <tr>
                  <th>Bot</th>
                  <th title="Formal reviews">Reviews</th>
                  <th title="Inline code review comments + comment-only reviews">Comments</th>
                  <th>Last active</th>
                </tr>
              </thead>
              <tbody>
                {#each scoreboard.bots as b}
                  <tr>
                    <td class="login">
                      <a href="https://github.com/{b.login}" target="_blank" rel="noreferrer">{b.login}</a>
                    </td>
                    <td class="num total">{b.formal_reviews}</td>
                    <td class="num comments">{b.review_comments}</td>
                    <td class="ts">{relativeTime(b.last_active)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </section>
    {/if}
  {/if}
</div>

<style>
  .login a { color: #0d6efd; text-decoration: none; font-weight: 500; }
  .login a:hover { text-decoration: underline; }

  .num { text-align: right; font-variant-numeric: tabular-nums; }
  .total { font-weight: 600; }
  .approved { color: #198754; }
  .changes { color: #fd7e14; }
  .dismissed { color: #6c757d; }
  .comments { color: #0d6efd; }

  .ts { color: #6c757d; white-space: nowrap; font-size: 0.82rem; }
</style>
