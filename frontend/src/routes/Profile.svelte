<script>
  import { preferences, authUser } from '../lib/store.js'

  // --- Starred PRs section ---
  let showClearStarredConfirm = false

  async function confirmClearStarred() {
    await preferences.clearStarred()
    showClearStarredConfirm = false
  }

  // --- Ignored PRs section ---
  let showClearIgnoredConfirm = false

  async function confirmClearIgnored() {
    await preferences.clearIgnored()
    showClearIgnoredConfirm = false
  }

  // --- Notes section ---
  // With server-side storage, notes are independent of stars — no orphan concept.
  $: starredCount = ($preferences.starred || []).length
  $: ignoredCount = ($preferences.ignored || []).length
  $: notesCount = Object.keys($preferences.notes || {}).length
</script>

<div class="row justify-content-center">
  <div class="col-12 col-md-7 col-lg-6">
    <h2 class="mb-4">Profile</h2>

    <!-- GitHub Account -->
    <section class="mb-5">
      <h5 class="fw-semibold mb-3">GitHub Account</h5>
      {#if $authUser.authenticated}
        <div class="d-flex align-items-center gap-3">
          <img
            src={$authUser.avatar_url}
            alt="@{$authUser.login}"
            width="48"
            height="48"
            class="rounded-circle"
            style="object-fit:cover"
          />
          <div>
            <div class="fw-semibold">@{$authUser.login}</div>
            <div class="text-secondary small">Signed in via GitHub</div>
          </div>
          <a href="/auth/logout" class="btn btn-outline-secondary btn-sm ms-auto">
            <i class="bi bi-box-arrow-right"></i> Logout
          </a>
        </div>
      {:else}
        <p class="text-secondary mb-2">Not signed in.</p>
        <a href="/auth/login" class="btn btn-dark btn-sm">
          <i class="bi bi-github"></i> Login with GitHub
        </a>
      {/if}
    </section>

    <hr />

    <!-- Starred PRs -->
    <section class="mb-5 mt-4">
      <h5 class="fw-semibold mb-3">Starred Pull Requests</h5>
      {#if starredCount === 0}
        <p class="text-secondary mb-2">You have no starred pull requests.</p>
      {:else}
        <p class="mb-2">
          You have <strong>{starredCount}</strong>
          starred pull request{starredCount === 1 ? '' : 's'}.
        </p>
      {/if}

      {#if !showClearStarredConfirm}
        <button
          class="btn btn-sm btn-outline-danger"
          disabled={starredCount === 0}
          on:click={() => showClearStarredConfirm = true}
        >
          <i class="bi bi-star"></i> Clear all starred
        </button>
      {:else}
        <div class="alert alert-warning py-2 px-3 d-inline-flex align-items-center gap-3">
          <span class="small">Are you sure? This will remove all starred PRs.</span>
          <button class="btn btn-sm btn-danger" on:click={confirmClearStarred}>Confirm</button>
          <button class="btn btn-sm btn-outline-secondary" on:click={() => showClearStarredConfirm = false}>Cancel</button>
        </div>
      {/if}
    </section>

    <hr />

    <!-- Ignored PRs -->
    <section class="mb-5 mt-4">
      <h5 class="fw-semibold mb-3">Ignored Pull Requests</h5>
      {#if ignoredCount === 0}
        <p class="text-secondary mb-2">You have no ignored pull requests.</p>
      {:else}
        <p class="mb-2">
          You have <strong>{ignoredCount}</strong>
          ignored pull request{ignoredCount === 1 ? '' : 's'}.
        </p>
      {/if}

      {#if !showClearIgnoredConfirm}
        <button
          class="btn btn-sm btn-outline-danger"
          disabled={ignoredCount === 0}
          on:click={() => showClearIgnoredConfirm = true}
        >
          <i class="bi bi-eye-slash"></i> Clear all ignored
        </button>
      {:else}
        <div class="alert alert-warning py-2 px-3 d-inline-flex align-items-center gap-3">
          <span class="small">Are you sure? This will un-ignore all hidden PRs.</span>
          <button class="btn btn-sm btn-danger" on:click={confirmClearIgnored}>Confirm</button>
          <button class="btn btn-sm btn-outline-secondary" on:click={() => showClearIgnoredConfirm = false}>Cancel</button>
        </div>
      {/if}
    </section>

    <hr />

    <!-- Notes -->
    <section class="mt-4">
      <h5 class="fw-semibold mb-3">Pull Request Notes</h5>
      {#if notesCount === 0}
        <p class="text-secondary mb-2">You have no notes on pull requests.</p>
      {:else}
        <p class="mb-0">
          You have notes on <strong>{notesCount}</strong>
          pull request{notesCount === 1 ? '' : 's'}.
        </p>
        <p class="text-secondary small mt-1">Notes can be edited directly on each PR card.</p>
      {/if}
    </section>
  </div>
</div>
