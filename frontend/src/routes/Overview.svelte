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
  let totalWaiting = 0

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

    totalWaiting = teams.reduce((sum, t) => sum + t.needs_review_count, 0);
  })
</script>

{#if loading}
  <p class="text-secondary py-4">Loading…</p>
{:else if error}
  <p class="text-danger py-4">Error: {error}</p>
{:else}
  <section class="mb-4">
    <WaitingBar {teams} />
  </section>

  <h3>Reviews requested: {totalWaiting}</h3>

  <section class="mb-4">
    <h2 class="h6 fw-semibold text-dark mb-3">Review Teams</h2>
    <div class="row row-cols-2 row-cols-md-3 row-cols-lg-4 row-cols-xl-5 g-2">
      {#each teams as team}
        <div class="col">
          <a class="card h-100 text-decoration-none p-3 d-flex flex-column gap-1" href="/team/{team.name}" use:link>
            <span class="fw-semibold text-dark" style="font-size:0.95rem">{team.name}</span>
            <span class="text-success small">{team.needs_review_count} waiting</span>
            {#if team.blocked_count > 0}
              <span class="text-warning small">{team.blocked_count} blocked</span>
            {/if}
          </a>
        </div>
      {/each}
    </div>
  </section>

  <section class="mb-4 col-md-6 col-sm-12">
    <h2 class="h6 fw-semibold text-dark mb-3">Longest Waiting PRs</h2>
    {#if topPRs.length === 0}
      <p class="text-secondary">No PRs currently awaiting review.</p>
    {:else}
      {#each topPRs as pr}
        <PRCard {pr} />
      {/each}
    {/if}
  </section>
{/if}
