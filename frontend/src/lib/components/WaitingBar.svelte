<script>
  import { onMount, onDestroy } from 'svelte'
  import Plotly from 'plotly.js-dist-min'

  export let teams = []

  let container
  let chart

  function render() {
    if (!container || teams.length === 0) return

    const sorted = [...teams].sort((a, b) => b.needs_review_count - a.needs_review_count)

    const data = [{
      type: 'bar',
      orientation: 'h',
      x: sorted.map(t => t.needs_review_count),
      y: sorted.map(t => t.name),
      marker: { color: '#198754' },
      text: sorted.map(t => String(t.needs_review_count)),
      textposition: 'outside',
    }]

    const layout = {
      title: { text: 'PRs Awaiting Review', font: { size: 15 } },
      margin: { l: 80, r: 60, t: 50, b: 40 },
      xaxis: { title: 'Open PRs', zeroline: false },
      yaxis: { automargin: true },
      height: Math.max(200, sorted.length * 36 + 100),
      plot_bgcolor: '#fff',
      paper_bgcolor: '#fff',
    }

    if (chart) {
      Plotly.react(container, data, layout, { responsive: true })
    } else {
      chart = Plotly.newPlot(container, data, layout, { responsive: true })
    }
  }

  onMount(render)
  $: teams, render()

  onDestroy(() => {
    if (container) Plotly.purge(container)
  })
</script>

<div bind:this={container}></div>
