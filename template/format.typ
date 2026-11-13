// Dates, clock times, durations and the short texts built from them.

// "2026-12-07" -> datetime
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

// "car · Home → TUM" for a travel block
#let leg-text(leg, t) = t.legs.at(leg.src + leg.dst, default: "") + " · " + t.modes.at(leg.mode)

// The evaluation line of a day: travel, extra travel, mode and, if known, the fuel estimate.
#let day-eval(option, t) = [#t.travel #dur(option.travel_minutes) (#t.extra #dur(option.extra_minutes)), #t.modes.at(option.modes, default: option.modes)#if option.fuel_eur != none [, ~#calc.round(option.fuel_eur, digits: 2) EUR]]
