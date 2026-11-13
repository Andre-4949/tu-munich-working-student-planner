// Helpers that read the JSON from scripts/plan.py: course identity, labels and grouping.

// Key identifying "the same course" for colouring.
#let course-key(ev) = if ev.lv_number != "" { ev.lv_number } else { ev.full_title }

#let type-label(ev, t) = t.types.at(ev.type, default: ev.type)

// Show the group only when it carries information.
#let group-label(ev, t) = if ev.group == t.default-group { none } else { ev.group }

// "Lecture · Group 2", without the empty parts.
#let detail-line(ev, t) = {
  let parts = (
    type-label(ev, t),
    group-label(ev, t),
  ).filter(x => x != none and x != "")
  parts.join(" · ")
}

// "Hall (01.02.003)", or only the room name when the code adds nothing.
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
