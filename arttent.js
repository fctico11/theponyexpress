// Renders the Art Tent from art-data.js,
// and handles the art submission form.
(function arttent() {
  const art = window.ART;
  if (!art) return;
  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };

  // ---- the brief: future drops in general, or one drop once its theme is set
  if (art.next) {
    $("brief-tag").textContent = `Now booking · Drop ${art.next.no}`;
    $("brief-title").textContent = art.next.title;
  }
  const brief = $("brief-text");
  art.brief.forEach((p) => brief.append(el("p", null, p)));
  const wanted = $("brief-wanted");
  art.wanted.forEach((w) => wanted.append(el("li", null, w)));

  const deadline = art.deadline ? new Date(art.deadline + "T23:59:00") : null;
  $("brief-deadline").textContent = deadline && !isNaN(deadline)
    ? deadline.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })
    : "Rolling. Submit any time.";

  // ---- the wall of featured work
  const wall = $("wall");
  if (art.featured.length) {
    art.featured.forEach((piece) => {
      const fig = el("figure", "gallery__item");
      const img = el("img");
      img.src = piece.image;
      img.alt = piece.alt || `${piece.title} by ${piece.name}`;
      img.loading = "lazy";
      const cap = el("figcaption");
      cap.append(el("strong", null, piece.title), document.createTextNode(` · ${piece.name}`));
      if (piece.handle) cap.append(document.createTextNode(` ${piece.handle}`));
      if (piece.drop) cap.append(document.createTextNode(` · Drop ${piece.drop}`));
      fig.append(img, cap);
      wall.append(fig);
    });
  } else {
    for (let i = 0; i < 3; i++) {
      const fig = el("figure", "gallery__item");
      fig.append(el("div", "gallery__blank", "Your art here"));
      wall.append(fig);
    }
  }

  // ---- the submission form
  const form = $("submit-form");
  const msg = $("submit-msg");
  const files = $("art-files");
  const fileList = $("art-file-list");
  const MAX_FILES = 5;
  const MAX_MB = 20;

  const say = (text, isError) => {
    msg.textContent = text;
    msg.classList.toggle("is-error", Boolean(isError));
  };

  files.addEventListener("change", () => {
    fileList.textContent = [...files.files].map((f) => f.name).join(", ");
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;

    const picked = [...files.files];
    if (picked.length > MAX_FILES) return say(`Up to ${MAX_FILES} files per submission, please.`, true);
    if (picked.some((f) => f.size > MAX_MB * 1024 * 1024)) return say(`Each file needs to be under ${MAX_MB} MB.`, true);

    // TODO: send to UploadThing. Set uploadUrl in art-data.js once the upload route exists.
    if (!art.uploadUrl) {
      say("Uploads open soon. Follow @thezebraexpress to hear the moment they do.");
      return;
    }

    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    say("Sending…");
    try {
      const res = await fetch(art.uploadUrl, { method: "POST", body: new FormData(form) });
      if (!res.ok) throw new Error(res.statusText);
      form.reset();
      fileList.textContent = "";
      say("Got it. When your piece is picked for a drop, we'll email you before it goes out.");
    } catch (err) {
      say("That didn't go through. Give it another try in a minute.", true);
    } finally {
      button.disabled = false;
    }
  });
})();
