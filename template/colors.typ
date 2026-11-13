// Colours of the planner. Planned and fallback work are green (work, not travel);
// travel is grey; skipped sessions are hatched.

// One entry per course (by LV number). `fill` is the block background,
// `line` the accent stripe; text uses a darkened `line`.
#let palette = (
  (fill: rgb("#dbe7fb"), line: rgb("#2f6fdd")),
  (fill: rgb("#fde3cc"), line: rgb("#e07a1f")),
  (fill: rgb("#d5f0dc"), line: rgb("#2f9e55")),
  (fill: rgb("#ead9f7"), line: rgb("#8e4fc4")),
  (fill: rgb("#fbd9d9"), line: rgb("#d64545")),
  (fill: rgb("#d2eeef"), line: rgb("#1f9ba3")),
  (fill: rgb("#fbefc4"), line: rgb("#c99a06")),
  (fill: rgb("#fbd8ea"), line: rgb("#d03c8a")),
  (fill: rgb("#dcdff7"), line: rgb("#4a55c9")),
  (fill: rgb("#e3eecb"), line: rgb("#6f9a1c")),
)

// Planned work: strong green. Fallback: a lighter green tone.
#let planned-fill = rgb("#c9f2d6")
#let planned-line = rgb("#16833f")
#let planned-ink = rgb("#0c5a2a")
#let planned-day = rgb("#f1fbf4")
#let fallback-fill = rgb("#eefaf2")
#let fallback-line = rgb("#8fd1a7")
#let fallback-ink = rgb("#3f7d58")

// Travel: neutral grey. A car leg is solid, a transit leg dotted.
#let travel-fill = luma(236)
#let car-fill = luma(222)
#let travel-line = luma(150)
#let travel-ink = luma(85)

// Skipped sessions: hatched and faded.
#let hatch = tiling(size: (4pt, 4pt), {
  place(top + left, line(start: (0pt, 0pt), end: (4pt, 4pt), stroke: 0.5pt + luma(185)))
})
