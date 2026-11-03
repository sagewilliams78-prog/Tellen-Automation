/**
 * Tellen Core — procedural 3D centerpiece.
 *
 * A floating ring built from three precision-machined curved silver
 * segments around a blue illuminated interior. Built entirely from
 * primitives (no external model) so there's nothing to license or host.
 *
 * Exposes a small controller API consumed by scroll-choreography.js:
 *   create(canvas) -> { setSeparation, setCamera, setStageProgress,
 *                        getHotspotScreenPositions, resize, setQuality,
 *                        pause, resume, dispose }
 *
 * Performance notes:
 *  - Pixel ratio is capped (2 on desktop, 1.5 on mobile).
 *  - Rendering pauses automatically when the tab is hidden or the
 *    canvas is scrolled off-screen (IntersectionObserver), handled by
 *    the caller via pause()/resume().
 *  - No post-processing pipeline: the "bloom" around the blue core is
 *    a cheap additive-blended sprite, not a full bloom pass, by design
 *    (the brief explicitly allows a lightweight technique here).
 */
import * as THREE from "./vendor/three.module.min.js";

const SEGMENT_COUNT = 3;
const RING_RADIUS = 1.7;
const GAP_DEGREES = 10; // gap between segments when fully assembled

// How quickly the camera chases its scroll-driven target each frame (0-1,
// higher = snappier). GSAP's ScrollTrigger scrub is unscrubbed (`scrub: true`
// in opening-experience.js), so camPos/camTarget already update in lockstep
// with the scrollbar with zero added delay — this lerp was the only place
// introducing lag between "you scrolled" and "the camera actually moved".
// 0.08 meant ~36 frames (~0.6s) to settle 95% of the way to a new target,
// which reads as the scene visibly catching up after you stop scrolling
// rather than tracking the scroll. 0.32 settles in ~7 frames (~115ms) —
// still eased enough to avoid raw per-frame scroll jitter, but close
// enough to 1:1 that the ring and camera feel driven by the scroll itself.
const CAMERA_EASE = 0.32;

function isMobile() {
  return window.matchMedia("(max-width: 760px)").matches;
}

/** 2D rounded cross-section for the segment tube (gives the "precision
 * machined" rounded-edge look without a bevel pass). */
function roundedCrossSection(width, height, r) {
  const shape = new THREE.Shape();
  const w = width / 2, h = height / 2;
  shape.moveTo(-w + r, -h);
  shape.lineTo(w - r, -h);
  shape.quadraticCurveTo(w, -h, w, -h + r);
  shape.lineTo(w, h - r);
  shape.quadraticCurveTo(w, h, w - r, h);
  shape.lineTo(-w + r, h);
  shape.quadraticCurveTo(-w, h, -w, h - r);
  shape.lineTo(-w, -h + r);
  shape.quadraticCurveTo(-w, -h, -w + r, -h);
  return shape;
}

/** A segment of a circle in the XZ plane, used as the extrude path. */
class ArcCurve3 extends THREE.Curve {
  constructor(radius, startAngle, endAngle) {
    super();
    this.radius = radius;
    this.startAngle = startAngle;
    this.endAngle = endAngle;
  }
  getPoint(t, target = new THREE.Vector3()) {
    const angle = this.startAngle + (this.endAngle - this.startAngle) * t;
    return target.set(Math.cos(angle) * this.radius, 0, Math.sin(angle) * this.radius);
  }
}

function buildSegmentGeometry(startAngle, endAngle, lowDetail) {
  const shape = roundedCrossSection(0.4, 0.16, 0.06);
  const path = new ArcCurve3(RING_RADIUS, startAngle, endAngle);
  return new THREE.ExtrudeGeometry(shape, {
    steps: lowDetail ? 18 : 28,
    bevelEnabled: false,
    extrudePath: path,
  });
}

/** Cheap canvas-generated radial gradient used for the glow sprite and
 * the soft contact shadow — avoids loading any external texture. */
function radialGradientTexture(innerColor, outerColorAlpha0, size = 256) {
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const ctx = c.getContext("2d");
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, innerColor);
  g.addColorStop(1, outerColorAlpha0);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

/** Builds a small procedural "studio" environment (a few bright panels
 * around the object) and bakes it to a PMREM texture so the metal has
 * something convincing to reflect, without a dark backdrop and without
 * shipping an HDR file. */
function buildStudioEnvironment(renderer) {
  const pmrem = new THREE.PMREMGenerator(renderer);
  pmrem.compileEquirectangularShader();

  const envScene = new THREE.Scene();
  envScene.background = new THREE.Color(0xf5f6f8);

  const panelMat = (color, intensity) =>
    new THREE.MeshBasicMaterial({ color, toneMapped: false });

  const addPanel = (w, h, x, y, z, ry, color, intensity) => {
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w, h), panelMat(color, intensity));
    mesh.position.set(x, y, z);
    mesh.rotation.y = ry;
    envScene.add(mesh);
  };

  // Soft bright panels on most sides, one faint blue-tinted panel to
  // give the metal a hint of the core's own color without relying on
  // a literal dark background anywhere.
  addPanel(8, 8, 0, 0, -6, 0, 0xffffff, 1);
  addPanel(8, 8, 6, 0, 0, -Math.PI / 2, 0xeef1f5, 1);
  addPanel(8, 8, -6, 0, 0, Math.PI / 2, 0xeef1f5, 1);
  addPanel(8, 8, 0, 6, 0, 0, 0xffffff, 1);
  addPanel(8, 8, 0, -6, 0, 0, 0xdfe6f5, 1);
  addPanel(6, 6, 0, 0, 6, Math.PI, 0xcfe0ff, 1);

  const rt = pmrem.fromScene(envScene, 0.04);
  pmrem.dispose();
  return rt.texture;
}

export function create(canvas, { reducedQuality = false } = {}) {
  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: false,
    powerPreference: "high-performance",
  });
  renderer.setClearColor(0xfbfbfc, 1);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = false; // using fake contact shadow instead (perf)

  const lowDetail = isMobile() || reducedQuality;
  const pixelRatioCap = isMobile() ? 1.5 : reducedQuality ? 1.25 : 2;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, pixelRatioCap));

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xfbfbfc);
  // The PMREM studio bake is one extra render pass; skip it on phones /
  // explicit reduced-quality and lean on the direct lights instead —
  // keeps the metal readable without the extra cost.
  if (!lowDetail) scene.environment = buildStudioEnvironment(renderer);

  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 50);
  camera.position.set(2.4, 1.1, 4.2);
  camera.lookAt(0, 0, 0);

  // Key + fill lights on top of the environment map (gives sharper
  // specular highlights than the env alone would). Ambient is kept
  // fairly low so the key light still carves out visible shadow/highlight
  // contrast across the machined facets instead of flattening them.
  const key = new THREE.DirectionalLight(0xffffff, 1.55);
  key.position.set(4, 5, 3);
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xdfe8ff, 0.45);
  fill.position.set(-4, 2, -3);
  scene.add(fill);
  // Cool rim light opposite the key, tinted to match the core's blue glow —
  // separates the ring's silhouette from the light studio backdrop and
  // ties a thin blue edge-highlight on the metal back to the core color.
  const rim = new THREE.DirectionalLight(0x6f9bff, 0.4);
  rim.position.set(-2, -1.5, -5);
  scene.add(rim);
  scene.add(new THREE.AmbientLight(0xffffff, 0.26));

  // ---- Ring segments ----
  const gapRad = (GAP_DEGREES * Math.PI) / 180;
  const segmentSpan = (Math.PI * 2) / SEGMENT_COUNT - gapRad;
  const metalMat = new THREE.MeshPhysicalMaterial({
    color: 0xd9dde3,
    metalness: 1,
    roughness: 0.22,
    clearcoat: 0.4,
    clearcoatRoughness: 0.18,
    envMapIntensity: 1.3,
  });

  const segmentGroup = new THREE.Group();
  const segments = [];
  for (let i = 0; i < SEGMENT_COUNT; i++) {
    const startAngle = i * ((Math.PI * 2) / SEGMENT_COUNT) + gapRad / 2;
    const endAngle = startAngle + segmentSpan;
    const geo = buildSegmentGeometry(startAngle, endAngle, lowDetail);
    const mesh = new THREE.Mesh(geo, metalMat);
    // Outward normal direction at the segment's midpoint — used both to
    // separate the segment along a believable radial path and to place
    // its hotspot anchor.
    const midAngle = (startAngle + endAngle) / 2;
    const normal = new THREE.Vector3(Math.cos(midAngle), 0, Math.sin(midAngle));
    const pivot = new THREE.Group();
    pivot.add(mesh);
    segmentGroup.add(pivot);
    segments.push({ pivot, mesh, normal, midAngle });
  }
  scene.add(segmentGroup);

  // ---- Blue illuminated interior ----
  // flatShading keeps each icosahedron facet a distinct flat plane, so the
  // core reads as a cut, glowing gem rather than a smooth plastic ball —
  // crisper and more "precision machined" to match the ring segments. A
  // thin clearcoat adds a sharp specular pass on top of the emissive glow.
  const coreGeo = new THREE.IcosahedronGeometry(0.62, lowDetail ? 1 : 2);
  const coreMat = new THREE.MeshPhysicalMaterial({
    color: 0x1d3fc9,
    emissive: 0x3f6bff,
    emissiveIntensity: 1.75,
    roughness: 0.22,
    metalness: 0.05,
    clearcoat: 0.6,
    clearcoatRoughness: 0.2,
    flatShading: true,
  });
  const core = new THREE.Mesh(coreGeo, coreMat);
  scene.add(core);

  const glowTex = radialGradientTexture("rgba(80,130,255,0.55)", "rgba(80,130,255,0)");
  const glowMat = new THREE.SpriteMaterial({
    map: glowTex,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const glow = new THREE.Sprite(glowMat);
  glow.scale.set(2.6, 2.6, 1);
  scene.add(glow);

  // ---- Soft grounding shadow (fake, cheap) ----
  const shadowTex = radialGradientTexture("rgba(20,22,26,0.28)", "rgba(20,22,26,0)");
  const shadowMat = new THREE.MeshBasicMaterial({ map: shadowTex, transparent: true, depthWrite: false });
  const shadowMesh = new THREE.Mesh(new THREE.PlaneGeometry(5, 5), shadowMat);
  shadowMesh.rotation.x = -Math.PI / 2;
  shadowMesh.position.y = -1.35;
  scene.add(shadowMesh);

  // ---- Cheap fake floor reflection: a mirrored, faded duplicate ----
  const reflectionGroup = segmentGroup.clone(true);
  reflectionGroup.traverse((obj) => {
    if (obj.isMesh) {
      obj.material = metalMat.clone();
      obj.material.transparent = true;
      obj.material.opacity = 0.14;
      obj.material.roughness = 0.6;
    }
  });
  reflectionGroup.scale.y = -1;
  reflectionGroup.position.y = -2.3;
  scene.add(reflectionGroup);

  // ---- Connecting lines ("Connect" stage: how an inquiry moves
  // between the three services) — restrained, opacity-driven ----
  const lineMat = new THREE.LineBasicMaterial({ color: 0x2f6bff, transparent: true, opacity: 0 });
  const connectLines = [];
  for (let i = 0; i < SEGMENT_COUNT; i++) {
    const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]);
    const line = new THREE.Line(geo, lineMat.clone());
    scene.add(line);
    connectLines.push(line);
  }

  let idleT = 0;
  let pointer = { x: 0, y: 0 };
  let targetPointer = { x: 0, y: 0 };
  let paused = false;
  let destroyed = false;

  function onPointerMove(e) {
    const nx = (e.clientX / window.innerWidth) * 2 - 1;
    const ny = (e.clientY / window.innerHeight) * 2 - 1;
    targetPointer.x = nx;
    targetPointer.y = ny;
  }
  window.addEventListener("pointermove", onPointerMove, { passive: true });

  // Shared state the choreography layer drives every frame.
  const state = {
    separation: 0, // 0 = closed ring, 1 = fully separated
    connect: 0, // 0..1 opacity of the connecting lines/pulses
    camPos: camera.position.clone(),
    camTarget: new THREE.Vector3(0, 0, 0),
  };

  function setSeparation(v) {
    state.separation = v;
  }
  function setConnect(v) {
    state.connect = v;
  }
  function setCamera(pos, target) {
    state.camPos.set(pos.x, pos.y, pos.z);
    state.camTarget.set(target.x, target.y, target.z);
  }

  function getHotspotScreenPositions() {
    const result = [];
    for (const seg of segments) {
      const dist = 0.55 + state.separation * 1.25;
      const worldPos = new THREE.Vector3(
        Math.cos(seg.midAngle) * (RING_RADIUS + dist * 0.4),
        0,
        Math.sin(seg.midAngle) * (RING_RADIUS + dist * 0.4)
      );
      worldPos.applyMatrix4(segmentGroup.matrixWorld);
      const proj = worldPos.clone().project(camera);
      result.push({
        x: (proj.x * 0.5 + 0.5) * canvas.clientWidth,
        y: (1 - (proj.y * 0.5 + 0.5)) * canvas.clientHeight,
        visible: proj.z < 1,
      });
    }
    return result;
  }

  function resize() {
    const w = canvas.clientWidth || 1;
    const h = canvas.clientHeight || 1;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  function animate() {
    if (destroyed) return;
    requestAnimationFrame(animate);
    if (paused) return;

    idleT += 0.0045;
    pointer.x += (targetPointer.x - pointer.x) * 0.04;
    pointer.y += (targetPointer.y - pointer.y) * 0.04;

    // Slow idle rotation + subtle pointer parallax (disabled once the
    // scroll sequence takes over separation, to avoid fighting it).
    const idleInfluence = 1 - Math.min(state.separation * 1.6, 1);
    segmentGroup.rotation.y = idleT * 0.12 + pointer.x * 0.08 * idleInfluence;
    reflectionGroup.rotation.y = segmentGroup.rotation.y;
    core.rotation.y += 0.0025;
    core.rotation.x += 0.0012;

    segments.forEach((seg) => {
      const dist = state.separation * 1.25;
      seg.pivot.position.set(seg.normal.x * dist, pointer.y * 0.05 * idleInfluence, seg.normal.z * dist);
    });

    const glowScale = 2.2 + state.separation * 0.9;
    glow.scale.set(glowScale, glowScale, 1);
    coreMat.emissiveIntensity = 1.55 + state.separation * 0.8;

    // Connecting lines: triangle between the three separated segments,
    // with a travelling pulse implied by a gentle opacity breathe.
    const breathe = 0.65 + 0.35 * Math.sin(idleT * 3);
    segments.forEach((seg, i) => {
      const next = segments[(i + 1) % segments.length];
      const a = seg.pivot.position.clone().add(new THREE.Vector3(seg.normal.x * RING_RADIUS, 0, seg.normal.z * RING_RADIUS));
      const b = next.pivot.position.clone().add(new THREE.Vector3(next.normal.x * RING_RADIUS, 0, next.normal.z * RING_RADIUS));
      const positions = connectLines[i].geometry.attributes.position;
      positions.setXYZ(0, a.x, a.y, a.z);
      positions.setXYZ(1, b.x, b.y, b.z);
      positions.needsUpdate = true;
      connectLines[i].material.opacity = state.connect * 0.5 * breathe;
    });

    camera.position.lerp(state.camPos, CAMERA_EASE);
    const lookTarget = new THREE.Vector3().copy(state.camTarget);
    const currentLook = new THREE.Vector3(0, 0, -1).applyQuaternion(camera.quaternion).add(camera.position);
    currentLook.lerp(lookTarget, CAMERA_EASE);
    camera.lookAt(currentLook);

    renderer.render(scene, camera);
  }
  requestAnimationFrame(animate);

  function pause() { paused = true; }
  function resume() { paused = false; }

  function dispose() {
    destroyed = true;
    window.removeEventListener("pointermove", onPointerMove);
    renderer.dispose();
    scene.traverse((obj) => {
      if (obj.isMesh) {
        obj.geometry.dispose();
        if (Array.isArray(obj.material)) obj.material.forEach((m) => m.dispose());
        else obj.material?.dispose?.();
      }
    });
    glowTex.dispose();
    shadowTex.dispose();
  }

  resize();

  return { setSeparation, setConnect, setCamera, getHotspotScreenPositions, resize, pause, resume, dispose };
}
