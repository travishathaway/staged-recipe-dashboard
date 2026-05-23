<script>
  import { onMount } from 'svelte'
  import { link } from 'svelte-routing'
  import { getTeams, getPRs } from '../lib/api.js'
  import PRCard from '../lib/components/PRCard.svelte'
  import WaitingBar from '../lib/components/WaitingBar.svelte'

  let teams = []
  let topPRs = []
  let loading = true
  let error = null

  onMount(async () => {
    try {
      ;[teams, topPRs] = await Promise.all([
        getTeams(),
        getPRs({ status: 'needs_review', limit: 20 }),
      ])
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
  })
</script>

{#if loading}
  <p class="loading">Loading…</p>
{:else if error}
  <p class="error">Error: {error}</p>
{:else}
  <section class="chart-section">
    <WaitingBar {teams} />
  </section>

  <section class="teams-section">
    <h2>Review Teams</h2>
    <div class="team-grid">
      {#each teams as team}
        <a class="team-card" href="/team/{team.name}" use:link>
          <span class="team-name">{team.name}</span>
          <span class="count">{team.needs_review_count} waiting</span>
          {#if team.blocked_count > 0}
            <span class="blocked-count">{team.blocked_count} blocked</span>
          {/if}
        </a>
      {/each}
    </div>
  </section>

  <section class="pr-section">
    <h2>Longest Waiting PRs</h2>
    {#if topPRs.length === 0}
      <p class="empty">No PRs currently awaiting review.</p>
    {:else}
      {#each topPRs as pr}
        <PRCard {pr} />
      {/each}
    {/if}
  </section>
{/if}

<style>
  .loading, .error, .empty { color: #6c757d; padding: 24px 0; }
  .error { color: #dc3545; }

  .chart-section { margin-bottom: 32px; }

  h2 { font-size: 1.1rem; font-weight: 600; margin-bottom: 12px; color: #343a40; }

  .teams-section { margin-bottom: 32px; }
  .team-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 10px;
  }
  .team-card {
    background: #fff;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 14px 16px;
    text-decoration: none;
    display: flex;
    flex-direction: column;
    gap: 4px;
    transition: box-shadow 0.15s;
  }
  .team-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
  .team-name { font-weight: 600; color: #212529; font-size: 0.95rem; }
  .count { color: #198754; font-size: 0.85rem; }
  .blocked-count { color: #ffc107; font-size: 0.8rem; }

  .pr-section { margin-bottom: 32px; }
</style>
