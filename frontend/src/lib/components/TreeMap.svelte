<script>
  import { hierarchy, treemap, treemapSquarify } from 'd3-hierarchy'

  export let teams = []

  const COLORS = [
    '#2196f3', '#4caf50', '#ff9800', '#e91e63', '#9c27b0',
    '#00bcd4', '#ff5722', '#8bc34a', '#ffc107', '#3f51b5',
    '#009688', '#f44336', '#673ab7', '#cddc39', '#795548',
  ]

  const HEIGHT = 160

  let containerWidth = 0
  let hoveredTeam = null

  $: colorMap = Object.fromEntries(teams.map((t, i) => [t.name, COLORS[i % COLORS.length]]))
  $: total = teams.reduce((s, t) => s + t.needs_review_count, 0)
  $: leaves = total > 0 && containerWidth > 0 ? buildLeaves(teams, containerWidth) : []
  $: hiddenLeaves = leaves.filter(n => !(n.x1 - n.x0 > 44 && n.y1 - n.y0 > 28))

  function buildLeaves(teams, width) {
    const root = hierarchy({ name: 'root', children: teams })
      .sum(d => d.needs_review_count ?? 0)
      .sort((a, b) => b.value - a.value)

    treemap()
      .size([width, HEIGHT])
      .paddingInner(3)
      .paddingOuter(2)
      .round(true)
      .tile(treemapSquarify)(root)

    return root.leaves()
  }

  function labelColor(hex) {
    const r = parseInt(hex.slice(1, 3), 16)
    const g = parseInt(hex.slice(3, 5), 16)
    const b = parseInt(hex.slice(5, 7), 16)
    return (r * 299 + g * 587 + b * 114) / 1000 > 145 ? '#333' : '#fff'
  }
</script>

<div bind:clientWidth={containerWidth}>
  {#if total === 0}
    <p class="text-secondary small">No PRs currently awaiting review.</p>
  {:else if containerWidth > 0}
    <svg width={containerWidth} height={HEIGHT}>
      <defs>
        {#each leaves as node, i}
          <clipPath id="treemap-clip-{i}">
            <rect x={node.x0} y={node.y0} width={node.x1 - node.x0} height={node.y1 - node.y0} />
          </clipPath>
        {/each}
      </defs>

      {#each leaves as node, i}
        {@const w = node.x1 - node.x0}
        {@const h = node.y1 - node.y0}
        {@const color = colorMap[node.data.name]}
        {@const fg = labelColor(color)}
        {@const showText = w > 44 && h > 28}
        <g
          role="img"
          aria-label="{node.data.name}: {node.value} waiting"
          style="opacity:{hoveredTeam && hoveredTeam !== node.data.name ? 0.65 : 1};transition:opacity 0.15s ease"
          on:mouseenter={() => hoveredTeam = node.data.name}
          on:mouseleave={() => hoveredTeam = null}
        >
          <rect
            x={node.x0} y={node.y0}
            width={w} height={h}
            fill={color}
            rx="3"
          >
            <title>{node.data.name}: {node.value} waiting</title>
          </rect>
          {#if showText}
            <text
              clip-path="url(#treemap-clip-{i})"
              x={node.x0 + 6}
              y={node.y0 + 15}
              fill={fg}
              font-size="14"
              font-family="inherit"
              pointer-events="none"
            >
              <tspan font-weight="600">{node.data.name}</tspan>
              <tspan x={node.x0 + 6} dy="1.3em" font-size="13" opacity="0.85">{node.value}</tspan>
            </text>
          {/if}
        </g>
      {/each}
    </svg>
  {/if}

  {#if hiddenLeaves.length > 0}
    <div class="treemap-legend mt-2">
      {#each hiddenLeaves as node}
        {@const color = colorMap[node.data.name]}
        <span
          class="legend-item"
          class:legend-item--active={hoveredTeam === node.data.name}
          on:mouseenter={() => hoveredTeam = node.data.name}
          on:mouseleave={() => hoveredTeam = null}
          role="img"
          aria-label="{node.data.name}: {node.value} waiting"
        >
          <span class="legend-swatch" style="background:{color}"></span>
          <span class="legend-label">{node.data.name} ({node.value})</span>
        </span>
      {/each}
    </div>
  {/if}
</div>

<style>
  .treemap-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem 0.9rem;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    cursor: default;
    transition: font-size 0.2s ease, font-weight 0.2s ease;
  }

  .legend-item--active {
    font-size: 1.1em;
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
    font-size: 0.8rem;
  }
</style>
