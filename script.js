// Waitlist form.
// TODO: not connected to a mailing list yet. Replace the body of `subscribe`
// with a call to your provider (Mailchimp, Buttondown, ConvertKit, etc.).
async function subscribe(email) {
  const list = JSON.parse(localStorage.getItem("zebra-waitlist") || "[]");
  if (!list.includes(email)) list.push(email);
  localStorage.setItem("zebra-waitlist", JSON.stringify(list));
}

const form = document.getElementById("signup");
const input = document.getElementById("email");
const msg = document.getElementById("signup-msg");

function say(text, isError) {
  msg.textContent = text;
  msg.classList.toggle("is-error", Boolean(isError));
  input.setAttribute("aria-invalid", isError ? "true" : "false");
}

// Pages without the signup form (e.g. marty.html) skip this part.
if (form) form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const email = input.value.trim();

  if (!email) {
    say("Pop your email in first so Marty knows where to find you.", true);
    input.focus();
    return;
  }
  if (!input.checkValidity()) {
    say("That email doesn't look right. Check it and try again.", true);
    input.focus();
    return;
  }

  try {
    await subscribe(email);
    form.reset();
    say("You're on the route. Marty's lacing up.");
    // Marty does a little dance to celebrate (a looping flipbook)
    const flip = document.getElementById("signup-flip");
    if (flip) flip.hidden = false;
  } catch {
    say("That didn't go through. Give it another try in a minute.", true);
  }
});

if (input) input.addEventListener("input", () => {
  if (msg.classList.contains("is-error")) say("");
});

// ---------------------------------------------------------------------------
// Phone and tablet menu: a button that opens the header's links in a panel.
// Without JavaScript the links are still in the footer of every page.
// ---------------------------------------------------------------------------
(function menu() {
  const header = document.querySelector(".site-header");
  const nav = header && header.querySelector("nav");
  if (!nav) return;

  const button = document.createElement("button");
  button.type = "button";
  button.className = "nav-toggle";
  button.setAttribute("aria-controls", "site-menu");
  button.innerHTML = "<span></span><span></span><span></span>";

  const panel = document.createElement("div");
  panel.className = "site-menu";
  panel.id = "site-menu";
  panel.setAttribute("role", "navigation");
  panel.setAttribute("aria-label", "Menu");
  nav.querySelectorAll("a").forEach((link) => {
    const copy = link.cloneNode(true);
    copy.removeAttribute("class");
    panel.append(copy);
  });

  function set(open) {
    header.classList.toggle("is-open", open);
    button.setAttribute("aria-expanded", String(open));
    button.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  }
  set(false);
  header.append(button, panel);

  button.addEventListener("click", () => set(!header.classList.contains("is-open")));
  panel.addEventListener("click", (event) => { if (event.target.closest("a")) set(false); });
  document.addEventListener("click", (event) => { if (!header.contains(event.target)) set(false); });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !header.classList.contains("is-open")) return;
    set(false);
    button.focus();
  });
  window.matchMedia("(min-width: 1001px)").addEventListener("change", () => set(false));
})();

// ---------------------------------------------------------------------------
// Background: slow zebra stripes drawn with WebGL, warped (home), lasers and fire (Marty), a bead pegboard (shop) or a lit floor (Dancefloor).
// Falls back to the CSS gradient on #trip if WebGL isn't available.
// ---------------------------------------------------------------------------
(function trip() {
  const canvas = document.getElementById("trip");
  const gl = canvas.getContext("webgl", { antialias: false, alpha: false });
  if (!gl) return;

  const vert = `
    attribute vec2 a;
    void main() { gl_Position = vec4(a, 0.0, 1.0); }`;

  const frag = `
    #ifdef GL_FRAGMENT_PRECISION_HIGH
    precision highp float;
    #else
    precision mediump float;
    #endif
    uniform vec2 u_res;
    uniform float u_time;
    uniform vec2 u_mouse;
    uniform float u_mode;

    float hash(vec2 v) { return fract(sin(dot(v, vec2(127.1, 311.7))) * 43758.5453); }
    float noise(vec2 v) {
      vec2 i = floor(v);
      vec2 f = fract(v);
      f = f * f * (3.0 - 2.0 * f);
      return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
                 mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
    }
    float fbm(vec2 v) {
      float amp = 0.5;
      float sum = 0.0;
      for (int i = 0; i < 4; i++) { sum += amp * noise(v); v *= 2.03; amp *= 0.5; }
      return sum;
    }

    // Pyro: lasers sweeping down through haze, flame cannons along the bottom, embers.
    vec3 pyro() {
      float asp = u_res.x / u_res.y;
      vec2 sc = gl_FragCoord.xy / u_res;
      vec2 s = vec2((sc.x - 0.5) * asp, sc.y);   // x centred, y: 0 at the bottom, 1 at the top
      float tt = u_time;
      vec3 col = vec3(0.014, 0.008, 0.024);

      float haze = 0.45 + 0.9 * fbm(s * 2.6 + vec2(tt * 0.07, -tt * 0.04));
      for (int i = 0; i < 10; i++) {
        float fi = float(i);
        float side = mod(fi, 2.0) * 2.0 - 1.0;
        vec2 o = vec2(side * asp * 0.4, 1.06);
        float a = -1.5708 - side * 0.3 + (u_mouse.x - 0.5) * 0.5
                + 0.8 * sin(tt * (0.3 + 0.06 * fi) + fi * 1.9);
        vec2 dir = vec2(cos(a), sin(a));
        vec2 r = s - o;
        float d = abs(r.x * dir.y - r.y * dir.x);
        float beam = (0.0015 / (d + 0.0015) + 0.06 * exp(-d * 24.0)) * step(0.0, dot(r, dir));
        float pulse = 0.6 + 0.4 * sin(tt * 1.2 + fi * 2.4);
        float m = mod(fi, 4.0);
        vec3 lc = m < 0.5 ? vec3(0.776, 1.0, 0.122)
                : m < 1.5 ? vec3(1.0, 0.165, 0.576)
                : m < 2.5 ? vec3(0.098, 0.902, 1.0)
                : vec3(0.55, 0.3, 1.0);
        col += lc * beam * pulse * haze * 0.75;
      }

      // Five flame cannons that fire in turn, on top of a low bed of fire.
      float jets = 0.0;
      for (int j = 0; j < 5; j++) {
        float fj = float(j);
        float x0 = (fj - 2.0) * asp * 0.21;
        float burst = pow(max(0.0, sin(tt * 0.85 + fj * 1.3)), 6.0);
        float w = (s.x - x0) * 9.0;
        jets += burst * exp(-w * w);
      }
      float height = 0.09 + 0.6 * jets;
      float n = fbm(vec2(s.x * 4.5, s.y * 3.2 - tt * 2.0));
      float heat = clamp((1.0 - s.y / height) + (n - 0.5) * 1.5, 0.0, 1.0);
      heat *= heat;
      vec3 fire = mix(vec3(1.0, 0.12, 0.38), vec3(1.0, 0.5, 0.08), smoothstep(0.1, 0.5, heat));
      fire = mix(fire, vec3(1.0, 0.96, 0.7), smoothstep(0.55, 1.0, heat));
      col = mix(col, fire, smoothstep(0.0, 0.25, heat));
      col += vec3(1.0, 0.35, 0.1) * 0.25 * exp(-s.y * 5.0);   // glow off the fire

      // Embers drifting up.
      vec2 g = vec2(s.x * 15.0, s.y * 9.0 - tt * 1.1);
      vec2 id = floor(g);
      float h = hash(id);
      vec2 e = fract(g) - 0.5 + vec2(sin(tt * 1.5 + h * 6.28) * 0.2, 0.0)
             + (vec2(hash(id + 3.1), hash(id + 7.7)) - 0.5) * 0.55;   // scatter them off the grid
      col += vec3(1.0, 0.65, 0.2) * smoothstep(0.07, 0.0, length(e)) * step(0.82, h) * (1.0 - s.y);

      return col;
    }

    void main() {
      if (u_mode > 3.5) { gl_FragColor = vec4(pyro(), 1.0); return; }
      vec2 p = 1.35 * (gl_FragCoord.xy - 0.5 * u_res) / min(u_res.x, u_res.y);
      float t = u_time * 0.11;
      float band;
      float k1;
      float k2;

      if (u_mode > 2.5) {
        // Floor: lit tiles running to the horizon, re-rolled on the beat.
        float y = 0.16 + (u_mouse.y - 0.5) * 0.08 - p.y;
        float z = 1.0 / max(y, 0.02);
        vec2 g = vec2((p.x + (u_mouse.x - 0.5) * 0.3) * z * 1.5, z * 1.5 + t * 5.0);
        vec2 id = floor(g);
        vec2 q = fract(g);
        float beat = floor(u_time * 2.3333);
        float rnd = fract(sin(dot(id, vec2(12.9898, 78.233)) + beat * 1.7) * 43758.5453);
        float tile = step(0.07, q.x) * step(0.07, q.y);
        float lit = 0.12 + 0.88 * step(0.5, rnd);
        band = tile * lit * smoothstep(0.0, 0.3, y);
        k1 = fract(rnd * 7.31);
        k2 = fract(rnd * 3.17 + 0.2);
      } else if (u_mode > 1.5) {
        // Beads: a pegboard of fused beads, size and colour rippling outward.
        p += (u_mouse - 0.5) * 0.12;
        vec2 g = p * 9.0;
        vec2 id = floor(g);
        vec2 q = fract(g) - 0.5;
        float d = length(q);
        float ring = length(id + 0.5);
        // Kept dim and gently pulsing so it stays a backdrop, not a strobe.
        float size = 0.36 + 0.04 * sin(ring * 0.6 - t * 3.0);
        band = (1.0 - smoothstep(size - 0.05, size, d)) * smoothstep(0.07, 0.12, d) * 0.4;
        k1 = 0.5 + 0.5 * sin(id.x * 0.45 + id.y * 0.3 + t * 1.2);
        k2 = 0.5 + 0.5 * sin(ring * 0.45 - t * 1.0);
      } else if (u_mode > 0.5) {
        // Spiral: four striped arms winding slowly into the centre.
        p += (u_mouse - 0.5) * 0.25;
        float r = length(p) + 0.0001;
        float a = atan(p.y, p.x);
        float wobble = 0.5 * sin(4.0 * a + t * 1.5) + 0.45 * sin(r * 6.0 - t * 2.0);
        float s = sin(13.0 * log(r) + 4.0 * a - t * 3.0 + wobble);
        band = smoothstep(-0.1, 0.1, s) * smoothstep(0.03, 0.14, r);
        k1 = 0.5 + 0.5 * sin(2.0 * a + r * 2.0 + t * 1.5);
        k2 = 0.5 + 0.5 * sin(3.0 * log(r) - t);
      } else {
        // Warp: fold the plane over itself a few times, then stripe it.
        p += (u_mouse - 0.5) * 0.18;
        for (int i = 1; i < 5; i++) {
          float f = float(i);
          p += 0.32 / f * sin(p.yx * f * 1.9 + t * f * 0.7 + vec2(0.0, 1.7));
        }
        float s = sin(p.x * 13.0 + p.y * 4.0 + t * 2.0);
        band = smoothstep(-0.1, 0.1, s);
        k1 = 0.5 + 0.5 * sin(p.y * 3.1 + t * 1.5);
        k2 = 0.5 + 0.5 * sin(p.x * 2.3 - t);
      }

      vec3 acid = vec3(0.776, 1.0, 0.122);
      vec3 pink = vec3(1.0, 0.165, 0.576);
      vec3 uv   = vec3(0.478, 0.231, 1.0);
      vec3 cyan = vec3(0.098, 0.902, 1.0);
      vec3 c = mix(mix(acid, pink, k1), mix(uv, cyan, k1), k2);

      gl_FragColor = vec4(mix(vec3(0.02), c, band), 1.0);
    }`;

  function compile(type, src) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null;
  }
  const vs = compile(gl.VERTEX_SHADER, vert);
  const fs = compile(gl.FRAGMENT_SHADER, frag);
  if (!vs || !fs) return;

  const prog = gl.createProgram();
  gl.attachShader(prog, vs);
  gl.attachShader(prog, fs);
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return;
  gl.useProgram(prog);

  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, "a");
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

  const uRes = gl.getUniformLocation(prog, "u_res");
  const uTime = gl.getUniformLocation(prog, "u_time");
  const uMouse = gl.getUniformLocation(prog, "u_mouse");
  // <canvas id="trip" data-mode="spiral"> "beads", "floor" or "pyro" switches the pattern.
  gl.uniform1f(gl.getUniformLocation(prog, "u_mode"), ({ spiral: 1, beads: 2, floor: 3, pyro: 4 })[canvas.dataset.mode] || 0);

  const mouse = { x: 0.5, y: 0.5, tx: 0.5, ty: 0.5 };
  window.addEventListener("pointermove", (e) => {
    mouse.tx = e.clientX / window.innerWidth;
    mouse.ty = 1 - e.clientY / window.innerHeight;
  }, { passive: true });

  function resize() {
    // Soft stripes don't need full resolution; keep the GPU cost low.
    const scale = Math.min(window.devicePixelRatio || 1, 1.5) * 0.75;
    canvas.width = Math.max(1, Math.round(window.innerWidth * scale));
    canvas.height = Math.max(1, Math.round(window.innerHeight * scale));
    gl.viewport(0, 0, canvas.width, canvas.height);
  }

  function draw(seconds) {
    mouse.x += (mouse.tx - mouse.x) * 0.04;
    mouse.y += (mouse.ty - mouse.y) * 0.04;
    gl.uniform2f(uRes, canvas.width, canvas.height);
    gl.uniform1f(uTime, seconds);
    gl.uniform2f(uMouse, mouse.x, mouse.y);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  const still = window.matchMedia("(prefers-reduced-motion: reduce)");

  // Only animate while a see-through section is on screen.
  let visible = new Set();
  let raf = 0;
  function loop(ms) {
    draw(ms / 1000 + 40);
    raf = requestAnimationFrame(loop);
  }
  function update() {
    cancelAnimationFrame(raf);
    raf = 0;
    if (still.matches) { draw(40); return; }
    if (visible.size && !document.hidden) raf = requestAnimationFrame(loop);
  }

  const io = new IntersectionObserver((entries) => {
    for (const e of entries) e.isIntersecting ? visible.add(e.target) : visible.delete(e.target);
    update();
  });
  document.querySelectorAll(".window").forEach((el) => io.observe(el));

  window.addEventListener("resize", () => { resize(); if (!raf) draw(40); });
  document.addEventListener("visibilitychange", update);
  still.addEventListener("change", update);

  resize();
  draw(40);
})();

// ---------------------------------------------------------------------------
// Privacy policy: a modal opened from the footer's "Privacy" link (or any link to #privacy).
// Edit the policy text here; every page uses this one copy.
// ---------------------------------------------------------------------------
const PRIVACY_HTML = `
  <p class="modal__updated">Last updated: November 17, 2026</p>
  <h2 id="privacy-title">Privacy</h2>
  <p>The short version: we only collect what we need to get mail to your door, we never sell it, and you can ask us to delete it any time.</p>

  <h3>What we collect</h3>
  <ul>
    <li><strong>Your email</strong>, when you join the waitlist or the route.</li>
    <li><strong>Your name and US shipping address</strong>, when you subscribe or order from the shop.</li>
    <li><strong>Payment details</strong> are handled by our payment provider. We never see or store your full card number.</li>
  </ul>

  <h3>What we use it for</h3>
  <ul>
    <li>Sending your monthly envelope and any shop orders.</li>
    <li>Emails about your subscription, each drop, and the occasional news. Every email has an unsubscribe link.</li>
    <li>Answering you when you get in touch.</li>
  </ul>

  <h3>Who else sees it</h3>
  <p>We never sell or rent your details. We share them only with the services that help us run the club, like our email, payment and postage providers, and only what they need to do their job.</p>
  <p>The site loads fonts from Google Fonts and 3D code from jsDelivr, so those services see your IP address when the page loads. Marty's tune only loads Spotify's player if you press play.</p>

  <h3>Cookies</h3>
  <p>We don't use advertising or tracking cookies.</p>

  <h3>Your choices</h3>
  <p>Unsubscribe from emails any time from the link in any email. To see, correct or delete what we hold about you, DM us on <a href="https://www.instagram.com/thezebraexpress/" rel="noopener" target="_blank">Instagram @thezebraexpress</a>. We keep shipping and payment records only as long as the law requires.</p>

  <h3>Kids</h3>
  <p>The Zebra Express is for adults. We don't knowingly collect details from anyone under 18.</p>

  <h3>Changes</h3>
  <p>If this policy changes, we'll update the date at the top. If it's a big change, we'll email members first.</p>
`;

(function modals() {
  let dialog = null;

  function build() {
    dialog = document.createElement("dialog");
    dialog.className = "modal";
    dialog.id = "privacy";
    dialog.setAttribute("aria-labelledby", "privacy-title");
    dialog.innerHTML = `<button class="modal__close" type="button">Close</button><div class="modal__inner">${PRIVACY_HTML}</div>`;
    document.body.append(dialog);
    dialog.querySelector(".modal__close").addEventListener("click", () => dialog.close());
    // a click on the dimmed backdrop (outside the box) closes it too
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener("close", () => {
      if (location.hash === "#privacy") history.replaceState(null, "", location.pathname + location.search);
    });
  }

  function open() {
    if (!dialog) build();
    if (!dialog.open) dialog.showModal();
    dialog.scrollTop = 0;
  }

  document.addEventListener("click", (event) => {
    const link = event.target.closest('a[data-modal="privacy"], a[href="#privacy"]');
    if (!link) return;
    event.preventDefault();
    open();
  });
  if (location.hash === "#privacy") open();
})();
