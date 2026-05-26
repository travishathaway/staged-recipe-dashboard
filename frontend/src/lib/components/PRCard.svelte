<script>
  import { daysWaiting } from '../api.js'

  export let pr

  const STATUS_LABELS = new Set(['review-requested', 'Awaiting author contribution'])
  $: teamLabels = (pr.labels || []).filter(l => !STATUS_LABELS.has(l))
  $: isBlocked = (pr.labels || []).includes('Awaiting author contribution')
  $: waitLabel = daysWaiting(pr.waiting_since)
  $: isLong = parseInt(waitLabel) > 14
</script>

<article class="card mb-2 border-start border-3"
  class:border-success={!isBlocked}
  class:border-warning={isBlocked}
  class:opacity-75={isBlocked}>
  <div class="card-body py-2 px-3">
    <div class="d-flex justify-content-between align-items-start gap-2 mb-1">
      <a href={pr.html_url} target="_blank" rel="noopener noreferrer"
        class="link-primary fw-medium text-decoration-none flex-grow-1" style="font-size:0.95rem">
        <i class="bi bi-github"></i> #{pr.number} {pr.title}
      </a>
      <span class="badge text-nowrap"
        class:bg-light={!isLong}
        class:text-secondary={!isLong}
        class:bg-danger-subtle={isLong}
        class:text-danger={isLong}>
        {waitLabel}
      </span>
    </div>
    <div class="d-flex align-items-center gap-2 small text-secondary">
      <span>@{pr.author}</span>
      <span class="d-flex gap-1 flex-wrap">
        {#each teamLabels as label}
          <span class="badge bg-light text-secondary">{label}</span>
        {/each}
        {#if isBlocked}
          <span class="badge bg-warning-subtle text-warning-emphasis">awaiting author</span>
        {/if}
      </span>
    </div>
  </div>
</article>

<style>
  /* Bootstrap has no single-side border-width utility, so we set left only */
  .card { border-left-width: 4px !important; }
</style>
