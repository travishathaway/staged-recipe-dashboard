<script>
  import { onMount } from 'svelte'
  import { getTeams, getScoreboard } from '../lib/api.js'

  const PERIODS = ['30d', '90d', '1y', '3y']
  const PERIOD_LABELS = { '30d': '30 days', '90d': '90 days', '1y': '1 year', '3y': '3 years' }

  let period = '90d'
  let selectedTeam = null
  let teams = []
  let scoreboard = null
  let loading = true
  let error = null

  onMount(async () => {
    try {
      teams = await getTeams()
    } catch (e) {
      // non-fatal: team filter just won't be populated
    }
    await fetchScoreboard()
  })

  async function fetchScoreboard() {
    loading = true
    error = null
    try {
      scoreboard = await getScoreboard(period, selectedTeam)
    } catch (e) {
      error = e.message
    } finally {
      loading = false
    }
  }

  function onPeriodChange(p) {
    period = p
    fetchScoreboard()
  }

  function onTeamChange(e) {
    selectedTeam = e.target.value || null
    fetchScoreboard()
  }

  function relativeTime(iso) {
    if (!iso) return '—'
    const ms = Date.now() - new Date(iso).getTime()
    const mins = Math.floor(ms / 60000)
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    const days = Math.floor(hrs / 24)
    if (days < 30) return `${days}d ago`
    const weeks = Math.floor(days / 7)
    if (weeks < 8) return `${weeks}w ago`
    return `${Math.floor(days / 30)}mo ago`
  }

  // Podium order: silver (2nd), gold (1st), bronze (3rd)
  $: top3 = scoreboard?.human_reviewers?.slice(0, 3) ?? []
  $: podium = [top3[1], top3[0], top3[2]].filter(Boolean)
  $: podiumMeta = [
    { rank: 2, label: 'silver', rankNum: '#2' },
    { rank: 1, label: 'gold',   rankNum: '#1' },
    { rank: 3, label: 'bronze', rankNum: '#3' },
  ]
  $: rest = scoreboard?.human_reviewers?.slice(3, 20) ?? []
</script>

<div style="max-width:960px">
  <h1 class="h4 fw-bold mb-4">Reviewer Scoreboard</h1>

  <div class="d-flex align-items-center gap-4 mb-4 flex-wrap">
    <div class="btn-group btn-group-sm" role="group" aria-label="Time period">
      {#each PERIODS as p}
        <button
          type="button"
          class="btn"
          class:btn-dark={period === p}
          class:btn-outline-secondary={period !== p}
          on:click={() => onPeriodChange(p)}
        >{PERIOD_LABELS[p]}</button>
      {/each}
    </div>

    <label class="d-flex align-items-center gap-2 small text-secondary">
      Team:
      <select class="form-select form-select-sm" style="width:auto" on:change={onTeamChange}>
        <option value="">All teams</option>
        {#each teams as team}
          <option value={team.name}>{team.name}</option>
        {/each}
      </select>
    </label>
  </div>

  {#if loading}
    <p class="text-secondary py-3">Loading…</p>
  {:else if error}
    <p class="text-danger py-3">Error: {error}</p>
  {:else if scoreboard}
    {#if !scoreboard.human_reviewers?.length}
      <p class="text-secondary">No review activity in this period.</p>
    {:else}

      <!-- Podium: silver | gold | bronze -->
      <div class="podium-row mb-5">
        {#each podium as r, i}
          {@const meta = podiumMeta[i]}
          <div class="podium-card {meta.label}">
            <div class="avatar-wrap">
              <div class="avatar-frame">
                <img
                  class="avatar"
                  src="https://github.com/{r.login}.png?size=100"
                  alt="{r.login} avatar"
                />
                <div class="rank-badge">{meta.rankNum}</div>
              </div>
              <a
                class="login-link"
                href="https://github.com/{r.login}"
                target="_blank"
                rel="noreferrer"
              >{r.login}</a>
            </div>
            <a
              class="login-link login-link-desktop"
              href="https://github.com/{r.login}"
              target="_blank"
              rel="noreferrer"
            >{r.login}</a>
            <div class="stats">
              <div class="stat">
                <span class="stat-value total">{r.formal_reviews}</span>
                <span class="stat-label">Reviews</span>
              </div>
              <div class="stat">
                <span class="stat-value approved">{r.approved}</span>
                <span class="stat-label">Approved</span>
              </div>
              <div class="stat">
                <span class="stat-value changes">{r.changes_requested}</span>
                <span class="stat-label">Changes</span>
              </div>
              <div class="stat">
                <span class="stat-value comments">{r.review_comments}</span>
                <span class="stat-label">Comments</span>
              </div>
            </div>
          </div>
        {/each}
      </div>

      <!-- Ranks 4–20 table -->
      {#if rest.length}
        <div class="table-responsive">
          <table class="table table-hover">
            <thead class="table-light">
              <tr>
                <th class="rank-col">#</th>
                <th>Reviewer</th>
                <th class="num">Reviews</th>
                <th class="num approved">Approved</th>
                <th class="num changes">Changes Requested</th>
                <th class="num comments">Comments</th>
                <th>Last Active</th>
              </tr>
            </thead>
            <tbody>
              {#each rest as r, i}
                <tr>
                  <td class="rank-col text-secondary">{i + 4}</td>
                  <td class="login">
                    <img
                      class="avatar-sm"
                      src="https://github.com/{r.login}.png?size=40"
                      alt="{r.login} avatar"
                    />
                    <a href="https://github.com/{r.login}" target="_blank" rel="noreferrer">{r.login}</a>
                  </td>
                  <td class="num total">{r.formal_reviews}</td>
                  <td class="num approved">{r.approved}</td>
                  <td class="num changes">{r.changes_requested}</td>
                  <td class="num comments">{r.review_comments}</td>
                  <td class="ts">{relativeTime(r.last_active)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}

    {/if}
  {/if}
</div>

<style>
  /* ── Podium layout ───────────────────────────────────────────── */
  .podium-row {
    display: flex;
    align-items: flex-end;
    justify-content: center;
    gap: 1rem;
  }

  .podium-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    border-radius: 12px;
    padding: 1.25rem 1rem;
    text-align: center;
    border: 2px solid transparent;
    transition: transform 0.15s ease;
  }

  .podium-card:hover {
    transform: translateY(-3px);
  }

  .gold   { background: #fffdf0; border-color: #FFD700; width: 240px; order: 2; }
  .silver { background: #f8f8f8; border-color: #C0C0C0; width: 210px; order: 1; }
  .bronze { background: #fdf6f0; border-color: #CD7F32; width: 210px; order: 3; }

  /* ── Avatar wrapper — positions the rank badge over the avatar ── */
  .avatar-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.25rem;
    flex-shrink: 0;
  }

  /* Inner frame provides the positioning context for the badge */
  .avatar-frame {
    position: relative;
    display: inline-block;
  }

  /* On desktop hide the login-link that lives inside avatar-wrap;
     the desktop duplicate outside is shown instead */
  .avatar-wrap .login-link {
    display: none;
  }

  /* Desktop duplicate link */
  .login-link-desktop {
    display: block;
  }

  .avatar {
    border-radius: 50%;
    display: block;
    border: 3px solid transparent;
  }

  .gold   .avatar { width: 80px; height: 80px; border-color: #FFD700; }
  .silver .avatar { width: 68px; height: 68px; border-color: #C0C0C0; }
  .bronze .avatar { width: 68px; height: 68px; border-color: #CD7F32; }

  .rank-badge {
    position: absolute;
    bottom: 0;
    right: -4px;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    padding: 2px 6px;
    border-radius: 999px;
    line-height: 1.4;
    border: 2px solid #fff;
  }

  .gold   .rank-badge { background: #FFD700; color: #5a4200; }
  .silver .rank-badge { background: #C0C0C0; color: #3a3a3a; }
  .bronze .rank-badge { background: #CD7F32; color: #fff; }

  .login-link {
    font-weight: 600;
    font-size: 0.9rem;
    color: #0d6efd;
    text-decoration: none;
    margin-bottom: 0.85rem;
    word-break: break-all;
  }
  .login-link:hover { text-decoration: underline; }

  .stats {
    display: flex;
    gap: 0.6rem;
    justify-content: center;
    flex-wrap: wrap;
  }

  .stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 46px;
  }

  .stat-value {
    font-size: 1.1rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    line-height: 1.1;
  }

  .stat-label {
    font-size: 0.65rem;
    color: #6c757d;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-top: 2px;
  }

  /* ── Mobile: stack gold/silver/bronze, avatar left + username below, stats right ── */
  @media (max-width: 600px) {
    .podium-row {
      flex-direction: column;
      align-items: stretch;
    }

    .gold, .silver, .bronze {
      width: 100%;
      order: unset;
      flex-direction: row;
      align-items: flex-start;
      flex-wrap: wrap;
      gap: 0.75rem;
      text-align: left;
      padding: 0.85rem 1rem;
    }
    .gold   { order: 1; }
    .silver { order: 2; }
    .bronze { order: 3; }

    /* Left column: avatar (with badge) + username stacked */
    .gold   .avatar-wrap,
    .silver .avatar-wrap,
    .bronze .avatar-wrap {
      margin-bottom: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0.35rem;
    }

    /* All avatars same size on mobile */
    .gold   .avatar,
    .silver .avatar,
    .bronze .avatar {
      width: 64px;
      height: 64px;
    }

    /* Username sits below the avatar inside avatar-wrap on mobile */
    .avatar-wrap .login-link {
      display: block;
      font-size: 0.78rem;
      margin-bottom: 0;
      text-align: center;
      max-width: 72px;
      overflow-wrap: break-word;
    }

    /* Hide the desktop duplicate link on mobile */
    .login-link-desktop {
      display: none;
    }

    /* Stats fill remaining width to the right */
    .stats {
      flex: 1;
      justify-content: flex-start;
      align-content: center;
      align-self: center;
    }
  }

  /* ── Table ───────────────────────────────────────────────────── */
  .rank-col { width: 2.5rem; color: #6c757d; font-variant-numeric: tabular-nums; }

  .login {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .login a { color: #0d6efd; text-decoration: none; font-weight: 500; }
  .login a:hover { text-decoration: underline; }

  .avatar-sm {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  :global(tbody tr td) { padding-top: 0.65rem !important; padding-bottom: 0.65rem !important; }

  .num { text-align: right; font-variant-numeric: tabular-nums; }
  .total { font-weight: 600; }
  .approved { color: #198754; }
  .changes  { color: #fd7e14; }
  .comments { color: #0d6efd; }

  .ts { color: #6c757d; white-space: nowrap; font-size: 0.82rem; }
</style>
