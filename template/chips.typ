// Small coloured blocks that stand for one item in the month grid.
#import "colors.typ": fallback-fill, fallback-ink, fallback-line, hatch, planned-fill, planned-ink, planned-line
#import "format.typ": dur

// The unpaid break of a visit, in brackets after the work time: "[+ 0h45 break]".
#let break-note(s, t) = {
  let b = s.minutes - s.work_minutes
  if b > 0 { [ \[+ #dur(b) #t.unpaid\]] }
}

// A planned or fallback visit: time range and work time (personal PDF).
#let work-chip(s, t) = {
  let (fill, line, ink) = if s.status == "planned" {
    (planned-fill, planned-line, planned-ink)
  } else {
    (fallback-fill, fallback-line, fallback-ink)
  }
  block(
    width: 100%, above: 0pt, below: 1.5pt,
    fill: fill, stroke: (left: 2pt + line),
    inset: (x: 2.5pt, y: 1.5pt),
    text(size: 6.8pt, fill: ink)[*#t.work #s.start–#s.end* #dur(s.work_minutes)#break-note(s, t)],
  )
}

// An office block for the supervisor: start and work time, no visit times.
#let boss-chip(b, t) = block(
  width: 100%, above: 0pt, below: 1.5pt,
  fill: planned-fill, stroke: (left: 2pt + planned-line),
  inset: (x: 2.5pt, y: 1.5pt),
  text(size: 6.8pt, fill: planned-ink)[*#t.office #b.start* #dur(b.minutes)],
)

// A lecture or exercise. Skipped sessions are hatched and labelled.
#let lecture-chip(it, t) = {
  let c = it.color
  block(
    width: 100%, above: 0pt, below: 1.5pt,
    fill: if it.skipped { hatch } else { c.fill },
    stroke: (left: 2pt + c.line),
    inset: (x: 2.5pt, y: 1.5pt),
    text(size: 6.8pt, fill: if it.skipped { luma(110) } else { c.line.darken(45%) })[
      *#it.start* #it.title#if it.skipped [ (#t.skipped)]
    ],
  )
}
