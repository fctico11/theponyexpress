// Renders the Drops page from drops-data.js: the current drop's teaser, a countdown to
// the day it ships, and the archive of past drops.
(function drops() {
  const data = window.DROPS;
  if (!data) return;
  const cur = data.current;
  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };

  // ---- the smiley's flowing colours stop for anyone who asks for less motion
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    document.querySelectorAll("svg.smiley").forEach((svg) => svg.pauseAnimations && svg.pauseAnimations());
  }

  // ---- the teaser
  document.querySelectorAll("[data-drop-no]").forEach((n) => { n.textContent = cur.no; });
  $("drop-title").textContent = cur.title;
  $("drop-kicker").textContent = cur.kicker;
  const blurb = $("drop-blurb");
  cur.blurb.forEach((p) => blurb.append(el("p", null, p)));
  const list = $("drop-chapters");
  cur.chapters.forEach((c, i) => {
    const li = el("li");
    li.append(el("span", "tracklist__no", String(i + 1).padStart(2, "0")), el("span", "tracklist__name", c));
    list.append(li);
  });
  $("drop-extras").textContent = cur.extras;

  // ---- when it ships, and the countdown to it
  const when = $("drop-when");
  const clock = $("drop-clock");
  const ships = cur.ships ? new Date(cur.ships + "T09:00:00") : null;
  if (!ships || isNaN(ships)) {
    when.textContent = "Ship date coming soon";
    clock.hidden = true;
  } else {
    const fmt = { month: "long", day: "numeric", year: "numeric" };
    const join = new Date(ships); join.setDate(join.getDate() - 1);
    when.textContent = `Ships ${ships.toLocaleDateString("en-US", fmt)} · Join by ${join.toLocaleDateString("en-US", { month: "long", day: "numeric" })}`;
    const parts = { d: $("clock-d"), h: $("clock-h"), m: $("clock-m"), s: $("clock-s") };
    const tick = () => {
      const left = Math.max(0, ships - Date.now());
      const s = Math.floor(left / 1000);
      parts.d.textContent = String(Math.floor(s / 86400)).padStart(2, "0");
      parts.h.textContent = String(Math.floor(s / 3600) % 24).padStart(2, "0");
      parts.m.textContent = String(Math.floor(s / 60) % 60).padStart(2, "0");
      parts.s.textContent = String(s % 60).padStart(2, "0");
      if (left <= 0) { when.textContent = `Drop ${cur.no} is on its way`; return; }
      setTimeout(tick, 1000 - (Date.now() % 1000));
    };
    tick();
  }

  // ---- the archive
  const past = $("drop-past");
  if (!data.past.length) {
    past.append(el("p", "archive__empty", `Nothing in the crate yet. Drop ${cur.no} is the first.`));
    return;
  }
  const ul = el("ul", "archive__list");
  data.past.forEach((d) => {
    const li = el("li", "archive__item");
    if (d.image) {
      const img = el("img");
      img.src = d.image; img.alt = ""; img.loading = "lazy";
      li.append(img);
    }
    li.append(el("p", "archive__no", `Drop ${d.no}`), el("h3", null, d.title));
    if (d.shipped) li.append(el("p", "archive__date", new Date(d.shipped + "T12:00:00").toLocaleDateString("en-US", { month: "long", year: "numeric" })));
    if (d.blurb) li.append(el("p", null, d.blurb));
    ul.append(li);
  });
  past.append(ul);
})();
