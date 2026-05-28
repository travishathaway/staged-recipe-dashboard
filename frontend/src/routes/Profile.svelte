<script>
  import { preferences } from '../lib/store.js'

  // --- Username section ---
  let draftUsername = $preferences.profile.githubUsername || ''
  let saved = false
  let saveTimer = null

  function saveUsername() {
    preferences.setUsername(draftUsername.trim())
    saved = true
    clearTimeout(saveTimer)
    saveTimer = setTimeout(() => { saved = false }, 2000)
  }

  // --- Starred PRs section ---
  let showClearConfirm = false

  function confirmClear() {
    preferences.clearStarred()
    showClearConfirm = false
  }

  // --- Export / Import section ---
  let fileInput
  let importConfirmText = null   // non-null when awaiting user confirmation
  let importError = null
  let importSuccess = false
  let importSuccessTimer = null

  function handleExport() {
    preferences.exportJSON()
  }

  function triggerImport() {
    importError = null
    fileInput.click()
  }

  function handleFileChange(e) {
    const file = e.target.files[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      const text = ev.target.result
      try {
        // Validate it parses and has a version field before prompting
        const parsed = JSON.parse(text)
        if (typeof parsed.version !== 'number') throw new Error('Not a valid settings file.')

        const hasData = $preferences.profile.githubUsername || Object.keys($preferences.starred.prs).length > 0
        if (hasData) {
          importConfirmText = text
        } else {
          doImport(text)
        }
      } catch (err) {
        importError = err.message || 'Failed to read file.'
      }
    }
    reader.readAsText(file)
    // Reset input so the same file can be re-selected if needed
    e.target.value = ''
  }

  function doImport(text) {
    try {
      preferences.importJSON(text)
      importConfirmText = null
      importError = null
      importSuccess = true
      clearTimeout(importSuccessTimer)
      importSuccessTimer = setTimeout(() => { importSuccess = false }, 2000)
      // Sync draftUsername to newly imported value
      draftUsername = $preferences.profile.githubUsername || ''
    } catch (err) {
      importConfirmText = null
      importError = err.message || 'Import failed.'
    }
  }

  function cancelImport() {
    importConfirmText = null
  }
</script>

<div class="row justify-content-center">
  <div class="col-12 col-md-7 col-lg-6">
    <h2 class="mb-4">Profile</h2>

    <!-- GitHub Username -->
    <section class="mb-5">
      <h5 class="fw-semibold mb-3">GitHub Username</h5>
      <div class="d-flex gap-2 align-items-center">
        <input
          type="text"
          class="form-control"
          placeholder="e.g. octocat"
          bind:value={draftUsername}
          on:keydown={(e) => e.key === 'Enter' && saveUsername()}
          style="max-width: 260px"
        />
        <button class="btn btn-primary" on:click={saveUsername}>Save</button>
        {#if saved}
          <span class="text-success small"><i class="bi bi-check-circle-fill"></i> Saved</span>
        {/if}
      </div>
      <p class="text-secondary small mt-2 mb-0">
        Used to show your GitHub avatar in the nav.
      </p>
    </section>

    <hr />

    <!-- Starred PRs -->
    <section class="mb-5 mt-4">
      <h5 class="fw-semibold mb-3">Starred Pull Requests</h5>
      {#if Object.keys($preferences.starred.prs).length === 0}
        <p class="text-secondary mb-2">You have no starred pull requests.</p>
      {:else}
        {@const count = Object.keys($preferences.starred.prs).length}
        <p class="mb-2">
          You have <strong>{count}</strong>
          starred pull request{count === 1 ? '' : 's'}.
        </p>
      {/if}

      {#if !showClearConfirm}
        <button
          class="btn btn-sm btn-outline-danger"
          disabled={Object.keys($preferences.starred.prs).length === 0}
          on:click={() => showClearConfirm = true}
        >
          <i class="bi bi-star"></i> Clear all starred
        </button>
      {:else}
        <div class="alert alert-warning py-2 px-3 d-inline-flex align-items-center gap-3">
          <span class="small">Are you sure? This will remove all starred PRs.</span>
          <button class="btn btn-sm btn-danger" on:click={confirmClear}>Confirm</button>
          <button class="btn btn-sm btn-outline-secondary" on:click={() => showClearConfirm = false}>Cancel</button>
        </div>
      {/if}
    </section>

    <hr />

    <!-- Export & Import -->
    <section class="mt-4">
      <h5 class="fw-semibold mb-3">Export &amp; Import</h5>
      <div class="d-flex gap-2 flex-wrap align-items-center">
        <button class="btn btn-outline-secondary" on:click={handleExport}>
          <i class="bi bi-download"></i> Export settings
        </button>
        <button class="btn btn-outline-secondary" on:click={triggerImport}>
          <i class="bi bi-upload"></i> Import settings
        </button>
        <input
          bind:this={fileInput}
          type="file"
          accept=".json"
          class="d-none"
          on:change={handleFileChange}
        />
        {#if importSuccess}
          <span class="text-success small"><i class="bi bi-check-circle-fill"></i> Imported</span>
        {/if}
      </div>

      {#if importConfirmText}
        <div class="alert alert-warning mt-3 py-2 px-3">
          <p class="mb-2 small fw-semibold">
            Importing will delete all your current settings on this site. Continue?
          </p>
          <div class="d-flex gap-2">
            <button class="btn btn-sm btn-danger" on:click={() => doImport(importConfirmText)}>Import</button>
            <button class="btn btn-sm btn-outline-secondary" on:click={cancelImport}>Cancel</button>
          </div>
        </div>
      {/if}

      {#if importError}
        <div class="alert alert-danger mt-3 py-2 px-3 small">{importError}</div>
      {/if}

      <p class="text-secondary small mt-3 mb-0">
        Export saves your profile and starred PRs as a JSON file you can import on another device.
        Import replaces all current settings.
      </p>
    </section>
  </div>
</div>
