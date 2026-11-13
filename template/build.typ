// The entry point of the template: prepares the data of the JSON and builds the pages.
// Input: the JSON written by scripts/plan.py. Typst only draws; all the planning happens in Python.
#import "colors.typ": palette
#import "data.typ": course-key, index-by-date
#import "format.typ": add-days, fmt-date-long, iso, parse-date
#import "language.typ": i18n
#import "month.typ": month-page
#import "overview.typ": overview-page
#import "week.typ": week-page

// One colour per course, stable across the document and ordered by title.
#let course-colors(all-events) = {
  let keys = all-events.sorted(key: e => e.title).map(course-key).dedup()
  e => palette.at(calc.rem(keys.position(k => k == course-key(e)), palette.len()))
}

// Weekdays drawn: Monday to Friday, plus the weekend only if something happens there.
#let weekday-count(plan, all-events, boss) = {
  let wds = if boss {
    plan.boss.blocks.map(b => parse-date(b.date).weekday()) + plan.boss.exams.map(e => parse-date(e).weekday())
  } else {
    all-events.map(e => e.d.weekday()) + plan.slots.map(s => parse-date(s.date).weekday())
  }
  calc.max(5, ..wds)
}

// The hours shown in the time grid: from 08:00 (or earlier) to 18:00 (or later).
#let time-range(events, slots, legs) = {
  let times = (events + slots + legs).map(x => (x.start_min, x.end_min))
  let start-h = calc.min(8, calc.quo(calc.min(..times.map(x => x.at(0))), 60))
  let end-h = calc.max(18, calc.ceil(calc.max(..times.map(x => x.at(1))) / 60))
  (start-h, end-h)
}

// The items of the month grid: lectures and visits, per date.
#let lecture-and-work-items(events, slots) = index-by-date(
  events.map(e => (date: e.date, kind: "lecture", start_min: e.start_min, title: e.title,
    start: e.start, color: e.color, skipped: e.skipped))
  + slots.map(s => (date: s.date, kind: "work", start_min: s.start_min, start: s.start,
    end: s.end, minutes: s.minutes, work_minutes: s.work_minutes, status: s.status))
)

// The supervisor's office blocks, per date.
#let boss-by-date(blocks) = {
  let out = (:)
  for b in blocks {
    out.insert(b.date, out.at(b.date, default: ()) + (b,))
  }
  out
}

#let planner-calendar(
  plan,
  title: "Working student plan",
  lang: "en",
  views: ("overview", "month", "week"),
  include-empty-weeks: false,
  audience: "me",
  font: ("Arial", "Liberation Sans", "Libertinus Serif"),
) = {
  let t = i18n.at(lang)
  // The supervisor gets the monthly view only: office blocks and exam days, nothing else.
  let boss = audience == "boss"
  let page-views = if boss { ("month",) } else { views }

  let all-events = plan.events.map(e => e + (d: parse-date(e.date)))
  let visible = if plan.config.show_skipped { all-events } else { all-events.filter(e => not e.skipped) }
  let slots = plan.slots
  let legs = plan.travel
  let days-info = (:)
  for d in plan.days {
    days-info.insert(d.date, d)
  }

  let color-of = course-colors(all-events)
  let events = visible.map(e => e + (color: color-of(e)))
  let days = range(1, weekday-count(plan, all-events, boss) + 1)
  let hours = time-range(events, slots, legs)

  let first = parse-date(plan.calendar.start)
  let last = parse-date(plan.calendar.end)
  let subtitle = [#fmt-date-long(first, t) – #fmt-date-long(last, t)]

  let month-items = if boss { (:) } else { lecture-and-work-items(events, slots) }
  let boss-info = if boss { (blocks: boss-by-date(plan.boss.blocks), exams: plan.boss.exams) } else { none }

  set document(title: title)
  set page(paper: "a4", flipped: true, margin: 1.2cm,
    footer: text(size: 7pt, fill: luma(150))[
      #title #h(1fr) #t.generated #datetime.today().display("[year]-[month]-[day]")
    ])
  set text(font: font, size: 9pt, lang: lang)

  let pages = ()

  if "overview" in page-views {
    pages.push(overview-page(plan, all-events, color-of, t, title, subtitle))
  }

  if "month" in page-views {
    let y = first.year()
    let m = first.month()
    while y < last.year() or (y == last.year() and m <= last.month()) {
      pages.push(month-page(y, m, month-items, days-info, days, t, title, boss: boss-info))
      if m == 12 { y += 1; m = 1 } else { m += 1 }
    }
  }

  if "week" in page-views {
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
