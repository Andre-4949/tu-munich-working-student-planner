// The overview page: settings used, weekly hours against the target, and the course legend.
#import "colors.typ": fallback-ink, fallback-line, hatch, planned-ink, planned-line
#import "data.typ": course-key, group-label, room-label, type-label
#import "format.typ": add-days, dur, fmt-date-short, hm, parse-date, signed-dur

#let weekday-keys = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

// Rows of the settings table: (label, value).
#let settings-rows(cfg, t) = {
  let rows = (
    (t.cfg.home-to-tum, [#cfg.home_to_tum min]),
    (t.cfg.tum-to-job, [#cfg.tum_to_job min]),
    (t.cfg.job-to-tum, [#cfg.job_to_tum min]),
    (t.cfg.home-to-job, [#cfg.home_to_job min]),
    (t.cfg.job-to-home, [#cfg.job_to_home min]),
  )
  if cfg.car != none {
    rows.push((t.cfg.car, [#cfg.car.home_to_tum / #cfg.car.home_to_job / #cfg.car.tum_to_job min]))
  }
  rows += (
    (t.cfg.wake, [#cfg.earliest_wake_up]),
    (t.cfg.ready, [#cfg.ready_minutes min]),
    (t.cfg.latest, [#cfg.latest_at_job]),
    (t.cfg.earliest-job, if cfg.earliest_at_job == none [#t.nothing] else [#cfg.earliest_at_job]),
    (t.cfg.min-block, [#cfg.min_time_at_company min]),
    (t.cfg.max-block, if cfg.max_shift_minutes == none [#t.nothing] else [#cfg.max_shift_minutes min]),
    (t.cfg.pause, [#cfg.break_minutes min]),
    (t.cfg.buffer, [#cfg.buffer_minutes min]),
    (t.cfg.work-days, t.days-short.enumerate()
      .filter(p => (p.at(0) + 1) in cfg.work_days).map(p => p.at(1)).join(", ")),
    (t.cfg.target, if cfg.weekly_target_minutes == none [#t.nothing] else [#dur(cfg.weekly_target_minutes)]),
    (t.cfg.maximum, if cfg.max_week_minutes == none [#t.nothing] else [#dur(cfg.max_week_minutes)]),
    (t.cfg.fuel, if cfg.car == none or cfg.car.distance_in_km == none [#t.nothing] else [
      #cfg.car.distance_in_km km × #cfg.car.liters_per_100km l/100 km × #cfg.car.fuel_price_per_liter EUR/l
    ]),
    (t.cfg.not-attended, if cfg.not_attended.len() == 0 [#t.nothing] else [#cfg.not_attended.join(", ")]),
    (t.cfg.sessions, if cfg.sessions_not_attended.len() == 0 [#t.nothing] else [#cfg.sessions_not_attended.join(", ")]),
    (t.cfg.show-skipped, if cfg.show_skipped [#t.yes] else [#t.hidden]),
    (t.cfg.no-work, if cfg.no_work.len() == 0 [#t.nothing] else [#cfg.no_work.join(", ")]),
    (t.cfg.blocked, if cfg.no_work_durations.len() == 0 [#t.nothing] else [#cfg.no_work_durations.join(", ")]),
    (t.cfg.overrides, if cfg.day_overrides.len() == 0 [#t.nothing] else [
      #cfg.day_overrides.pairs().map(p => {
        let day = t.days-short.at(weekday-keys.position(x => x == p.at(0)))
        let parts = p.at(1).pairs().map(q => (if q.at(0) == "latest_at_job" { t.cfg.latest } else { t.cfg.earliest-job }) + " " + q.at(1))
        day + ": " + parts.join(", ")
      }).join("; ")
    ]),
  )
  rows
}

#let settings-table(cfg, t) = table(
  columns: (4.6cm, 1fr),
  inset: (x: 4pt, y: 2.2pt),
  stroke: (x: none, y: 0.4pt + luma(220)),
  ..settings-rows(cfg, t).map(r => (text(fill: luma(90))[#r.at(0)], r.at(1))).flatten(),
)

// One row per week: lectures, planned and fallback hours, the difference to the target and a bar.
#let weekly-hours(weeks, t) = {
  // the bars share one scale: the longest week fills 3.2 cm
  let scale = calc.max(60, ..weeks.map(w => calc.max(w.planned_minutes + w.fallback_minutes, w.lecture_minutes)))
  [
    #text(size: 10pt, weight: "bold")[#t.hours]
    #v(0.15cm)
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
  ]
}

// One row per course and group: colour, times, rooms, the number of sessions and the period.
#let course-table(events, color-of, t) = {
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

#let overview-page(plan, events, color-of, t, title, subtitle) = {
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
      #settings-table(plan.config, t)
    ],
    weekly-hours(plan.weeks, t),
  )

  v(0.4cm)
  text(size: 10pt, weight: "bold")[#t.courses]
  v(0.15cm)
  course-table(events, color-of, t)
}
