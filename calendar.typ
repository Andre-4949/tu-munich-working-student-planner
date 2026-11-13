// Entry point. Build with:
//
//   typst compile calendar.typ plan.pdf
//
// Run scripts/plan.py first; it writes the JSON read here.
//
// Optional settings via `--input key=value`:
//   data         JSON file from scripts/plan.py     (default: data/plan.json)
//   title        title printed on every page         (default: Working student plan)
//   lang         en | de                             (default: en)
//   views        comma separated: overview,month,week (default: all three)
//   empty-weeks  true to also print weeks without lectures or work slots (default: false)
#import "lib.typ": planner-calendar

#let opt(key, default) = sys.inputs.at(key, default: default)

#planner-calendar(
  json(opt("data", "data/plan.json")),
  title: opt("title", "Working student plan"),
  lang: opt("lang", "en"),
  views: opt("views", "overview,month,week").split(","),
  include-empty-weeks: opt("empty-weeks", "false") == "true",
)
