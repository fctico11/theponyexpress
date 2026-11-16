// Renders Marty's dates and gallery from marty-data.js.
(function () {
  const data = window.MARTY || { stops: [], media: [] };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  // ---- Dates ---------------------------------------------------------------

  // Parse "YYYY-MM-DD" as a local date so it doesn't shift a day by timezone.
  function parse(date) {
    const [y, m, d] = String(date).split("-").map(Number);
    return new Date(y, m - 1, d);
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const stops = (data.stops || [])
    .map((s) => {
      const when = parse(s.date);
      const until = s.end ? parse(s.end) : when;
      return { ...s, when, until: Number.isNaN(until.getTime()) ? when : until };
    })
    .filter((s) => !Number.isNaN(s.when.getTime()));

  // A festival counts as upcoming until its last day has passed.
  const upcoming = stops.filter((s) => s.until >= today).sort((a, b) => a.when - b.when);
  const been = stops.filter((s) => s.until < today).sort((a, b) => b.when - a.when);

  const dayMonth = new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short" });

  function row(stop, kind) {
    const li = el("li");

    const time = el("time", "sets__time");
    time.dateTime = stop.date;
    time.append(dayMonth.format(stop.when).toUpperCase());
    const year = String(stop.until.getFullYear());
    const multiDay = stop.until > stop.when;
    time.append(el("small", "", multiDay ? `to ${dayMonth.format(stop.until).toUpperCase()} ${year}` : year));
    li.append(time);

    const body = el("div");
    body.append(el("h3", "", stop.event));
    const line = [stop.place, stop.note].filter(Boolean).join(" · ");
    if (line) body.append(el("p", "", line));
    li.append(body);

    li.append(el("span", "sets__kind", kind));
    return li;
  }

  function fill(listId, emptyId, items, kind) {
    const list = document.getElementById(listId);
    const empty = document.getElementById(emptyId);
    if (!list) return;
    if (!items.length) {
      list.hidden = true;
      if (empty) empty.hidden = false;
      return;
    }
    items.forEach((s) => list.append(row(s, kind)));
  }

  fill("upcoming", "upcoming-empty", upcoming, "Heading there");
  fill("been", "been-empty", been, "Spotted");

  // ---- Gallery -------------------------------------------------------------

  const gallery = document.getElementById("gallery");
  if (!gallery) return;

  const media = data.media || [];

  if (!media.length) {
    ["Photo coming soon", "Video coming soon", "Photo coming soon"].forEach((label) => {
      const fig = el("figure", "gallery__item gallery__item--empty");
      fig.append(el("div", "gallery__blank", label));
      gallery.append(fig);
    });
    return;
  }

  media.forEach((item) => {
    const fig = el("figure", "gallery__item");
    if (item.type === "video") {
      const video = el("video");
      video.src = item.src;
      video.controls = true;
      video.preload = "metadata";
      video.playsInline = true;
      if (item.poster) video.poster = item.poster;
      if (item.caption) video.setAttribute("aria-label", item.caption);
      fig.append(video);
    } else {
      const img = el("img");
      img.src = item.src;
      img.alt = item.alt || item.caption || "Marty at a rave";
      img.loading = "lazy";
      fig.append(img);
    }
    if (item.caption) fig.append(el("figcaption", "", item.caption));
    gallery.append(fig);
  });
})();
