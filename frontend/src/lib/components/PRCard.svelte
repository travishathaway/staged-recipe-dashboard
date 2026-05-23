<script>
  import { daysWaiting } from '../api.js'

  export let pr

  const STATUS_LABELS = new Set(['review-requested', 'Awaiting author contribution'])
  $: teamLabels = (pr.labels || []).filter(l => !STATUS_LABELS.has(l))
  $: isBlocked = (pr.labels || []).includes('Awaiting author contribution')
</script>

<article class="pr-card" class:blocked={isBlocked}>
  <header>
    <a href={pr.html_url} target="_blank" rel="noopener noreferrer" class="pr-title">
      #{pr.number} {pr.title}
    </a>
    <span class="waiting" class:long={parseInt(daysWaiting(pr.waiting_since)) > 14}>
      {daysWaiting(pr.waiting_since)}
    </span>
  </header>

  <footer>
    <span class="author">@{pr.author}</span>
    <span class="labels">
      {#each teamLabels as label}
        <span class="label">{label}</span>
      {/each}
      {#if isBlocked}
        <span class="label label--blocked">awaiting author</span>
      {/if}
    </span>
  </footer>
</article>

<style>
  .pr-card {
    background: #fff;
    border: 1px solid #dee2e6;
    border-left: 4px solid #198754;
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 8px;
  }
  .pr-card.blocked {
    border-left-color: #ffc107;
    opacity: 0.85;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 6px;
  }
  .pr-title {
    color: #0d6efd;
    text-decoration: none;
    font-weight: 500;
    font-size: 0.95rem;
    flex: 1;
  }
  .pr-title:hover { text-decoration: underline; }
  .waiting {
    font-size: 0.8rem;
    font-weight: 600;
    color: #6c757d;
    white-space: nowrap;
    background: #f8f9fa;
    padding: 2px 8px;
    border-radius: 10px;
  }
  .waiting.long { color: #dc3545; background: #fff0f0; }
  footer {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.8rem;
  }
  .author { color: #6c757d; }
  .labels { display: flex; gap: 4px; flex-wrap: wrap; }
  .label {
    background: #e9ecef;
    border-radius: 4px;
    padding: 1px 6px;
    font-size: 0.75rem;
    color: #495057;
  }
  .label--blocked { background: #fff3cd; color: #856404; }
</style>
