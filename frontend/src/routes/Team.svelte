<script>
  import { onMount } from 'svelte'
  import { link } from 'svelte-routing'
  import { getPRs } from '../lib/api.js'
  import PRCard from '../lib/components/PRCard.svelte'

  export let name

  let needsReview = []
  let blocked = []
  let needsReviewTotal = 0
  let blockedTotal = 0
  let loading = true
  let error = null
  let showBlocked = false

  async function load() {
    loading = true
    error = null
    try {
      const [needsReviewData, blockedData] = await Promise.all([
        getPRs({ team: name, status: 'needs_review', limit: 200 }),
        getPRs({ team: name, status: 'blocked', limit: 200 }),
      ])
      needsReview = needsReviewData.results
      needsReviewTotal = needsReviewData.total
      blocked = blockedData.results
      blockedTotal = blockedData.total
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
  }

  onMount(load)
  $: name, load()
</script>

<header class="mb-4">
  <a href="/" use:link class="text-secondary text-decoration-none small d-inline-block mb-2">
    <i class="bi bi-arrow-left me-1"></i>All teams
  </a>
  <h1 class="h4 fw-bold text-dark"><code class="bg-light px-2 py-1 rounded">{name}</code> team</h1>
</header>

{#if loading}
  <p class="text-secondary py-3">Loading…</p>
{:else if error}
  <p class="text-danger py-3">Error: {error}</p>
{:else}
  <div class="d-flex gap-2 mb-4 align-items-center">
    <span class="badge bg-success">{needsReviewTotal} awaiting review</span>
    {#if blockedTotal > 0}
      <button class="badge bg-warning text-dark border-0" style="cursor:pointer"
        on:click={() => (showBlocked = !showBlocked)}>
        {blockedTotal} blocked
        <i class="bi {showBlocked ? 'bi-chevron-up' : 'bi-chevron-down'} ms-1"></i>
      </button>
    {/if}
  </div>

  {#if needsReview.length === 0}
    <p class="text-secondary">No PRs awaiting review for this team.</p>
  {:else}
    <section class="mb-4">
      {#each needsReview as pr}
        <PRCard {pr} />
      {/each}
    </section>
  {/if}

  {#if showBlocked && blockedTotal > 0}
    <section class="mb-4" style="opacity:0.85">
      <h2 class="h6 fw-semibold text-secondary mb-3">Blocked on author ({blockedTotal})</h2>
      {#each blocked as pr}
        <PRCard {pr} />
      {/each}
    </section>
  {/if}
{/if}
