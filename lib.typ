// Planner template: lectures, travel and possible work slots.
// Input: the JSON written by scripts/plan.py (see README). Typst only draws;
// all the interval maths happens in Python.

// ---------------------------------------------------------------- labels ---

#let i18n = (
  en: (
    months: ("January", "February", "March", "April", "May", "June", "July",
      "August", "September", "October", "November", "December"),
    days: ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
    days-short: ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    week: "Week", wk: "Wk", ord: "",
    overview: "Overview",
    settings: "Settings used",
    courses: "Courses",
    hours: "Possible work per week",
    course: "Course", kind: "Type", group: "Group", times: "Times", room: "Room",
    sessions: "Sessions", period: "Period",
    lectures: "Lectures", possible: "Possible work", target: "Target", delta: "vs. target",
    work: "Work", skipped: "skipped", nothing: "none", every-day: "every day",
    default-group: "Standardgruppe",
    types: (VO: "Lecture", UE: "Exercise", VU: "Lecture + Exercise",
      VI: "Lecture + Exercise", PR: "Lab", SE: "Seminar", PS: "Proseminar",
      KO: "Colloquium", RE: "Revision course"),
    travel: (
      home-to-tum: "Home → TUM", tum-to-job: "TUM → job", job-to-tum: "job → TUM",
      home-to-job: "Home → job", job-to-home: "job → home", tum-to-home: "TUM → home",
    ),
    cfg: (
      home-to-tum: "Home → TUM", tum-to-job: "TUM → job", job-to-tum: "Job → TUM",
      home-to-job: "Home → job (first morning)", job-to-home: "Job → home",
      wake: "Earliest wake-up", ready: "Ready after wake-up", latest: "Latest at job",
      earliest-job: "Earliest at job", min-block: "Shortest work block",
      max-block: "Longest work block", buffer: "Buffer next to lectures",
      work-days: "Work days", target: "Weekly target", not-attended: "Courses not attended",
      sessions: "Sessions not attended", show-skipped: "Skipped sessions in PDF",
      no-work: "No-work dates", overrides: "Day overrides",
    ),
    yes: "shown", hidden: "hidden",
    generated: "Generated from a TUMonline export on",
  ),
  de: (
    months: ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
      "August", "September", "Oktober", "November", "Dezember"),
    days: ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"),
    days-short: ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"),
    week: "KW", wk: "KW", ord: ".",
    overview: "Übersicht",
    settings: "Verwendete Einstellungen",
    courses: "Lehrveranstaltungen",
    hours: "Mögliche Arbeitszeit pro Woche",
    course: "Lehrveranstaltung", kind: "Art", group: "Gruppe", times: "Zeiten", room: "Raum",
    sessions: "Termine", period: "Zeitraum",
    lectures: "Vorlesungen", possible: "Mögliche Arbeit", target: "Ziel", delta: "vs. Ziel",
    work: "Arbeit", skipped: "übersprungen", nothing: "keine", every-day: "jeden Tag",
    default-group: "Standardgruppe",
    types: (VO: "Vorlesung", UE: "Übung", VU: "Vorlesung + Übung",
      VI: "Vorlesung + Übung", PR: "Praktikum", SE: "Seminar", PS: "Proseminar",
      KO: "Kolloquium", RE: "Repetitorium"),
    travel: (
      home-to-tum: "Zuhause → TUM", tum-to-job: "TUM → Job", job-to-tum: "Job → TUM",
      home-to-job: "Zuhause → Job", job-to-home: "Job → Zuhause", tum-to-home: "TUM → Zuhause",
    ),
    cfg: (
      home-to-tum: "Zuhause → TUM", tum-to-job: "TUM → Job", job-to-tum: "Job → TUM",
      home-to-job: "Zuhause → Job (erster Morgen)", job-to-home: "Job → Zuhause",
      wake: "Frühestes Aufstehen", ready: "Fertig machen nach dem Aufstehen",
      latest: "Spätestens im Job", earliest-job: "Frühestens im Job",
      min-block: "Kürzester Arbeitsblock", max-block: "Längster Arbeitsblock",
      buffer: "Puffer neben Vorlesungen", work-days: "Arbeitstage",
      target: "Wochenziel", not-attended: "Nicht besuchte Veranstaltungen",
      sessions: "Nicht besuchte Termine", show-skipped: "Übersprungene im PDF",
      no-work: "Tage ohne Arbeit", overrides: "Tages-Ausnahmen",
    ),
    yes: "angezeigt", hidden: "ausgeblendet",
    generated: "Erstellt aus einem TUMonline-Export am",
  ),
)

// One entry per course (by LV number). `fill` is the block background,
// `line` the accent stripe, text uses a darkened `line`.
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

// Work slots are the colour of the planner: green with a strong outline.
#let work-fill = rgb("#c9f2d6")
#let work-day-fill = rgb("#f1fbf4")
#let work-line = rgb("#16833f")
#let work-ink = rgb("#0c5a2a")
// Travel is neutral grey.
#let travel-fill = luma(236)
#let travel-line = luma(150)
#let travel-ink = luma(85)
// Skipped sessions: hatched and faded.
#let hatch = tiling(size: (4pt, 4pt), {
  place(top + left, line(start: (0pt, 0pt), end: (4pt, 4pt), stroke: 0.5pt + luma(185)))
})

// -------------------------------------------------------------- helpers ---

#let parse-date(s) = {
  let p = s.split("-").map(int)
  datetime(year: p.at(0), month: p.at(1), day: p.at(2))
}
#let iso(d) = d.display("[year]-[month]-[day]")
#let weeknum(d) = int(d.display("[week_number]"))
#let monday-of(d) = d - duration(days: d.weekday() - 1)
#let add-days(d, n) = d + duration(days: n)
// Minutes after midnight -> "08:05"
#let hm(m) = {
  let h = calc.quo(m, 60)
  let mi = calc.rem(m, 60)
  (if h < 10 { "0" } else { "" }) + str(h) + ":" + (if mi < 10 { "0" } else { "" }) + str(mi)
}
// Minutes -> "4h05"
#let dur(m) = {
  let mi = calc.rem(m, 60)
  str(calc.quo(m, 60)) + "h" + (if mi < 10 { "0" } else { "" }) + str(mi)
}
// Minutes -> "+0h30" / "−0h30"
#let signed-dur(m) = if m >= 0 { "+" + dur(m) } else { "−" + dur(-m) }
#let fmt-date(d, t) = [#d.day()#t.ord #t.months.at(d.month() - 1)]
#let fmt-date-short(d, t) = [#d.day().#d.month().]
#let fmt-date-long(d, t) = [#d.day()#t.ord #t.months.at(d.month() - 1) #d.year()]

// Key identifying "the same course" for colouring.
#let course-key(ev) = if ev.lv_number != "" { ev.lv_number } else { ev.full_title }

#let type-label(ev, t) = t.types.at(ev.type, default: ev.type)

// Show the group only when it carries information.
#let group-label(ev, t) = if ev.group == t.default-group { none } else { ev.group }

#let detail-line(ev, t) = {
  let parts = (
    type-label(ev, t),
    group-label(ev, t),
  ).filter(x => x != none and x != "")
  parts.join(" · ")
}

#let room-label(ev) = {
  if ev.room == "" { none } else if ev.room_code != "" and ev.room_code != ev.room {
    ev.room + " (" + ev.room_code + ")"
  } else { ev.room }
}

// Group items (events, slots, legs) by their ISO date.
#let index-by-date(items) = {
  let out = (:)
  for it in items {
    out.insert(it.date, out.at(it.date, default: ()) + (it,))
  }
  out
}

// Chip with the work slot, used in the month view.
#let work-chip(s, t) = block(
  width: 100%, above: 0pt, below: 1.5pt,
  fill: work-fill, stroke: (left: 2pt + work-line),
  inset: (x: 2.5pt, y: 1.5pt),
  text(size: 6.8pt, fill: work-ink)[*#t.work #s.start–#s.end* #dur(s.minutes)],
)

// ---------------------------------------------------------------- views ---

// Settings used, weekly hours and the course legend.
#let overview-page(plan, events, color-of, t, title, subtitle) = {
  let cfg = plan.config
  let weekday-keys = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
  let cfg-rows = (
    (t.cfg.home-to-tum, [#cfg.home_to_tum min]),
    (t.cfg.tum-to-job, [#cfg.tum_to_job min]),
    (t.cfg.job-to-tum, [#cfg.job_to_tum min]),
    (t.cfg.home-to-job, [#cfg.home_to_job min]),
    (t.cfg.job-to-home, [#cfg.job_to_home min]),
    (t.cfg.wake, [#cfg.earliest_wake_up]),
    (t.cfg.ready, [#cfg.ready_minutes min]),
    (t.cfg.latest, [#cfg.latest_at_job]),
    (t.cfg.earliest-job, if cfg.earliest_at_job == none [#t.nothing] else [#cfg.earliest_at_job]),
    (t.cfg.min-block, [#cfg.min_time_at_company min]),
    (t.cfg.max-block, if cfg.max_shift_minutes == none [#t.nothing] else [#cfg.max_shift_minutes min]),
    (t.cfg.buffer, [#cfg.buffer_minutes min]),
    (t.cfg.work-days, t.days-short.enumerate()
      .filter(p => (p.at(0) + 1) in cfg.work_days).map(p => p.at(1)).join(", ")),
    (t.cfg.target, if cfg.weekly_target_minutes == none [#t.nothing] else [#dur(cfg.weekly_target_minutes)]),
    (t.cfg.not-attended, if cfg.not_attended.len() == 0 [#t.nothing] else [#cfg.not_attended.join(", ")]),
    (t.cfg.sessions, if cfg.sessions_not_attended.len() == 0 [#t.nothing] else [#cfg.sessions_not_attended.join(", ")]),
    (t.cfg.show-skipped, if cfg.show_skipped [#t.yes] else [#t.hidden]),
    (t.cfg.no-work, if cfg.no_work.len() == 0 [#t.nothing] else [#cfg.no_work.join(", ")]),
    (t.cfg.overrides, if cfg.day_overrides.len() == 0 [#t.nothing] else [
      #cfg.day_overrides.pairs().map(p => {
        let day = t.days-short.at(weekday-keys.position(x => x == p.at(0)))
        let parts = p.at(1).pairs().map(q => (if q.at(0) == "latest_at_job" { t.cfg.latest } else { t.cfg.earliest-job }) + " " + q.at(1))
        day + ": " + parts.join(", ")
      }).join("; ")
    ]),
  )

  [
    #text(size: 20pt, weight: "bold")[#title]
    #if subtitle != none [ #h(0.6em) #text(size: 12pt, fill: luma(110))[#subtitle]]
    #v(0.3cm)
  ]

  set text(size: 8pt)
  grid(
    columns: (9.6cm, 1fr), column-gutter: 0.8cm,
    [
      #text(size: 10pt, weight: "bold")[#t.settings]
      #v(0.15cm)
      #table(
        columns: (4.4cm, 1fr),
        inset: (x: 4pt, y: 2.6pt),
        stroke: (x: none, y: 0.4pt + luma(220)),
        ..cfg-rows.map(r => (text(fill: luma(90))[#r.at(0)], r.at(1))).flatten(),
      )
    ],
    [
      #text(size: 10pt, weight: "bold")[#t.hours]
      #v(0.15cm)
      #let weeks = plan.weeks
      #let scale = calc.max(60, ..weeks.map(w => calc.max(w.work_minutes, w.lecture_minutes)))
      #table(
        columns: (1.3cm, 4.6cm, 2.2cm, 2.4cm, 2.4cm, 1fr),
        inset: (x: 4pt, y: 2.6pt),
        stroke: (x: none, y: 0.4pt + luma(220)),
        align: (left + horizon, left + horizon, right + horizon, right + horizon,
          right + horizon, left + horizon),
        table.header(
          [*#t.week*], [], [*#t.lectures*], [*#t.possible*], [*#t.delta*], [],
        ),
        ..weeks.map(w => {
          let monday = parse-date(w.monday)
          let sunday = add-days(monday, 6)
          let delta = if w.target_minutes == none { none } else { w.work_minutes - w.target_minutes }
          (
            [#t.wk #w.week],
            [#fmt-date-short(monday, t) – #fmt-date-short(sunday, t)#sunday.year()],
            [#dur(w.lecture_minutes)],
            text(weight: "bold", fill: work-ink)[#dur(w.work_minutes)],
            if delta == none [–] else [#signed-dur(delta)],
            stack(dir: ttb, spacing: 1pt,
              rect(width: 3.2cm * (w.lecture_minutes / scale), height: 0.12cm, fill: luma(200), stroke: none),
              rect(width: 3.2cm * (w.work_minutes / scale), height: 0.18cm, fill: work-line, stroke: none),
            ),
          )
        }).flatten(),
      )
    ],
  )

  v(0.4cm)
  text(size: 10pt, weight: "bold")[#t.courses]
  v(0.15cm)

  // One row per (course, group).
  let series = events.map(e => (course-key(e), e.group)).dedup()
  let rows = series.map(sk => {
    let evs = events.filter(e => course-key(e) == sk.at(0) and e.group == sk.at(1))
    let first = evs.first()
    let weekly = evs.map(e => (parse-date(e.date).weekday(), e.start_min, e.end_min)).dedup()
      .sorted(key: x => x.at(0) * 10000 + x.at(1))
    let times = weekly.map(w => t.days-short.at(w.at(0) - 1) + " " + hm(w.at(1)) + "–" + hm(w.at(2)))
    let rooms = evs.map(e => room-label(e)).filter(r => r != none).dedup()
    (
      title: first.title,
      color: color-of(first),
      kind: type-label(first, t),
      group: group-label(first, t),
      times: times.join(", "),
      rooms: rooms.join("; "),
      count: evs.len(),
      from: parse-date(evs.first().date),
      to: parse-date(evs.last().date),
      skipped: first.skipped,
    )
  }).sorted(key: r => r.title)

  table(
    columns: (0.5cm, 5.2cm, 2.4cm, 2.4cm, 4.6cm, 1fr, 1.7cm, 3.4cm),
    inset: (x: 4pt, y: 3pt),
    stroke: (x: none, y: 0.4pt + luma(210)),
    align: (center + horizon, left + horizon, left + horizon, left + horizon,
      left + horizon, left + horizon, center + horizon, left + horizon),
    table.header(
      [], [*#t.course*], [*#t.kind*], [*#t.group*], [*#t.times*], [*#t.room*],
      [*#t.sessions*], [*#t.period*],
    ),
    ..rows.map(r => (
      rect(width: 0.28cm, height: 0.28cm, fill: if r.skipped { hatch } else { r.color.line }, radius: 1pt),
      [#text(weight: "bold")[#r.title]#if r.skipped [ #text(size: 7pt, fill: luma(120), style: "italic")[(#t.skipped)]]],
      r.kind,
      if r.group == none [] else [#r.group],
      r.times,
      r.rooms,
      str(r.count),
      [#fmt-date-short(r.from, t) – #fmt-date-short(r.to, t)#r.to.year()],
    )).flatten(),
  )
}

// Month grid: lectures, possible work and the hours per day.
#let month-page(year, month, by-date, days, t, title) = {
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
    let wk-w = 0.9cm
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
          grid.cell(fill: luma(245), align: center + top, inset: 4pt,
            text(size: 7.5pt, fill: luma(120))[#t.wk #weeknum(monday)]),
          ..days.map(wd => {
            let d = add-days(monday, wd - 1)
            let in-month = d.month() == month
            let items = if in-month { by-date.at(iso(d), default: ()) } else { () }
            let work = items.filter(it => it.kind == "work").map(it => it.minutes).sum(default: 0)
            grid.cell(
              inset: 3pt,
              fill: if not in-month { luma(248) } else if work > 0 { work-day-fill } else { white },
              block(width: 100%, height: 100%, clip: true, {
                if in-month {
                  grid(
                    columns: (1fr, auto),
                    text(size: 9pt, weight: "bold", fill: luma(90))[#d.day()],
                    if work > 0 { text(size: 8pt, weight: "bold", fill: work-ink)[#dur(work)] },
                  )
                  v(1pt)
                  for it in items.sorted(key: it => it.start_min) {
                    if it.kind == "work" {
                      work-chip(it, t)
                    } else {
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
                  }
                }
              }),
            )
          }),
        )
      }).flatten(),
    )
  }))
}

// One week as a time grid: lectures, travel and possible work.
#let week-page(week, events, slots, legs, days, hours, color-of, t, title) = {
  let (start-h, end-h) = hours
  let n-hours = end-h - start-h
  let monday = parse-date(week.monday)
  let work = week.work_minutes
  let target = week.target_minutes

  [
    #text(size: 20pt, weight: "bold")[#t.week #week.week]
    #h(0.6em)
    #text(size: 12pt, fill: luma(110))[
      #fmt-date(monday, t) – #fmt-date-long(add-days(monday, days.last() - 1), t)
    ]
    #h(1fr)
    #text(size: 10pt, weight: "bold", fill: work-ink)[#t.possible: #dur(work)]
    #if target != none [
      #text(size: 9pt, fill: luma(110))[ (#t.target #dur(target), #t.delta #signed-dur(work - target))]
    ]
  ]
  v(0.2cm)

  block(width: 100%, height: 1fr, layout(size => {
    let time-w = 1.1cm
    let head-h = 0.9cm
    let col-w = (size.width - time-w) / days.len()
    let hour-h = calc.min(1.7cm, (size.height - head-h - 0.1cm) / n-hours)
    let grid-h = hour-h * n-hours
    let y-of(minutes) = head-h + (minutes - start-h * 60) / 60 * hour-h
    let by-day-events = index-by-date(events)
    let by-day-slots = index-by-date(slots)
    let by-day-legs = index-by-date(legs)

    block(width: 100%, height: head-h + grid-h, {
      // day headers with the possible work per day
      for (i, wd) in days.enumerate() {
        let d = add-days(monday, wd - 1)
        let day-work = by-day-slots.at(iso(d), default: ()).map(s => s.minutes).sum(default: 0)
        place(top + left, dx: time-w + i * col-w,
          box(width: col-w, height: head-h, align(center + horizon)[
            #text(weight: "bold", size: 10pt)[#t.days.at(wd - 1)]
            #text(size: 9pt, fill: luma(110))[#h(0.4em) #fmt-date-short(d, t)]
            #if day-work > 0 [#linebreak()#text(size: 8pt, weight: "bold", fill: work-ink)[#t.work #dur(day-work)]]
          ]))
      }
      // hour lines + labels
      for h in range(start-h, end-h + 1) {
        let y = y-of(h * 60)
        place(top + left, dy: y, line(length: 100%, stroke: 0.4pt + luma(205)))
        place(top + left, dy: y - 5pt, box(width: time-w - 4pt, align(right,
          text(size: 8pt, fill: luma(120))[#hm(h * 60)])))
        if h < end-h {
          place(top + left, dx: time-w, dy: y + hour-h / 2,
            line(length: size.width - time-w, stroke: (paint: luma(235), thickness: 0.4pt, dash: "dotted")))
        }
      }
      // day separators
      for i in range(days.len() + 1) {
        place(top + left, dx: time-w + i * col-w, dy: head-h,
          line(angle: 90deg, length: grid-h, stroke: 0.4pt + luma(205)))
      }

      for (i, wd) in days.enumerate() {
        let key = iso(add-days(monday, wd - 1))
        let x = time-w + i * col-w

        // 1. travel (neutral grey, behind everything else)
        for leg in by-day-legs.at(key, default: ()) {
          let h = (leg.end_min - leg.start_min) / 60 * hour-h
          place(top + left, dx: x + 2pt, dy: y-of(leg.start_min) + 0.5pt,
            block(
              width: col-w - 4pt, height: h - 1pt,
              fill: travel-fill, stroke: (left: 1pt + travel-line),
              inset: (x: 3pt, y: 1pt), clip: true,
              align(horizon, text(size: 6.8pt, fill: travel-ink, style: "italic")[
                #t.travel.at(leg.kind.replace("_", "-")) · #(leg.end_min - leg.start_min) min
              ]),
            ))
        }

        // 2. possible work: highlighted in green
        for s in by-day-slots.at(key, default: ()) {
          let h = (s.end_min - s.start_min) / 60 * hour-h
          place(top + left, dx: x + 2pt, dy: y-of(s.start_min) + 1pt,
            block(
              width: col-w - 4pt, height: h - 2pt,
              fill: work-fill, stroke: 1.4pt + work-line, radius: 3pt,
              inset: (x: 4pt, y: 3pt), clip: true,
              {
                set par(leading: 0.35em, spacing: 0.35em)
                set text(size: 8pt, fill: work-ink)
                text(weight: "bold")[#t.work #s.start–#s.end]
                linebreak()
                text(size: 7.5pt, weight: "bold")[#dur(s.minutes)]
              },
            ))
        }

        // 3. lectures: attended ones share the column in lanes; skipped ones are a
        //    narrow hatched strip on the right edge, drawn last so they stay visible
        let day-events = by-day-events.at(key, default: ())
        for e in day-events.sorted(key: e => if e.skipped { 1 } else { 0 }) {
          let c = e.color
          let lane-w = if e.skipped { col-w * 0.36 } else { col-w / e.lanes }
          let lane-x = if e.skipped { col-w * 0.64 } else { e.lane * lane-w }
          let h = (e.end_min - e.start_min) / 60 * hour-h
          place(top + left,
            dx: x + lane-x + 1pt,
            dy: y-of(e.start_min) + 0.5pt,
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
      }
    })
  }))
}

// ----------------------------------------------------------------- main ---

#let planner-calendar(
  plan,
  title: "Working student plan",
  lang: "en",
  views: ("overview", "month", "week"),
  include-empty-weeks: false,
  font: ("Arial", "Liberation Sans", "Libertinus Serif"),
) = {
  let t = i18n.at(lang)
  let all-events = plan.events.map(e => e + (d: parse-date(e.date)))
  let show-skipped = plan.config.show_skipped
  // Skipped sessions are part of the overview; in the grids they are shown or hidden.
  let visible = if show-skipped { all-events } else { all-events.filter(e => not e.skipped) }
  let slots = plan.slots
  let legs = plan.travel

  // Colours: stable per course, ordered by title.
  let keys = all-events.sorted(key: e => e.title).map(course-key).dedup()
  let color-of(e) = palette.at(calc.rem(keys.position(k => k == course-key(e)), palette.len()))
  let events = visible.map(e => e + (color: color-of(e)))

  // Visible weekdays: Mon-Fri, plus the weekend only if something happens there.
  let wds = (all-events.map(e => e.d.weekday()) + slots.map(s => parse-date(s.date).weekday()))
  let last-wd = calc.max(5, ..wds)
  let days = range(1, last-wd + 1)

  // Vertical extent of the time grid.
  let times = (events + slots + legs).map(x => (x.start_min, x.end_min))
  let start-h = calc.min(8, calc.quo(calc.min(..times.map(x => x.at(0))), 60))
  let end-h = calc.max(18, calc.ceil(calc.max(..times.map(x => x.at(1))) / 60))
  let hours = (start-h, end-h)

  let first = all-events.first().d
  let last = all-events.last().d
  let subtitle = [#fmt-date-long(first, t) – #fmt-date-long(last, t)]

  let month-items = index-by-date(
    events.map(e => (date: e.date, kind: "lecture", start_min: e.start_min, title: e.title,
      start: e.start, color: e.color, skipped: e.skipped))
    + slots.map(s => (date: s.date, kind: "work", start_min: s.start_min, start: s.start,
      end: s.end, minutes: s.minutes))
  )

  set document(title: title)
  set page(paper: "a4", flipped: true, margin: 1.2cm,
    footer: text(size: 7pt, fill: luma(150))[
      #title #h(1fr) #t.generated #datetime.today().display("[year]-[month]-[day]")
    ])
  set text(font: font, size: 9pt, lang: lang)

  let pages = ()

  if "overview" in views {
    pages.push(overview-page(plan, all-events, color-of, t, title, subtitle))
  }

  if "month" in views {
    let y = first.year()
    let m = first.month()
    while y < last.year() or (y == last.year() and m <= last.month()) {
      pages.push(month-page(y, m, month-items, days, t, title))
      if m == 12 { y += 1; m = 1 } else { m += 1 }
    }
  }

  if "week" in views {
    for week in plan.weeks {
      let monday = parse-date(week.monday)
      let sunday = add-days(monday, 6)
      let week-events = events.filter(e => week.monday <= e.date and e.date <= iso(sunday))
      let week-slots = slots.filter(s => week.monday <= s.date and s.date <= iso(sunday))
      let week-legs = legs.filter(l => week.monday <= l.date and l.date <= iso(sunday))
      if week-events.len() > 0 or week-slots.len() > 0 or include-empty-weeks {
        pages.push(week-page(week, week-events, week-slots, week-legs, days, hours,
          color-of, t, title))
      }
    }
  }

  pages.join(pagebreak())
}
