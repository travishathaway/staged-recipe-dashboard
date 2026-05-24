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

<div class="scoreboard">
  <h1>Reviewer Scoreboard</h1>

  <div class="filters">
    <div class="period-tabs">
      {#each PERIODS as p}
        <button
          class="period-tab"
          class:active={period === p}
          on:click={() => onPeriodChange(p)}
        >{PERIOD_LABELS[p]}</button>
      {/each}
    </div>

    <label class="team-filter">
      Team:
      <select on:change={onTeamChange}>
        <option value="">All teams</option>
        {#each teams as team}
          <option value={team.name}>{team.name}</option>
        {/each}
      </select>
    </label>
  </div>

  {#if loading}
    <p class="loading">Loading…</p>
  {:else if error}
    <p class="error">Error: {error}</p>
  {:else if scoreboard}
    <section>
      <h2>Human Reviewers</h2>
      {#if scoreboard.human_reviewers.length === 0}
        <p class="empty">No review activity in this period.</p>
      {:else}
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Reviewer</th>
                <th title="Formal reviews: approved + changes requested + dismissed">Reviews</th>
                <th title="Approved">✓</th>
                <th title="Changes requested">↩</th>
                <th title="Dismissed">✗</th>
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
      <section class="bots-section">
        <button class="collapsible" on:click={() => (botsOpen = !botsOpen)}>
          {botsOpen ? '▼' : '▶'} Bots ({scoreboard.bots.length})
        </button>
        {#if botsOpen}
          <div class="table-wrap">
            <table>
              <thead>
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
  .scoreboard { max-width: 900px; }

  h1 { font-size: 1.4rem; font-weight: 700; margin-bottom: 20px; color: #212529; }
  h2 { font-size: 1.05rem; font-weight: 600; margin-bottom: 10px; color: #343a40; }

  .filters {
    display: flex;
    align-items: center;
    gap: 24px;
    margin-bottom: 24px;
    flex-wrap: wrap;
  }

  .period-tabs { display: flex; gap: 4px; }
  .period-tab {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 6px;
    padding: 6px 14px;
    cursor: pointer;
    font-size: 0.85rem;
    color: #495057;
    transition: background 0.12s;
  }
  .period-tab:hover { background: #e9ecef; }
  .period-tab.active {
    background: #2d2d2d;
    color: #fff;
    border-color: #2d2d2d;
  }

  .team-filter {
    font-size: 0.85rem;
    color: #495057;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .team-filter select {
    border: 1px solid #dee2e6;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 0.85rem;
    background: #fff;
  }

  section { margin-bottom: 28px; }

  .table-wrap { overflow-x: auto; }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.88rem;
  }
  thead th {
    text-align: left;
    padding: 8px 12px;
    border-bottom: 2px solid #dee2e6;
    color: #6c757d;
    font-weight: 600;
    white-space: nowrap;
    cursor: default;
  }
  tbody tr:hover { background: #f8f9fa; }
  td { padding: 7px 12px; border-bottom: 1px solid #f0f0f0; }

  .login a { color: #0d6efd; text-decoration: none; font-weight: 500; }
  .login a:hover { text-decoration: underline; }

  .num { text-align: right; font-variant-numeric: tabular-nums; }
  .total { font-weight: 600; }
  .approved { color: #198754; }
  .changes { color: #fd7e14; }
  .dismissed { color: #6c757d; }
  .comments { color: #0d6efd; }

  .ts { color: #6c757d; white-space: nowrap; font-size: 0.82rem; }

  .bots-section { margin-top: 8px; }
  .collapsible {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 0.9rem;
    color: #6c757d;
    padding: 4px 0;
    margin-bottom: 8px;
    font-weight: 600;
  }
  .collapsible:hover { color: #343a40; }

  .loading, .error, .empty { color: #6c757d; padding: 16px 0; }
  .error { color: #dc3545; }
</style>
