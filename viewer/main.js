import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { PointerLockControls } from "three/addons/controls/PointerLockControls.js";

const SLAB = 0.25;
const EYE = 1.62;

// ---------- renderer / scene ----------
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
document.getElementById("app").appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xbfd9f2);
scene.fog = new THREE.Fog(0xbfd9f2, 120, 280);

const camera = new THREE.PerspectiveCamera(58, innerWidth / innerHeight, 0.05, 500);

// lights
const hemi = new THREE.HemisphereLight(0xeaf3ff, 0x6f7a66, 0.85);
scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff2dd, 2.6);
sun.position.set(-14, 24, 10);
sun.castShadow = true;
sun.shadow.mapSize.set(4096, 4096);
sun.shadow.camera.left = -25; sun.shadow.camera.right = 25;
sun.shadow.camera.top = 25; sun.shadow.camera.bottom = -25;
sun.shadow.bias = -0.0004;
scene.add(sun);

// ---------- materials ----------
const M = {
  wallExt: new THREE.MeshStandardMaterial({ color: 0xf2efe9, roughness: 0.9 }),
  wallMamad: new THREE.MeshStandardMaterial({ color: 0xe8e4dc, roughness: 0.9 }),
  slab: new THREE.MeshStandardMaterial({ color: 0xd8d4cc, roughness: 0.85 }),
  floorWood: new THREE.MeshStandardMaterial({ color: 0xc9a37c, roughness: 0.65 }),
  floorTerr: new THREE.MeshStandardMaterial({ color: 0xd9d2c4, roughness: 0.9 }),
  glass: new THREE.MeshPhysicalMaterial({
    color: 0x9fc8e0, transmission: 0.85, opacity: 0.45, transparent: true,
    roughness: 0.05, metalness: 0, side: THREE.DoubleSide, depthWrite: false,
  }),
  frame: new THREE.MeshStandardMaterial({ color: 0x3a3f45, roughness: 0.5, metalness: 0.4 }),
  parapet: new THREE.MeshStandardMaterial({ color: 0xeceae4, roughness: 0.9 }),
  stair: new THREE.MeshStandardMaterial({ color: 0xcfc8bb, roughness: 0.8 }),
  door: new THREE.MeshStandardMaterial({ color: 0x7d5a3c, roughness: 0.7 }),
  lawn: new THREE.MeshStandardMaterial({ color: 0x7da05c, roughness: 1 }),
  paving: new THREE.MeshStandardMaterial({ color: 0xc8c2b6, roughness: 0.95 }),
};

// ---------- helpers ----------
function shapeFromPoly(poly) {
  const s = new THREE.Shape(poly.outer.map(([x, y]) => new THREE.Vector2(x, y)));
  for (const h of poly.holes) s.holes.push(new THREE.Path(h.map(([x, y]) => new THREE.Vector2(x, y))));
  return s;
}

// extrude a 2D (x,y) shape vertically: plan x -> world x, plan y -> world -z, up -> +y
function extrude(poly, z0, z1, mat) {
  const geo = new THREE.ExtrudeGeometry(shapeFromPoly(poly), { depth: z1 - z0, bevelEnabled: false });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.y = z0;
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

function boxMesh(x0, y0, x1, y1, z0, z1, mat) {
  const g = new THREE.BoxGeometry(Math.max(x1 - x0, 0.01), Math.max(z1 - z0, 0.01), Math.max(y1 - y0, 0.01));
  const m = new THREE.Mesh(g, mat);
  m.position.set((x0 + x1) / 2, (z0 + z1) / 2, -(y0 + y1) / 2);
  m.castShadow = true;
  m.receiveShadow = true;
  return m;
}

// ---------- model ----------
const model = await (await fetch("./house.json")).json();
const groups = { ground: new THREE.Group(), first: new THREE.Group(), stairroom: new THREE.Group(), roofs: new THREE.Group(), site: new THREE.Group() };
Object.values(groups).forEach((g) => scene.add(g));

const FLOOR_NAMES = ["ground", "first", "stairroom"];

for (const name of FLOOR_NAMES) {
  const fl = model.floors[name];
  const g = groups[name];
  const wallTop = fl.top - SLAB;

  for (const w of fl.walls) g.add(extrude(w, fl.z, wallTop, name === "ground" ? M.wallExt : M.wallExt));

  // openings: sill / lintel / glass / doors
  for (const o of fl.openings) {
    const [x0, y0, x1, y1] = o.rect;
    const sill = fl.z + o.sill, head = fl.z + o.head;
    if (o.sill > 0.05) g.add(boxMesh(x0, y0, x1, y1, fl.z, sill, M.wallExt));
    if (head < wallTop) g.add(boxMesh(x0, y0, x1, y1, head, wallTop, M.wallExt));
    const horiz = (x1 - x0) >= (y1 - y0);
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
    if (o.kind === "door") {
      // open passage with thin top lintel already added; add open door leaf hint
      continue;
    }
    if (o.kind === "entry") {
      // door slab, slightly ajar look: keep closed for simplicity
      const t = 0.06;
      const dm = horiz
        ? boxMesh(x0 + 0.03, cy - t / 2, x1 - 0.03, cy + t / 2, fl.z, fl.z + Math.min(2.1, o.head), M.door)
        : boxMesh(cx - t / 2, y0 + 0.03, cx + t / 2, y1 - 0.03, fl.z, fl.z + Math.min(2.1, o.head), M.door);
      // doors on main entry get glass sidelight if wide
      g.add(dm);
      continue;
    }
    // window / glazing: frame + glass
    const t = 0.05;
    const gm = horiz
      ? boxMesh(x0, cy - t / 2, x1, cy + t / 2, sill, head, M.glass)
      : boxMesh(cx - t / 2, y0, cx + t / 2, y1, sill, head, M.glass);
    gm.castShadow = false;
    g.add(gm);
    const ft = 0.07;
    const fr = horiz
      ? [boxMesh(x0, cy - ft / 2, x0 + ft, cy + ft / 2, sill, head, M.frame),
         boxMesh(x1 - ft, cy - ft / 2, x1, cy + ft / 2, sill, head, M.frame),
         boxMesh(x0, cy - ft / 2, x1, cy + ft / 2, sill, sill + ft, M.frame),
         boxMesh(x0, cy - ft / 2, x1, cy + ft / 2, head - ft, head, M.frame)]
      : [boxMesh(cx - ft / 2, y0, cx + ft / 2, y0 + ft, sill, head, M.frame),
         boxMesh(cx - ft / 2, y1 - ft, cx + ft / 2, y1, sill, head, M.frame),
         boxMesh(cx - ft / 2, y0, cx + ft / 2, y1, sill, sill + ft, M.frame),
         boxMesh(cx - ft / 2, y0, cx + ft / 2, y1, head - ft, head, M.frame)];
    fr.forEach((f) => g.add(f));
  }
}

// interior floor finishes (top of each slab, inside footprint)
for (const name of FLOOR_NAMES) {
  const fl = model.floors[name];
  for (const fp of fl.footprint) {
    const geo = new THREE.ShapeGeometry(shapeFromPoly(fp));
    const mesh = new THREE.Mesh(geo, name === "stairroom" ? M.floorTerr : M.floorWood);
    mesh.rotation.x = -Math.PI / 2;
    mesh.position.y = fl.z + 0.005;
    mesh.receiveShadow = true;
    groups[name].add(mesh);
  }
}

// slabs + parapets
for (const s of model.slabs) {
  const grp = s.z === 0 ? groups.ground : groups.roofs;
  for (const p of s.poly) grp.add(extrude(p, s.z - s.thick, s.z, M.slab));
  for (const seg of s.parapets) {
    const [[ax, ay], [bx, by]] = seg;
    const t = model.meta.parapet_t, h = model.meta.parapet_h;
    const dx = bx - ax, dy = by - ay;
    const L = Math.hypot(dx, dy);
    if (L < 0.05) continue;
    const nx = -dy / L * t / 2, ny = dx / L * t / 2;
    const xs = [ax + nx, ax - nx, bx + nx, bx - nx];
    const ys = [ay + ny, ay - ny, by + ny, by - ny];
    grp.add(boxMesh(Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys), s.z, s.z + h, M.parapet));
  }
}

// walkable terrace floors (top of roof slabs already there via slab tops)

// ---------- stairs ----------
for (const st of model.stairs) {
  const [x0, y0, x1, y1] = st.core;
  const W = (y1 - y0) / 2 - 0.02;            // flight width (two runs side by side)
  const rise = (st.z1 - st.z0) / st.risers;
  const lowerN = Math.ceil(st.risers / 2), upperN = st.risers - lowerN;
  const landW = 1.0;
  const runLen = (x1 - x0) - landW;
  // lower flight: along south edge, from east end going west & up
  for (let i = 0; i < lowerN; i++) {
    const tx1 = x1 - (runLen / lowerN) * i;
    const tx0 = tx1 - runLen / lowerN;
    groups.first.add(boxMesh(tx0, y0, tx1, y0 + W, st.z0, st.z0 + rise * (i + 1), M.stair));
  }
  // landing at west
  groups.first.add(boxMesh(x0, y0, x0 + landW, y1, st.z0, st.z0 + rise * lowerN, M.stair));
  // upper flight: along north edge, from west going east & up
  for (let i = 0; i < upperN; i++) {
    const tx0 = x0 + landW + (runLen / upperN) * i;
    const tx1 = tx0 + runLen / upperN;
    groups.first.add(boxMesh(tx0, y1 - W, tx1, y1, st.z0, st.z0 + rise * (lowerN + i + 1), M.stair));
  }
}

// ---------- site ----------
{
  const lawn = new THREE.Mesh(new THREE.CylinderGeometry(90, 90, 0.4, 48), M.lawn);
  lawn.position.y = -0.21;
  lawn.receiveShadow = true;
  groups.site.add(lawn);
  // paving apron around the house
  const fp = model.floors.ground.footprint[0];
  if (fp) {
    const xs = fp.outer.map((p) => p[0]), ys = fp.outer.map((p) => p[1]);
    const pad = 3.2;
    const pv = boxMesh(Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) + pad, Math.max(...ys) + pad, -0.02, 0.0, M.paving);
    pv.receiveShadow = true;
    groups.site.add(pv);
  }
}

// ---------- camera modes ----------
const fp0 = model.floors.ground.footprint[0];
const fxs = fp0.outer.map((p) => p[0]), fys = fp0.outer.map((p) => p[1]);
const cx = (Math.min(...fxs) + Math.max(...fxs)) / 2;
const cy = (Math.min(...fys) + Math.max(...fys)) / 2;
const center = new THREE.Vector3(cx, 3.2, -cy);
camera.position.set(cx - 12, 11, -cy + 10);
const orbit = new OrbitControls(camera, renderer.domElement);
orbit.target.copy(center);
orbit.enableDamping = true;
orbit.maxPolarAngle = Math.PI * 0.495;

const plock = new PointerLockControls(camera, renderer.domElement);
let mode = "orbit";
const keys = {};
let velY = 0;
let walkLevel = 0; // index into levels
const LEVELS_Y = [0, 3.38, 6.78];

const hint = document.getElementById("hint");
const cross = document.getElementById("crosshair");
const lvlInd = document.getElementById("level-ind");

function setMode(m) {
  mode = m;
  document.getElementById("btn-orbit").classList.toggle("active", m === "orbit");
  document.getElementById("btn-walk").classList.toggle("active", m === "walk");
  document.getElementById("keys-orbit").style.display = m === "orbit" ? "" : "none";
  document.getElementById("keys-walk").style.display = m === "walk" ? "" : "none";
  hint.style.display = m === "walk" ? "" : "none";
  cross.style.display = "none";
  lvlInd.style.display = m === "walk" ? "" : "none";
  orbit.enabled = m === "orbit";
  if (m === "walk") {
    camera.position.set(cx, LEVELS_Y[walkLevel] + EYE, -cy + 4);
    camera.lookAt(cx, LEVELS_Y[walkLevel] + EYE, -cy - 4);
    updateLvl();
  } else {
    plock.unlock();
    camera.position.set(cx - 12, 11, -cy + 10);
    orbit.target.copy(center);
  }
}
function updateLvl() {
  const names = ["Ground floor", "First floor", "Roof terrace"];
  lvlInd.textContent = names[walkLevel] + "  ·  E/Q to change level";
}
document.getElementById("btn-orbit").onclick = () => setMode("orbit");
document.getElementById("btn-walk").onclick = () => setMode("walk");
renderer.domElement.addEventListener("click", () => { if (mode === "walk" && !plock.isLocked) plock.lock(); });
plock.addEventListener("lock", () => { hint.style.display = "none"; cross.style.display = ""; });
plock.addEventListener("unlock", () => { if (mode === "walk") { hint.style.display = ""; cross.style.display = "none"; } });

addEventListener("keydown", (e) => {
  keys[e.code] = true;
  if (mode === "walk" && plock.isLocked) {
    if (e.code === "KeyE") { walkLevel = Math.min(2, walkLevel + 1); camera.position.y = LEVELS_Y[walkLevel] + EYE; updateLvl(); }
    if (e.code === "KeyQ") { walkLevel = Math.max(0, walkLevel - 1); camera.position.y = LEVELS_Y[walkLevel] + EYE; updateLvl(); }
  }
});
addEventListener("keyup", (e) => (keys[e.code] = false));

// floor visibility
for (const [id, grp] of [["vis-ground", "ground"], ["vis-first", "first"], ["vis-stairroom", "stairroom"], ["vis-roofs", "roofs"]]) {
  document.getElementById(id).addEventListener("change", (e) => (groups[grp].visible = e.target.checked));
}

// ---------- loop ----------
const clock = new THREE.Clock();
function tick() {
  requestAnimationFrame(tick);
  const dt = Math.min(clock.getDelta(), 0.05);
  if (mode === "orbit") {
    orbit.update();
  } else if (plock.isLocked) {
    const sp = (keys.ShiftLeft || keys.ShiftRight ? 5.2 : 2.6) * dt;
    if (keys.KeyW) plock.moveForward(sp);
    if (keys.KeyS) plock.moveForward(-sp);
    if (keys.KeyA) plock.moveRight(-sp);
    if (keys.KeyD) plock.moveRight(sp);
    camera.position.y = LEVELS_Y[walkLevel] + EYE; // stay on level
  }
  renderer.render(scene, camera);
}
tick();

addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

setMode("orbit");

// scripted camera hook (used by screenshot tooling)
window.__setCam = ({ pos, look, vis }) => {
  if (vis) for (const k of Object.keys(groups)) groups[k].visible = vis.includes(k);
  if (pos) camera.position.set(pos[0], pos[1], pos[2]);
  if (look) { orbit.target.set(look[0], look[1], look[2]); orbit.update(); }
};
