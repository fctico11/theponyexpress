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
  } catch {
    say("That didn't go through. Give it another try in a minute.", true);
  }
});

if (input) input.addEventListener("input", () => {
  if (msg.classList.contains("is-error")) say("");
});

// ---------------------------------------------------------------------------
// Background: slow zebra stripes drawn with WebGL, warped (home), spiral (Marty) or a bead pegboard (shop).
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
    precision mediump float;
    uniform vec2 u_res;
    uniform float u_time;
    uniform vec2 u_mouse;
    uniform float u_mode;

    void main() {
      vec2 p = 1.35 * (gl_FragCoord.xy - 0.5 * u_res) / min(u_res.x, u_res.y);
      float t = u_time * 0.11;
      float band;
      float k1;
      float k2;

      if (u_mode > 1.5) {
        // Beads: a pegboard of fused beads, size and colour rippling outward.
        p += (u_mouse - 0.5) * 0.12;
        vec2 g = p * 9.0;
        vec2 id = floor(g);
        vec2 q = fract(g) - 0.5;
        float d = length(q);
        float ring = length(id + 0.5);
        float size = 0.36 + 0.1 * sin(ring * 0.6 - t * 5.0);
        band = (1.0 - smoothstep(size - 0.05, size, d)) * smoothstep(0.07, 0.12, d);
        k1 = 0.5 + 0.5 * sin(id.x * 0.45 + id.y * 0.3 + t * 2.0);
        k2 = 0.5 + 0.5 * sin(ring * 0.45 - t * 1.6);
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
  // <canvas id="trip" data-mode="spiral"> or "beads" switches the pattern.
  gl.uniform1f(gl.getUniformLocation(prog, "u_mode"), ({ spiral: 1, beads: 2 })[canvas.dataset.mode] || 0);

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
