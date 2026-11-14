// The month grid: one cell per day with its lectures, work and hours.
#import "chips.typ": boss-chip, lecture-chip, work-chip
#import "colors.typ": fallback-ink, planned-day, planned-ink
#import "format.typ": add-days, dur, iso, monday-of, weeknum

// One day of the grid: its number, the hours (or the exam marker) and the items of the day.
#let month-cell(d, month, by-date, days-info, t, boss) = {
  let in-month = d.month() == month
  let items = if in-month and boss == none { by-date.at(iso(d), default: ()) } else { () }
  let info = days-info.at(iso(d), default: none)
  let blocks = if in-month and boss != none { boss.blocks.at(iso(d), default: ()) } else { () }
  let exam = boss != none and iso(d) in boss.exams
  let planned = if boss == none and info != none and info.status == "planned" { info.work_minutes } else { 0 }
  let fallback = if boss == none and info != none and info.status == "fallback" { info.work_minutes } else { 0 }
  let shaded = if boss != none { blocks.len() > 0 } else { planned > 0 }
  let fill = if not in-month { luma(248) } else if info != none and info.status == "outside" { luma(242) } else if shaded { planned-day } else { white }

  grid.cell(
    inset: 3pt,
    fill: fill,
    block(width: 100%, height: 100%, clip: true, {
      if in-month {
        grid(
          columns: (1fr, auto),
          text(size: 9pt, weight: "bold", fill: luma(90))[#d.day()],
          if boss != none {
            if exam { text(size: 8pt, weight: "bold", fill: luma(60))[#t.exam] }
          } else if planned > 0 {
            text(size: 8pt, weight: "bold", fill: planned-ink)[#dur(planned)]
          } else if fallback > 0 {
            text(size: 8pt, fill: fallback-ink)[#dur(fallback) #t.fallback]
          },
        )
        v(1pt)
        for b in blocks {
          boss-chip(b, t)
        }
        for it in items.sorted(key: it => it.start_min) {
          if it.kind == "work" {
            work-chip(it, t)
          } else {
            lecture-chip(it, t)
          }
        }
      }
    }),
  )
}

// Work of one calendar week (Monday to Sunday), in minutes: the planned visits, or the office
// blocks for the supervisor. Days outside the month still count, since the week is shown in full.
#let week-work-minutes(monday, days-info, boss) = {
  let dates = range(7).map(i => iso(add-days(monday, i)))
  if boss != none {
    dates.map(d => boss.blocks.at(d, default: ()).map(b => b.minutes).sum(default: 0)).sum(default: 0)
  } else {
    dates.map(d => {
      let info = days-info.at(d, default: none)
      if info != none and info.status == "planned" { info.work_minutes } else { 0 }
    }).sum(default: 0)
  }
}

// The month grid. `by-date`: items per ISO date (lectures and work), used for the personal PDF.
// `boss` = (blocks: by date, exams: dates) for the supervisor PDF; lectures and travel are left out.
#let month-page(year, month, by-date, days-info, days, t, title, boss: none) = {
  let first = datetime(year: year, month: month, day: 1)
  let next-first = if month == 12 { datetime(year: year + 1, month: 1, day: 1) } else {
    datetime(year: year, month: month + 1, day: 1)
  }
  let n-days = int(calc.round((next-first - first).days()))
  let start = monday-of(first)
  let n-weeks = calc.ceil((first.weekday() - 1 + n-days) / 7)

  [
    #text(size: 20pt, weight: "bold")[#t.months.at(month - 1) #year]
    #h(0.6em)
    #text(size: 12pt, fill: luma(110))[#title]
  ]
  v(0.3cm)

  // The grid fills whatever is left of the page.
  block(width: 100%, height: 1fr, layout(size => {
    let head-h = 0.6cm
    let wk-w = 1.25cm
    let row-h = (size.height - head-h - 0.1cm) / n-weeks
    grid(
      columns: (wk-w, ..(1fr,) * days.len()),
      rows: (head-h, ..(row-h,) * n-weeks),
      stroke: 0.4pt + luma(200),
      grid.cell(fill: luma(245))[],
      ..days.map(wd => grid.cell(fill: luma(245), align: center + horizon,
        text(weight: "bold", size: 9pt)[#t.days.at(wd - 1)])),
      ..range(n-weeks).map(w => {
        let monday = add-days(start, 7 * w)
        (
          grid.cell(fill: luma(245), align: center + top, inset: 3pt, {
            let total = week-work-minutes(monday, days-info, boss)
            [#text(size: 7.5pt, fill: luma(120))[#t.wk #weeknum(monday)]
            #if total > 0 [#linebreak()#text(size: 7.5pt, weight: "bold", fill: planned-ink)[#dur(total)]]]
          }),
          ..days.map(wd => month-cell(add-days(monday, wd - 1), month, by-date, days-info, t, boss)),
        )
      }).flatten(),
    )
  }))
}
