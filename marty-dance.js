// 3D Marty, dancing. Loads media/marty/marty-shuffle.glb with three.js
// (fetched from a CDN) the first time the stage scrolls into view.
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const stage = document.getElementById("dance-stage");
const toggle = document.getElementById("dance-toggle");
const status = document.getElementById("dance-status");
const speed = document.getElementById("dance-speed");
const speedOut = document.getElementById("dance-speed-out");
const controls = document.getElementById("dance-controls");

// The source clip starts and ends with Marty standing still. We keep only the
// shuffling in the middle (frames at 30 per second) and ease the last few
// frames back into the first so it repeats without a jump.
const LOOP = { from: 30, to: 125, blend: 10 };

function loopClip(clip) {
  const length = LOOP.to - LOOP.from;
  const tracks = clip.tracks.map((track) => {
    const size = track.getValueSize();
    const src = track.values;
    if (track.times.length <= LOOP.to || LOOP.from < LOOP.blend) return track;
    const step = track.times[1] - track.times[0];
    const isRotation = track instanceof THREE.QuaternionKeyframeTrack;
    const times = new Float32Array(length + 1);
    const values = new Float32Array((length + 1) * size);
    for (let j = 0; j <= length; j++) {
      const at = (LOOP.from + j) * size;
      times[j] = j * step;
      const k = j - (length - LOOP.blend);
      if (k <= 0) {
        for (let c = 0; c < size; c++) values[j * size + c] = src[at + c];
        continue;
      }
      // Blend towards the frames that lead into the loop's first frame.
      const t = k / LOOP.blend;
      const w = t * t * (3 - 2 * t);
      const lead = (LOOP.from - LOOP.blend + k) * size;
      if (isRotation) {
        THREE.Quaternion.slerpFlat(values, j * size, src, at, src, lead, w);
      } else {
        for (let c = 0; c < size; c++) values[j * size + c] = src[at + c] + (src[lead + c] - src[at + c]) * w;
      }
    }
    return new track.constructor(track.name, times, values);
  });
  return new THREE.AnimationClip("shuffle-loop", -1, tracks);
}

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
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    stage.append(renderer.domElement);

    const scene = new THREE.Scene();
    // Looking slightly down, so the floor (and his shadow on it) is visible.
    const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 50);
    camera.position.set(0, 1.45, 6.2);
    camera.lookAt(0, 1.2, 0);

    // Soft white from the front, a warm fill, and pink and cyan rims from behind.
    scene.add(new THREE.HemisphereLight(0xffffff, 0x2a1a44, 1.5));
    const key = new THREE.DirectionalLight(0xffffff, 2.6);
    key.position.set(1.5, 4, 5);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xffe9d6, 0.9);
    fill.position.set(-3, 1.5, 4);
    scene.add(fill);
    const pink = new THREE.SpotLight(0xff2a93, 90, 14, 0.9, 0.6);
    pink.position.set(-3.2, 3, -2.6);
    scene.add(pink, pink.target);
    const cyan = new THREE.SpotLight(0x19e6ff, 90, 14, 0.9, 0.6);
    cyan.position.set(3.2, 3, -2.6);
    scene.add(cyan, cyan.target);
    pink.target.position.set(0, 1, 0);
    cyan.target.position.set(0, 1, 0);

    const spinner = new THREE.Group(); // drag turns this
    scene.add(spinner);

    // The floor: a pool of light, with a soft shadow that follows him around.
    function spot(stops) {
      const c = document.createElement("canvas");
      c.width = c.height = 256;
      const g = c.getContext("2d");
      const fade = g.createRadialGradient(128, 128, 0, 128, 128, 128);
      stops.forEach(([at, colour]) => fade.addColorStop(at, colour));
      g.fillStyle = fade;
      g.fillRect(0, 0, 256, 256);
      const texture = new THREE.CanvasTexture(c);
      texture.colorSpace = THREE.SRGBColorSpace;
      return texture;
    }
    function decal(size, texture, height) {
      const mesh = new THREE.Mesh(
        new THREE.PlaneGeometry(size, size),
        new THREE.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false, toneMapped: false })
      );
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.y = height;
      mesh.renderOrder = -1;
      return mesh;
    }
    scene.add(decal(4.2, spot([[0, "rgba(198,255,31,0.5)"], [0.45, "rgba(198,255,31,0.2)"], [1, "rgba(198,255,31,0)"]]), 0));
    const shadow = decal(2.0, spot([[0, "rgba(0,0,0,0.8)"], [0.5, "rgba(0,0,0,0.4)"], [1, "rgba(0,0,0,0)"]]), 0.01);
    scene.add(shadow);
    let hips = null;
    const hipsAt = new THREE.Vector3();

    function resize() {
      const w = stage.clientWidth;
      const h = stage.clientHeight;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }
    new ResizeObserver(() => { resize(); if (!running) paint(); }).observe(stage);
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
      paint();
      requestAnimationFrame(frame);
    }
    function paint() {
      if (hips) {
        hips.getWorldPosition(hipsAt);
        shadow.position.x = hipsAt.x;
        shadow.position.z = hipsAt.z;
      }
      renderer.render(scene, camera);
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
    function setSpeed() {
      const rate = Number(speed.value) || 1;
      if (mixer) mixer.timeScale = rate;
      speedOut.textContent = `${rate}×`;
    }
    speed.addEventListener("input", setSpeed);

    // Drag (or arrow keys) to turn him round.
    let dragX = null;
    stage.addEventListener("pointerdown", (e) => { dragX = e.clientX; stage.setPointerCapture(e.pointerId); });
    stage.addEventListener("pointermove", (e) => {
      if (dragX === null) return;
      spinner.rotation.y += (e.clientX - dragX) * 0.012;
      dragX = e.clientX;
      if (!running) paint();
    });
    const drop = () => { dragX = null; };
    stage.addEventListener("pointerup", drop);
    stage.addEventListener("pointercancel", drop);
    stage.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      spinner.rotation.y += e.key === "ArrowLeft" ? -0.3 : 0.3;
      if (!running) paint();
    });

    // The model is Marty's scan re-rigged in Blender: a skeleton fitted to his
    // rope limbs and pom-pom hands and feet, with the shuffle retargeted onto it.
    new GLTFLoader().load("media/marty/marty-shuffle.glb", (gltf) => {
      const model = gltf.scene;
      model.traverse((o) => {
        if (!o.isSkinnedMesh) return;
        o.frustumCulled = false;
        const map = o.material.map || null;
        if (map) map.anisotropy = renderer.capabilities.getMaxAnisotropy();
        // Matte and plush, whatever the file's material says.
        o.material = new THREE.MeshStandardMaterial({ map, roughness: 1, metalness: 0 });
      });
      hips = model.getObjectByName("mixamorigHips") || null;

      const clip = gltf.animations[0] && loopClip(gltf.animations[0]);
      if (clip) {
        mixer = new THREE.AnimationMixer(model);
        mixer.clipAction(clip).play();
      }

      const stand = new THREE.Group();
      stand.add(model);

      // Measure the actual skin (not the skeleton) across the whole dance, so he
      // is sized and centred for every pose and his feet really touch the floor.
      const box = new THREE.Box3();
      const at = new THREE.Vector3();
      const skins = [];
      model.traverse((o) => { if (o.isSkinnedMesh) skins.push(o); });
      const samples = clip ? 16 : 1;
      for (let i = 0; i < samples; i++) {
        if (mixer) mixer.setTime((clip.duration * i) / samples);
        stand.updateMatrixWorld(true);
        for (const skin of skins) {
          skin.skeleton.update();
          const count = skin.geometry.attributes.position.count;
          for (let v = 0; v < count; v += 5) {
            skin.getVertexPosition(v, at).applyMatrix4(skin.matrixWorld);
            box.expandByPoint(at);
          }
        }
      }
      if (mixer) {
        mixer.setTime(still.matches ? 0.6 : 0);
        mixer.timeScale = Number(speed.value) || 1;
      }
      const size = box.getSize(new THREE.Vector3());
      const scale = 2.5 / (size.y || 1);
      const centre = box.getCenter(new THREE.Vector3());
      stand.scale.setScalar(scale);
      stand.position.set(-centre.x * scale, -box.min.y * scale, -centre.z * scale);
      spinner.add(stand);

      stage.classList.add("is-ready");
      status.textContent = "";
      controls.hidden = false;
      setSpeed();
      paint();
      sync();
    }, undefined, () => {
      status.textContent = "Marty's dance didn't load. Refresh to try again.";
    });
  }
}
