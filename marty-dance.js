// 3D Marty, dancing. Loads media/marty/marty-shuffle.fbx with three.js
// (fetched from a CDN) the first time the stage scrolls into view.
import * as THREE from "three";
import { FBXLoader } from "three/addons/loaders/FBXLoader.js";

const stage = document.getElementById("dance-stage");
const toggle = document.getElementById("dance-toggle");
const status = document.getElementById("dance-status");

if (stage) {
  const still = window.matchMedia("(prefers-reduced-motion: reduce)");
  let started = false;

  const io = new IntersectionObserver((entries) => {
    if (entries.some((e) => e.isIntersecting) && !started) {
      started = true;
      io.disconnect();
      start();
    }
  }, { rootMargin: "300px" });
  io.observe(stage);

  function start() {
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      status.textContent = "Your browser can't show 3D, so Marty's dancing in spirit.";
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    stage.append(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 50);
    camera.position.set(0, 1.15, 5.2);
    camera.lookAt(0, 1.0, 0);

    // House lights: soft white from the front, pink and cyan from the wings.
    scene.add(new THREE.HemisphereLight(0xffffff, 0x332244, 2.4));
    const key = new THREE.DirectionalLight(0xffffff, 1.8);
    key.position.set(1.5, 4, 5);
    scene.add(key);
    const pink = new THREE.PointLight(0xff2a93, 30, 12);
    pink.position.set(-3, 2, -1.5);
    scene.add(pink);
    const cyan = new THREE.PointLight(0x19e6ff, 30, 12);
    cyan.position.set(3, 2, -1.5);
    scene.add(cyan);

    const spinner = new THREE.Group(); // drag turns this
    scene.add(spinner);

    function resize() {
      const w = stage.clientWidth;
      const h = stage.clientHeight;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }
    new ResizeObserver(() => { resize(); if (!running) renderer.render(scene, camera); }).observe(stage);
    resize();

    let mixer = null;
    let running = false;
    let playing = !still.matches;
    let onScreen = true;
    const clock = new THREE.Clock();

    function frame() {
      if (!running) return;
      const dt = Math.min(clock.getDelta(), 0.1);
      if (mixer) mixer.update(dt);
      renderer.render(scene, camera);
      requestAnimationFrame(frame);
    }
    function sync() {
      const should = Boolean(mixer) && playing && onScreen && !document.hidden;
      if (should && !running) { running = true; clock.getDelta(); requestAnimationFrame(frame); }
      if (!should) running = false;
      toggle.textContent = playing ? "Pause" : "Play";
      toggle.setAttribute("aria-pressed", String(!playing));
    }

    new IntersectionObserver((entries) => {
      onScreen = entries[entries.length - 1].isIntersecting;
      sync();
    }).observe(stage);
    document.addEventListener("visibilitychange", sync);
    toggle.addEventListener("click", () => { playing = !playing; sync(); });

    // Drag (or arrow keys) to turn him round.
    let dragX = null;
    stage.addEventListener("pointerdown", (e) => { dragX = e.clientX; stage.setPointerCapture(e.pointerId); });
    stage.addEventListener("pointermove", (e) => {
      if (dragX === null) return;
      spinner.rotation.y += (e.clientX - dragX) * 0.012;
      dragX = e.clientX;
      if (!running) renderer.render(scene, camera);
    });
    const drop = () => { dragX = null; };
    stage.addEventListener("pointerup", drop);
    stage.addEventListener("pointercancel", drop);
    stage.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      spinner.rotation.y += e.key === "ArrowLeft" ? -0.3 : 0.3;
      if (!running) renderer.render(scene, camera);
    });

    new FBXLoader().load("media/marty/marty-shuffle.fbx", (model) => {
      // The file ships its own camera and light; ours replace them.
      model.children.filter((c) => c.isCamera || c.isLight).forEach((c) => model.remove(c));
      model.traverse((o) => { if (o.isSkinnedMesh) o.frustumCulled = false; });

      const clip = model.animations[0];
      if (clip) {
        // Keep him on the spot: remove any steady drift from the hips so the loop doesn't wander off.
        for (const track of clip.tracks) {
          if (!/Hips\.position$/.test(track.name)) continue;
          const v = track.values;
          const n = v.length / 3;
          for (const axis of [0, 2]) {
            const first = v[axis];
            const drift = v[(n - 1) * 3 + axis] - first;
            for (let i = 0; i < n; i++) v[i * 3 + axis] -= (drift * i) / (n - 1 || 1);
          }
        }
        mixer = new THREE.AnimationMixer(model);
        mixer.clipAction(clip).play();
        mixer.update(still.matches ? 0.6 : 0);
      }

      // Measure him from his skeleton once he's in the dance pose (the rest pose
      // sits somewhere else entirely), then scale to 2 units tall, feet on the floor.
      model.updateMatrixWorld(true);
      const box = new THREE.Box3();
      const at = new THREE.Vector3();
      model.traverse((o) => { if (o.isBone) box.expandByPoint(o.getWorldPosition(at)); });
      const size = box.getSize(new THREE.Vector3());
      const scale = 2 / (size.y || 1);
      const centre = box.getCenter(new THREE.Vector3());
      model.scale.setScalar(scale);
      model.position.set(-centre.x * scale, -box.min.y * scale, -centre.z * scale);
      spinner.add(model);

      stage.classList.add("is-ready");
      status.textContent = "";
      toggle.hidden = false;
      renderer.render(scene, camera);
      sync();
    }, undefined, () => {
      status.textContent = "Marty's dance didn't load. Refresh to try again.";
    });
  }
}
