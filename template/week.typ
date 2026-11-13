// One week as a time grid: lectures, travel and work.
#import "colors.typ": car-fill, fallback-fill, fallback-ink, fallback-line, hatch, planned-fill, planned-ink, planned-line, travel-fill, travel-ink, travel-line
#import "chips.typ": break-note
#import "data.typ": index-by-date, detail-line, room-label
#import "format.typ": add-days, day-eval, dur, fmt-date, fmt-date-long, fmt-date-short, hm, iso, leg-text, parse-date, signed-dur

// The title line: week number, dates, planned and fallback hours, target, fuel.
#let week-title(week, days, t) = {
  let monday = parse-date(week.monday)
  let target = week.target_minutes
  [
    #text(size: 20pt, weight: "bold")[#t.week #week.week]
    #h(0.6em)
    #text(size: 12pt, fill: luma(110))[
      #fmt-date(monday, t) – #fmt-date-long(add-days(monday, days.last() - 1), t)
    ]
    #h(1fr)
    #text(size: 10pt, weight: "bold", fill: planned-ink)[#t.planned: #dur(week.planned_minutes)]
    #if week.fallback_minutes > 0 [
      #text(size: 9pt, fill: fallback-ink)[ · #t.fallback #dur(week.fallback_minutes)]
    ]
    #if target != none [
      #text(size: 9pt, fill: luma(110))[ (#t.target #dur(target), #t.delta #signed-dur(week.planned_minutes - target))]
    ]
    #if week.fuel_eur != none [
      #text(size: 9pt, fill: luma(110))[ · #t.cfg.fuel ~#calc.round(week.fuel_eur, digits: 2) EUR]
    ]
  ]
}

// The sizes of the grid. The hour height shrinks to fit the page height, up to 1.7 cm.
#let week-geometry(width, height, days, hours) = {
  let (start-h, end-h) = hours
  let n-hours = end-h - start-h
  let time-w = 1.1cm
  let head-h = 1.25cm
  let col-w = (width - time-w) / days.len()
  let hour-h = calc.min(1.7cm, (height - head-h - 0.1cm) / n-hours)
  (
    width: width, start-h: start-h, end-h: end-h,
    time-w: time-w, head-h: head-h, col-w: col-w,
    hour-h: hour-h, grid-h: hour-h * n-hours,
  )
}

// Vertical position of a time of day (minutes after midnight) on the grid.
#let y-at(g, minutes) = g.head-h + (minutes - g.start-h * 60) / 60 * g.hour-h

// Days outside the calendar range are shaded and carry no plan.
#let week-shading(days, monday, days-info, g) = {
  for (i, wd) in days.enumerate() {
    let info = days-info.at(iso(add-days(monday, wd - 1)), default: none)
    if info != none and info.status == "outside" {
      place(top + left, dx: g.time-w + i * g.col-w, dy: g.head-h,
        rect(width: g.col-w, height: g.grid-h, fill: luma(242), stroke: none))
    }
  }
}

// The header of one day: name and date, planned or fallback work, and the evaluation of the plan.
#let day-header(i, wd, monday, days-info, t, g) = {
  let d = add-days(monday, wd - 1)
  let info = days-info.at(iso(d), default: none)
  let status-line = if info == none {
    none
  } else if info.status == "outside" {
    text(size: 7.5pt, fill: luma(150))[#t.outside]
  } else if info.status == "planned" {
    text(size: 8pt, weight: "bold", fill: planned-ink)[#t.planned #dur(info.work_minutes)]
  } else if info.status == "fallback" {
    text(size: 8pt, weight: "bold", fill: fallback-ink)[#t.fallback #dur(info.work_minutes)]
  } else if info.best != none {
    text(size: 7.5pt, fill: luma(110))[#t.possible #dur(info.best.work_minutes)]
  } else {
    text(size: 7.5pt, fill: luma(110))[#t.no-work]
  }
  place(top + left, dx: g.time-w + i * g.col-w,
    box(width: g.col-w, height: g.head-h, align(center + horizon)[
      #text(weight: "bold", size: 10pt)[#t.days.at(wd - 1)]
      #text(size: 9pt, fill: luma(110))[#h(0.4em) #fmt-date-short(d, t)]
      #linebreak()
      #status-line
      #if info != none and info.drawn != none and info.status != "none" [
        #linebreak()#text(size: 7pt, fill: luma(110))[#day-eval(info.drawn, t)]
      ]
    ]))
}

// Hour lines with their labels, and dotted half-hour lines.
#let hour-lines(g) = {
  for h in range(g.start-h, g.end-h + 1) {
    let y = y-at(g, h * 60)
    place(top + left, dy: y, line(length: 100%, stroke: 0.4pt + luma(205)))
    place(top + left, dy: y - 5pt, box(width: g.time-w - 4pt, align(right,
      text(size: 8pt, fill: luma(120))[#hm(h * 60)])))
    if h < g.end-h {
      place(top + left, dx: g.time-w, dy: y + g.hour-h / 2,
        line(length: g.width - g.time-w, stroke: (paint: luma(235), thickness: 0.4pt, dash: "dotted")))
    }
  }
}

#let day-separators(days, g) = {
  for i in range(days.len() + 1) {
    place(top + left, dx: g.time-w + i * g.col-w, dy: g.head-h,
      line(angle: 90deg, length: g.grid-h, stroke: 0.4pt + luma(205)))
  }
}

// A travel leg. Car: solid; transit: dotted outline.
#let travel-block(leg, x, g, t) = {
  let h = (leg.end_min - leg.start_min) / 60 * g.hour-h
  let car = leg.mode == "car"
  place(top + left, dx: x + 2pt, dy: y-at(g, leg.start_min) + 0.5pt,
    block(
      width: g.col-w - 4pt, height: h - 1pt,
      fill: if car { car-fill } else { travel-fill },
      stroke: (left: 1.2pt + travel-line, rest: if car { none } else { (paint: travel-line, thickness: 0.5pt, dash: "dotted") }),
      inset: (x: 3pt, y: 1pt), clip: true,
      align(horizon, text(size: 6.8pt, fill: travel-ink, style: "italic")[
        #leg-text(leg, t) · #(leg.end_min - leg.start_min) min
      ]),
    ))
}

// A visit: planned work in strong green, fallback in a lighter tone. Break in brackets.
#let work-block(s, x, g, t) = {
  let planned = s.status == "planned"
  let h = (s.end_min - s.start_min) / 60 * g.hour-h
  place(top + left, dx: x + 2pt, dy: y-at(g, s.start_min) + 1pt,
    block(
      width: g.col-w - 4pt, height: h - 2pt,
      fill: if planned { planned-fill } else { fallback-fill },
      stroke: if planned { 1.4pt + planned-line } else { 1pt + fallback-line },
      radius: 3pt,
      inset: (x: 4pt, y: 3pt), clip: true,
      {
        set par(leading: 0.35em, spacing: 0.35em)
        set text(size: 8pt, fill: if planned { planned-ink } else { fallback-ink })
        text(weight: "bold")[#if planned { t.planned } else { t.fallback } #s.start–#s.end]
        linebreak()
        text(size: 7.5pt, weight: "bold")[#dur(s.work_minutes) #t.work#break-note(s, t)]
      },
    ))
}

// A lecture or exercise. Attended ones share the column in lanes; skipped ones are a narrow
// hatched strip on the right edge.
#let lecture-block(e, x, g, t) = {
  let c = e.color
  let lane-w = if e.skipped { g.col-w * 0.36 } else { g.col-w / e.lanes }
  let lane-x = if e.skipped { g.col-w * 0.64 } else { e.lane * lane-w }
  let h = (e.end_min - e.start_min) / 60 * g.hour-h
  place(top + left,
    dx: x + lane-x + 1pt,
    dy: y-at(g, e.start_min) + 0.5pt,
    block(
      width: lane-w - 2pt, height: h - 1pt,
      fill: if e.skipped { hatch } else { c.fill },
      stroke: (left: 2.5pt + c.line,
        rest: if e.skipped { (paint: c.line, thickness: 0.5pt, dash: "dashed") } else { none }),
      radius: (right: 2pt),
      inset: (x: 4pt, y: 3pt), clip: true,
      {
        set par(leading: 0.35em, spacing: 0.35em)
        set text(size: 8pt, fill: if e.skipped { luma(110) } else { c.line.darken(55%) })
        text(weight: "bold")[#e.title]
        linebreak()
        text(size: 7pt)[#e.start–#e.end · #detail-line(e, t)]
        let r = room-label(e)
        if r != none {
          linebreak()
          text(size: 7pt)[#r]
        }
        if e.skipped {
          linebreak()
          text(size: 7pt, style: "italic")[#t.skipped]
        }
      },
    ))
}

// The page: week title with the hours, then the time grid.
#let week-page(week, events, slots, legs, days-info, days, hours, color-of, t, title) = {
  let monday = parse-date(week.monday)
  week-title(week, days, t)
  v(0.2cm)

  block(width: 100%, height: 1fr, layout(size => {
    let g = week-geometry(size.width, size.height, days, hours)
    let by-day-events = index-by-date(events)
    let by-day-slots = index-by-date(slots)
    let by-day-legs = index-by-date(legs)

    block(width: 100%, height: g.head-h + g.grid-h, {
      week-shading(days, monday, days-info, g)
      for (i, wd) in days.enumerate() {
        day-header(i, wd, monday, days-info, t, g)
      }
      hour-lines(g)
      day-separators(days, g)

      for (i, wd) in days.enumerate() {
        let key = iso(add-days(monday, wd - 1))
        let x = g.time-w + i * g.col-w
        // travel first, behind everything else; then work; lectures last so they stay on top
        for leg in by-day-legs.at(key, default: ()) {
          travel-block(leg, x, g, t)
        }
        for s in by-day-slots.at(key, default: ()) {
          work-block(s, x, g, t)
        }
        for e in by-day-events.at(key, default: ()).sorted(key: e => if e.skipped { 1 } else { 0 }) {
          lecture-block(e, x, g, t)
        }
      }
    })
  }))
}
