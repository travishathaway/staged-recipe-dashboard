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
  $: isIgnored = String(pr.number) in $preferences.ignored.prs
  $: noteText  = $preferences.notes.prs[String(pr.number)] ?? ''
  $: hasNote   = noteText.length > 0
  let isEditing = false
  let draftNote = ''
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

  function toggleIgnore(e) {
    e.preventDefault()
    e.stopPropagation()
    if (isIgnored) {
      preferences.unignorePR(pr.number)
    } else {
      preferences.ignorePR(pr.number)
    }
  }

  function focusOnMount(node) {
    node.focus()
  }

  function openNote(e) {
    e.preventDefault()
    e.stopPropagation()
    draftNote = noteText
    isEditing = true
  }

  function saveNote() {
    preferences.setNote(pr.number, draftNote)
    isEditing = false
  }

  function cancelNote() {
    isEditing = false
  }
</script>

<li class="list-group-item list-group-item-action py-2 px-3 pr-card"
  class:pr-card--ready={authorReplied && !isBlocked}
  class:pr-card--blocked={isBlocked && !authorReplied}
  class:opacity-50={isIgnored}>
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
        on:click={openNote}
        title={hasNote ? 'Edit note' : 'Add note'}
        aria-label={hasNote ? 'Edit note' : 'Add note'}
      >
        <i class="bi bi-pencil"
          class:text-primary={hasNote}
          class:text-secondary={!hasNote}></i>
      </button>
      <button
        class="btn btn-sm p-0 border-0 bg-transparent"
        style="line-height:1; font-size:1rem"
        on:click={toggleIgnore}
        title={isIgnored ? 'Un-ignore PR' : 'Ignore PR'}
        aria-label={isIgnored ? 'Un-ignore' : 'Ignore'}
      >
        <i class="bi"
          class:bi-eye-slash-fill={isIgnored}
          class:bi-eye-slash={!isIgnored}
          class:text-muted={isIgnored}
          class:text-secondary={!isIgnored}></i>
      </button>
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
    {#if lastCommenter}
      <span class="text-secondary" aria-hidden="true">·</span>
      <span class:text-success-emphasis={authorReplied} class:text-secondary={!authorReplied} style="font-size: 0.85em;">last: @{lastCommenter}</span>
    {/if}
  </div>
  {#if hasNote && !isEditing}
    <div class="mt-1 small text-secondary fst-italic note-text">{noteText}</div>
  {/if}
  {#if isEditing}
    <div class="mt-1" style="max-width: 80ch">
      <textarea
        class="form-control form-control-sm"
        rows="2"
        bind:value={draftNote}
        on:keydown={(e) => { if (e.key === 'Escape') cancelNote() }}
        use:focusOnMount
      ></textarea>
      <div class="d-flex gap-2 mt-1">
        <button class="btn btn-sm btn-primary" on:click={saveNote}>Save</button>
        <button class="btn btn-sm btn-outline-secondary" on:click={cancelNote}>Cancel</button>
      </div>
    </div>
  {/if}
</li>

<style>
  .pr-card {
    border-radius: 6px !important;
    border-left: 5px solid var(--bs-border-color) !important;
  }
  .pr-card--ready {
    border-left-color: var(--bs-success) !important;
  }
  .pr-card--blocked {
    border-left-color: var(--bs-warning) !important;
    opacity: 0.75;
  }
  .note-text {
    max-width: 80ch;
    white-space: pre-wrap;
  }
</style>
