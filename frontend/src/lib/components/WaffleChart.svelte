<script>
  export let teams = []

  const COLORS = [
    '#2196f3', '#4caf50', '#ff9800', '#e91e63', '#9c27b0',
    '#00bcd4', '#ff5722', '#8bc34a', '#ffc107', '#3f51b5',
    '#009688', '#f44336', '#673ab7', '#cddc39', '#795548',
  ]

  const TOTAL_CELLS = 100

  $: cells = buildCells(teams)
  $: legend = buildLegend(teams)

  function buildCells(teams) {
    const total = teams.reduce((s, t) => s + t.needs_review_count, 0)
    if (total === 0) return []

    // Largest-remainder method
    const raws = teams.map((t, i) => ({
      index: i,
      name: t.name,
      count: t.needs_review_count,
      raw: (t.needs_review_count / total) * TOTAL_CELLS,
    }))

    const floors = raws.map(r => ({ ...r, cells: Math.floor(r.raw), remainder: r.raw - Math.floor(r.raw) }))
    let remaining = TOTAL_CELLS - floors.reduce((s, r) => s + r.cells, 0)

    floors
      .slice()
      .sort((a, b) => b.remainder - a.remainder)
      .slice(0, remaining)
      .forEach(r => { floors[r.index].cells += 1 })

    const result = []
    floors.forEach((r, i) => {
      const color = COLORS[i % COLORS.length]
      for (let c = 0; c < r.cells; c++) {
        result.push({ color, name: r.name, count: r.count })
      }
    })
    return result
  }

  function buildLegend(teams) {
    return teams
      .map((t, i) => ({ name: t.name, count: t.needs_review_count, color: COLORS[i % COLORS.length] }))
      .filter(t => t.count > 0)
      .sort((a, b) => b.count - a.count)
  }

  let hoveredTeam = null
</script>

<div class="row">
  <div class="col-md-8 col-sm-12 ">
    <div class="waffle-wrapper">
      {#if cells.length === 0}
        <p class="text-secondary small">No PRs currently awaiting review.</p>
      {:else}
        <div class="waffle-grid">
          {#each cells as cell}
            <div
              class="waffle-cell"
              role="img"
              aria-label="{cell.name}: {cell.count} waiting"
              style="background:{cell.color}"
              title="{cell.name}: {cell.count} waiting"
              on:mouseenter={() => hoveredTeam = cell.name}
              on:mouseleave={() => hoveredTeam = null}
            ></div>
          {/each}
        </div>
      {/if}
    </div>
  </div>
  <div class="col-sm-12 col-md-4">
    <div class="waffle-legend mt-2">
      {#each legend as item}
        <span class="legend-item" class:legend-item--active={hoveredTeam === item.name}>
          <span class="legend-swatch" style="background:{item.color};"></span>
          <span class="legend-label">{item.name} ({item.count})</span>
        </span>
      {/each}
    </div>
  </div>
</div>

<style>
  .waffle-grid {
    display: grid;
    grid-template-columns: repeat(20, 1fr);
    gap: 3px;
  }

  .waffle-cell {
    aspect-ratio: 1;
    border-radius: 2px;
    cursor: default;
    transition: opacity 0.1s;
  }

  .waffle-cell:hover {
    opacity: 0.75;
  }

  .waffle-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1rem;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    transition: font-size 0.2s ease, font-weight 0.2s ease;
  }

  .legend-item--active {
    font-size: 1.25em;
    font-weight: 700;
  }

  .legend-swatch {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 2px;
    flex-shrink: 0;
  }

  .legend-label {
    color: #444;
  }
</style>
