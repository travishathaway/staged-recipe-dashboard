<script>
  import { preferences } from '../store.js'
  import { daysWaiting } from '../api.js'

  export let pr

  const STATUS_LABELS = new Set(['review-requested', 'Awaiting author contribution'])
  $: teamLabels = (pr.labels || []).filter(l => !STATUS_LABELS.has(l))
  $: isBlocked = (pr.labels || []).includes('Awaiting author contribution')
  $: waitLabel = daysWaiting(pr.waiting_since)
  $: isLong = parseInt(waitLabel) > 14
  $: isStarred = String(pr.number) in $preferences.starred.prs
  $: roleBadges = pr.roles ?? []
  $: authorReplied = pr.author_replied ?? false
  $: lastCommenter = pr.last_commenter ?? null

  const roleBadgeClass = {
    author:    'bg-primary-subtle text-primary-emphasis',
    reviewer:  'bg-success-subtle text-success-emphasis',
    commenter: 'bg-secondary-subtle text-secondary-emphasis',
  }

  function toggleStar(e) {
    e.preventDefault()
    e.stopPropagation()
    if (isStarred) {
      preferences.unstarPR(pr.number)
    } else {
      preferences.starPR(pr)
    }
  }
</script>

<li class="list-group-item list-group-item-action py-2 px-3"
  class:border-start={isBlocked && !authorReplied}
  class:border-3={isBlocked && !authorReplied}
  class:border-warning={isBlocked && !authorReplied}
  class:opacity-75={isBlocked && !authorReplied}
  style={authorReplied ? 'background-color: #cdffe552;' : ''}>
  <div class="d-flex justify-content-between align-items-start gap-2 mb-1">
    <a href={pr.html_url} target="_blank" rel="noopener noreferrer"
      class="link-primary fw-medium text-decoration-none flex-grow-1" style="font-size:0.95rem">
      <i class="bi bi-github"></i> #{pr.number} {pr.title}
    </a>
    <div class="d-flex align-items-center gap-1 flex-shrink-0">
      <span class="badge text-nowrap"
        class:bg-light={!isLong}
        class:text-secondary={!isLong}
        class:bg-danger-subtle={isLong}
        class:text-danger={isLong}>
        {waitLabel}
      </span>
      <button
        class="btn btn-sm p-0 border-0 bg-transparent"
        style="line-height:1; font-size:1rem"
        on:click={toggleStar}
        title={isStarred ? 'Unstar PR' : 'Star PR'}
        aria-label={isStarred ? 'Unstar' : 'Star'}
      >
        <i class="bi"
          class:bi-star-fill={isStarred}
          class:bi-star={!isStarred}
          class:text-warning={isStarred}
          class:text-secondary={!isStarred}></i>
      </button>
    </div>
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
    {#if roleBadges.length > 0}
      <span class="text-secondary" aria-hidden="true">·</span>
      <span class="d-flex gap-1 flex-wrap">
        {#each roleBadges as role}
          <span class="badge {roleBadgeClass[role] ?? 'bg-light text-secondary'}">{role}</span>
        {/each}
      </span>
    {/if}
    {#if authorReplied && lastCommenter}
      <span class="text-secondary" aria-hidden="true">·</span>
      <span class="text-success-emphasis" style="font-size: 0.85em;">last: @{lastCommenter}</span>
    {/if}
  </div>
</li>

<style>
  .border-start { border-left-width: 4px !important; }
</style>
