<script>
  import { onMount } from 'svelte'
  import { link } from 'svelte-routing'
  import { getPRs } from '../lib/api.js'
  import PRCard from '../lib/components/PRCard.svelte'

  export let name

  let needsReview = []
  let blocked = []
  let loading = true
  let error = null
  let showBlocked = false

  async function load() {
    loading = true
    error = null
    try {
      ;[needsReview, blocked] = await Promise.all([
        getPRs({ team: name, status: 'needs_review', limit: 200 }),
        getPRs({ team: name, status: 'blocked', limit: 200 }),
      ])
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
  }

  onMount(load)
  $: name, load()
</script>

<header class="team-header">
  <a href="/" use:link class="back">← All teams</a>
  <h1><code>{name}</code> team</h1>
</header>

{#if loading}
  <p class="loading">Loading…</p>
{:else if error}
  <p class="error">Error: {error}</p>
{:else}
  <div class="summary">
    <span class="badge badge--green">{needsReview.length} awaiting review</span>
    {#if blocked.length > 0}
      <button class="badge badge--yellow" on:click={() => (showBlocked = !showBlocked)}>
        {blocked.length} blocked {showBlocked ? '▲' : '▼'}
      </button>
    {/if}
  </div>

  {#if needsReview.length === 0}
    <p class="empty">No PRs awaiting review for this team.</p>
  {:else}
    <section class="pr-list">
      {#each needsReview as pr}
        <PRCard {pr} />
      {/each}
    </section>
  {/if}

  {#if showBlocked && blocked.length > 0}
    <section class="pr-list blocked-section">
      <h2>Blocked on author ({blocked.length})</h2>
      {#each blocked as pr}
        <PRCard {pr} />
      {/each}
    </section>
  {/if}
{/if}

<style>
  .team-header { margin-bottom: 20px; }
  .back {
    color: #6c757d;
    text-decoration: none;
    font-size: 0.85rem;
    display: inline-block;
    margin-bottom: 8px;
  }
  .back:hover { color: #0d6efd; }
  h1 { font-size: 1.5rem; font-weight: 700; color: #212529; }
  h1 code { background: #f1f3f5; padding: 2px 8px; border-radius: 4px; }
  h2 { font-size: 1rem; font-weight: 600; color: #6c757d; margin-bottom: 12px; }

  .summary { display: flex; gap: 10px; margin-bottom: 20px; align-items: center; }
  .badge {
    font-size: 0.85rem;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 12px;
    border: none;
    cursor: default;
  }
  .badge--green { background: #d1e7dd; color: #0a3622; }
  .badge--yellow { background: #fff3cd; color: #664d03; cursor: pointer; }

  .loading, .error, .empty { color: #6c757d; padding: 16px 0; }
  .error { color: #dc3545; }

  .pr-list { margin-bottom: 24px; }
  .blocked-section { opacity: 0.85; }
</style>
