// Planner template: lectures, travel (car or transit) and the planned work visits.
// Input: the JSON written by scripts/plan.py (see README). Typst only draws;
// all the planning happens in Python.

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
    hours: "Work hours per week",
    course: "Course", kind: "Type", group: "Group", times: "Times", room: "Room",
    sessions: "Sessions", period: "Period",
    lectures: "Lectures", planned: "Planned", fallback: "Fallback", target: "Target",
    delta: "vs. target", travel: "Travel", extra: "extra", possible: "possible",
    work: "Work", skipped: "skipped", nothing: "none", no-work: "no work", commute: "commute",
    default-group: "Standardgruppe",
    types: (VO: "Lecture", UE: "Exercise", VU: "Lecture + Exercise",
      VI: "Lecture + Exercise", PR: "Lab", SE: "Seminar", PS: "Proseminar",
      KO: "Colloquium", RE: "Revision course"),
    // leg labels: from-to, H = home, T = TUM, J = job
    legs: ("HT": "Home → TUM", "TH": "TUM → home", "TJ": "TUM → job", "JT": "Job → TUM",
      "HJ": "Home → job", "JH": "Job → home"),
    modes: (car: "car", transit: "transit", mixed: "mixed", nothing: ""),
    cfg: (
      home-to-tum: "Home → TUM (transit)", tum-to-job: "TUM → job (transit)",
      job-to-tum: "Job → TUM (transit)", home-to-job: "Home → job (transit)",
      job-to-home: "Job → home (transit)",
      car: "Car times", wake: "Earliest wake-up", ready: "Ready after wake-up",
      latest: "Latest at job", earliest-job: "Earliest at job",
      min-block: "Shortest work block", max-block: "Longest work block",
      buffer: "Buffer next to lectures", work-days: "Work days",
      target: "Weekly target", maximum: "Weekly maximum", penalty: "Penalty per company day",
      not-attended: "Courses not attended", sessions: "Sessions not attended",
      show-skipped: "Skipped sessions in PDF", no-work: "Closed / no work",
      overrides: "Day overrides", calendar: "Calendar range",
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
    hours: "Arbeitsstunden pro Woche",
    course: "Lehrveranstaltung", kind: "Art", group: "Gruppe", times: "Zeiten", room: "Raum",
    sessions: "Termine", period: "Zeitraum",
    lectures: "Vorlesungen", planned: "Geplant", fallback: "Ersatz", target: "Ziel",
    delta: "vs. Ziel", travel: "Fahrt", extra: "zusätzlich", possible: "möglich",
    work: "Arbeit", skipped: "übersprungen", nothing: "keine", no-work: "keine Arbeit",
    commute: "Anfahrt",
    default-group: "Standardgruppe",
    types: (VO: "Vorlesung", UE: "Übung", VU: "Vorlesung + Übung",
      VI: "Vorlesung + Übung", PR: "Praktikum", SE: "Seminar", PS: "Proseminar",
      KO: "Kolloquium", RE: "Repetitorium"),
    legs: ("HT": "Zuhause → TUM", "TH": "TUM → Zuhause", "TJ": "TUM → Job", "JT": "Job → TUM",
      "HJ": "Zuhause → Job", "JH": "Job → Zuhause"),
    modes: (car: "Auto", transit: "ÖPNV", mixed: "gemischt", nothing: ""),
    cfg: (
      home-to-tum: "Zuhause → TUM (ÖPNV)", tum-to-job: "TUM → Job (ÖPNV)",
      job-to-tum: "Job → TUM (ÖPNV)", home-to-job: "Zuhause → Job (ÖPNV)",
      job-to-home: "Job → Zuhause (ÖPNV)",
      car: "Auto-Fahrzeiten", wake: "Frühestes Aufstehen", ready: "Fertig machen nach dem Aufstehen",
      latest: "Spätestens im Job", earliest-job: "Frühestens im Job",
      min-block: "Kürzester Arbeitsblock", max-block: "Längster Arbeitsblock",
      buffer: "Puffer neben Vorlesungen", work-days: "Arbeitstage",
      target: "Wochenziel", maximum: "Wochenmaximum", penalty: "Strafe pro Firmentag",
      not-attended: "Nicht besuchte Veranstaltungen", sessions: "Nicht besuchte Termine",
      show-skipped: "Übersprungene im PDF", no-work: "Geschlossen / keine Arbeit",
      overrides: "Tages-Ausnahmen", calendar: "Kalenderzeitraum",
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

// Planned work: strong green. Fallback: a lighter green tone. Both are work, not travel.
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

// Group items (events, slots, legs, days) by their ISO date.
#let index-by-date(items) = {
  let out = (:)
  for it in items {
    out.insert(it.date, out.at(it.date, default: ()) + (it,))
  }
  out
}

// "car · Home → TUM" for a travel block
#let leg-text(leg, t) = t.legs.at(leg.src + leg.dst, default: "") + " · " + t.modes.at(leg.mode)

// The evaluation line of a day: what it would cost in travel
#let day-eval(option, t) = [#t.travel #dur(option.travel_minutes) (#t.extra #dur(option.extra_minutes)), #t.modes.at(option.modes, default: option.modes)]

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
  )
  if cfg.car != none {
    cfg-rows.push((t.cfg.car, [#cfg.car.home_to_tum / #cfg.car.home_to_job / #cfg.car.tum_to_job min]))
  }
  cfg-rows += (
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
    (t.cfg.maximum, if cfg.max_week_minutes == none [#t.nothing] else [#dur(cfg.max_week_minutes)]),
    (t.cfg.penalty, [#cfg.company_day_penalty min]),
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
        columns: (4.6cm, 1fr),
        inset: (x: 4pt, y: 2.2pt),
        stroke: (x: none, y: 0.4pt + luma(220)),
        ..cfg-rows.map(r => (text(fill: luma(90))[#r.at(0)], r.at(1))).flatten(),
      )
    ],
    [
      #text(size: 10pt, weight: "bold")[#t.hours]
      #v(0.15cm)
      #let weeks = plan.weeks
      #let scale = calc.max(60, ..weeks.map(w => calc.max(w.planned_minutes + w.fallback_minutes, w.lecture_minutes)))
      #table(
        columns: (1.3cm, 4.2cm, 1.9cm, 1.9cm, 1.9cm, 2.1cm, 1fr),
        inset: (x: 4pt, y: 2.2pt),
        stroke: (x: none, y: 0.4pt + luma(220)),
        align: (left + horizon, left + horizon, right + horizon, right + horizon,
          right + horizon, right + horizon, left + horizon),
        table.header(
          [*#t.week*], [], [*#t.lectures*], [*#t.planned*], [*#t.fallback*], [*#t.delta*], [],
        ),
        ..weeks.map(w => {
          let monday = parse-date(w.monday)
          let sunday = add-days(monday, 6)
          let delta = if w.target_minutes == none { none } else { w.planned_minutes - w.target_minutes }
          (
            [#t.wk #w.week],
            [#fmt-date-short(monday, t) – #fmt-date-short(sunday, t)#sunday.year()],
            [#dur(w.lecture_minutes)],
            text(weight: "bold", fill: planned-ink)[#dur(w.planned_minutes)],
            text(fill: fallback-ink)[#dur(w.fallback_minutes)],
            if delta == none [–] else [#signed-dur(delta)],
            stack(dir: ttb, spacing: 1pt,
              rect(width: 3.2cm * (w.lecture_minutes / scale), height: 0.12cm, fill: luma(200), stroke: none),
              rect(width: 3.2cm * (w.planned_minutes / scale), height: 0.16cm, fill: planned-line, stroke: none),
              rect(width: 3.2cm * (w.fallback_minutes / scale), height: 0.10cm, fill: fallback-line, stroke: none),
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

// Work chip in the month view.
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
    text(size: 6.8pt, fill: ink)[*#t.work #s.start–#s.end* #dur(s.minutes)],
  )
}

// Month grid: lectures, planned work and the hours per day.
#let month-page(year, month, by-date, days-info, days, t, title) = {
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
            let info = days-info.at(iso(d), default: none)
            let planned = if info != none and info.status == "planned" { info.work_minutes } else { 0 }
            let fallback = if info != none and info.status == "fallback" { info.work_minutes } else { 0 }
            grid.cell(
              inset: 3pt,
              fill: if not in-month { luma(248) } else if planned > 0 { planned-day } else { white },
              block(width: 100%, height: 100%, clip: true, {
                if in-month {
                  grid(
                    columns: (1fr, auto),
                    text(size: 9pt, weight: "bold", fill: luma(90))[#d.day()],
                    if planned > 0 {
                      text(size: 8pt, weight: "bold", fill: planned-ink)[#dur(planned)]
                    } else if fallback > 0 {
                      text(size: 8pt, fill: fallback-ink)[#dur(fallback) #t.fallback]
                    },
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

// One week as a time grid: lectures, travel and work.
#let week-page(week, events, slots, legs, days-info, days, hours, color-of, t, title) = {
  let (start-h, end-h) = hours
  let n-hours = end-h - start-h
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
  ]
  v(0.2cm)

  block(width: 100%, height: 1fr, layout(size => {
    let time-w = 1.1cm
    let head-h = 1.25cm
    let col-w = (size.width - time-w) / days.len()
    let hour-h = calc.min(1.7cm, (size.height - head-h - 0.1cm) / n-hours)
    let grid-h = hour-h * n-hours
    let y-of(minutes) = head-h + (minutes - start-h * 60) / 60 * hour-h
    let by-day-events = index-by-date(events)
    let by-day-slots = index-by-date(slots)
    let by-day-legs = index-by-date(legs)

    block(width: 100%, height: head-h + grid-h, {
      // day headers: date, planned or fallback work, and the travel of the plan
      for (i, wd) in days.enumerate() {
        let d = add-days(monday, wd - 1)
        let info = days-info.at(iso(d), default: none)
        let line = if info == none {
          none
        } else if info.status == "planned" {
          text(size: 8pt, weight: "bold", fill: planned-ink)[#t.planned #dur(info.work_minutes)]
        } else if info.status == "fallback" {
          text(size: 8pt, weight: "bold", fill: fallback-ink)[#t.fallback #dur(info.work_minutes)]
        } else if info.best != none {
          text(size: 7.5pt, fill: luma(110))[#t.possible #dur(info.best.work_minutes)]
        } else {
          text(size: 7.5pt, fill: luma(110))[#t.no-work]
        }
        place(top + left, dx: time-w + i * col-w,
          box(width: col-w, height: head-h, align(center + horizon)[
            #text(weight: "bold", size: 10pt)[#t.days.at(wd - 1)]
            #text(size: 9pt, fill: luma(110))[#h(0.4em) #fmt-date-short(d, t)]
            #linebreak()
            #line
            #if info != none and info.drawn != none and info.status != "none" [
              #linebreak()#text(size: 7pt, fill: luma(110))[#day-eval(info.drawn, t)]
            ]
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

        // 1. travel, behind everything else. Car: solid; transit: dotted outline.
        for leg in by-day-legs.at(key, default: ()) {
          let h = (leg.end_min - leg.start_min) / 60 * hour-h
          let car = leg.mode == "car"
          place(top + left, dx: x + 2pt, dy: y-of(leg.start_min) + 0.5pt,
            block(
              width: col-w - 4pt, height: h - 1pt,
              fill: if car { car-fill } else { travel-fill },
              stroke: (left: 1.2pt + travel-line, rest: if car { none } else { (paint: travel-line, thickness: 0.5pt, dash: "dotted") }),
              inset: (x: 3pt, y: 1pt), clip: true,
              align(horizon, text(size: 6.8pt, fill: travel-ink, style: "italic")[
                #leg-text(leg, t) · #(leg.end_min - leg.start_min) min
              ]),
            ))
        }

        // 2. work: planned in strong green, fallback in a lighter tone
        for s in by-day-slots.at(key, default: ()) {
          let planned = s.status == "planned"
          let h = (s.end_min - s.start_min) / 60 * hour-h
          place(top + left, dx: x + 2pt, dy: y-of(s.start_min) + 1pt,
            block(
              width: col-w - 4pt, height: h - 2pt,
              fill: if planned { planned-fill } else { fallback-fill },
              stroke: if planned { 1.4pt + planned-line } else { 1pt + fallback-line },
              radius: 3pt,
              inset: (x: 4pt, y: 3pt), clip: true,
              {
                set par(leading: 0.35em, spacing: 0.35em)
                set text(size: 8pt, fill: if planned { planned-ink } else { fallback-ink })
                text(weight: "bold")[#if planned { t.planned } else { t.fallback } #s.start–#s.end]
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
  let visible = if show-skipped { all-events } else { all-events.filter(e => not e.skipped) }
  let slots = plan.slots
  let legs = plan.travel
  let days-info = (:)
  for d in plan.days {
    days-info.insert(d.date, d)
  }

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

  let first = parse-date(plan.calendar.start)
  let last = parse-date(plan.calendar.end)
  let subtitle = [#fmt-date-long(first, t) – #fmt-date-long(last, t)]

  let month-items = index-by-date(
    events.map(e => (date: e.date, kind: "lecture", start_min: e.start_min, title: e.title,
      start: e.start, color: e.color, skipped: e.skipped))
    + slots.map(s => (date: s.date, kind: "work", start_min: s.start_min, start: s.start,
      end: s.end, minutes: s.minutes, status: s.status))
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
      pages.push(month-page(y, m, month-items, days-info, days, t, title))
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
      let has-days = week-events.len() > 0 or week-slots.len() > 0
      if has-days or include-empty-weeks {
        pages.push(week-page(week, week-events, week-slots, week-legs, days-info, days, hours,
          color-of, t, title))
      }
    }
  }

  pages.join(pagebreak())
}
