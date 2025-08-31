"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { PLYLoader } from "three/examples/jsm/loaders/PLYLoader.js";

export default function PlyViewer({ plyUrl, trajUrl, pointsUrl, height = "100vh" }) {
  const containerRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const uiScaleRef = useRef(0.5); // marker 크기 내부 스케일
  const rescaleFnRef = useRef(() => {});

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b0b0b);

    const camera = new THREE.PerspectiveCamera(
      75,
      container.clientWidth / container.clientHeight,
      0.01,
      10000
    );
    camera.position.set(5, 5, 5);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio ?? 1, 2));
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    scene.add(new THREE.AmbientLight(0x808080));
    const dir = new THREE.DirectionalLight(0xffffff, 1);
    dir.position.set(1, 1, 1);
    scene.add(dir);

    const grid = new THREE.GridHelper(100, 100, 0x333333, 0x333333);
    scene.add(grid);

    const world = new THREE.Group();
    world.rotation.x = (130 * Math.PI) / 180;
    world.rotation.y = (5 * Math.PI) / 180;
    scene.add(world);

    const plyLoader = new PLYLoader();

    let pointCloud = null;
    let markersMesh = null;
    let glowPoints = null;
    let bboxDiag = 0;
    let coordsArray = null;

    function fitTo(obj) {
      const box = new THREE.Box3().setFromObject(obj);
      if (box.isEmpty()) return;
      const size = new THREE.Vector3();
      const center = new THREE.Vector3();
      box.getSize(size);
      box.getCenter(center);
      bboxDiag = size.length();

      const maxDim = Math.max(size.x, size.y, size.z) || 1;
      // 조금 더 가까이 보기 (기존 1.2 -> 0.8)
      const dist = (maxDim * 0.8) / Math.tan((Math.PI * camera.fov) / 360);
      const dirV = new THREE.Vector3(1, 0.8, 1).normalize();
      camera.position.copy(center.clone().add(dirV.multiplyScalar(dist)));
      camera.near = Math.max(dist / 1000, 0.01);
      camera.far = dist * 1000;
      camera.updateProjectionMatrix();
      controls.target.copy(center);
      controls.update();
    }

    function loadPLYFromArrayBuffer(buf) {
      const geometry = plyLoader.parse(buf);
      geometry.computeVertexNormals();
      const hasColor = !!geometry.getAttribute("color");
      const mat = new THREE.PointsMaterial({ size: 0.02, vertexColors: hasColor });
      if (!hasColor) {
        mat.color.set(0x00ff00);
        mat.vertexColors = false;
      }

      if (pointCloud) {
        world.remove(pointCloud);
        pointCloud.geometry?.dispose();
      }
      pointCloud = new THREE.Points(geometry, mat);
      world.add(pointCloud);
      fitTo(pointCloud);

      if (coordsArray?.length) drawMarkers(coordsArray, true);
    }

    async function loadPLYFromUrl(url) {
      setLoading(true);
      try {
        const r = await fetch(url, { cache: "no-store" });
        const buf = await r.arrayBuffer();
        loadPLYFromArrayBuffer(buf);
      } finally {
        setLoading(false);
      }
    }

    function parseCoordsText(text) {
      try {
        const j = JSON.parse(text);
        const arr = Array.isArray(j) ? j : j.points || j.coords || [];
        return arr
          .map((v) => {
            if (Array.isArray(v) && v.length >= 3) return [+v[0], +v[1], +v[2]];
            if (v && typeof v === "object") return [+v.x, +v.y, +v.z];
            return null;
          })
          .filter((v) => v && v.every(Number.isFinite));
      } catch (_) {
        const lines = text
          .split(/\r?\n/)
          .map((s) => s.trim())
          .filter((s) => s && !s.startsWith("#"));
        const out = [];
        if (!lines.length) return out;
        const first = lines[0].toLowerCase();
        const isHeader = first.includes("x") && first.includes("y") && first.includes("z");
        if (isHeader) {
          const d = first.includes(",") ? "," : /\s+/;
          const cols = lines.shift().split(d).map((s) => s.trim().toLowerCase());
          const ix = cols.indexOf("x"), iy = cols.indexOf("y"), iz = cols.indexOf("z");
          for (const line of lines) {
            const p = line.split(d).map(Number);
            const x = p[ix], y = p[iy], z = p[iz];
            if ([x, y, z].every(Number.isFinite)) out.push([x, y, z]);
          }
          return out;
        }
        for (const line of lines) {
          const d = line.includes(",") ? "," : /\s+/;
          const p = line.split(d).map(Number);
          if (p.length >= 3 && [p[0], p[1], p[2]].every(Number.isFinite)) out.push([p[0], p[1], p[2]]);
        }
        return out;
      }
    }

    function diagOf(list) {
      const box = new THREE.Box3();
      const v = new THREE.Vector3();
      for (const [x, y, z] of list) {
        v.set(x, y, z);
        box.expandByPoint(v);
      }
      return box.getSize(new THREE.Vector3()).length();
    }

    function baseMarkerRadius(list) {
      const diagPts = diagOf(list) || 1;
      const base = bboxDiag > 1e-6 ? bboxDiag / 120 : diagPts / 40;
      return Math.max(base, 0.02) * uiScaleRef.current;
    }

    function makeGlowTexture() {
      const size = 128;
      const canvas = document.createElement("canvas");
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext("2d");
      const grd = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
      grd.addColorStop(0.0, "rgba(255, 40, 40, 1.0)");
      grd.addColorStop(0.35, "rgba(255, 40, 40, 0.55)");
      grd.addColorStop(1.0, "rgba(255, 40, 40, 0.0)");
      ctx.fillStyle = grd;
      ctx.fillRect(0, 0, size, size);
      const tex = new THREE.CanvasTexture(canvas);
      tex.minFilter = THREE.LinearFilter;
      tex.magFilter = THREE.LinearFilter;
      tex.generateMipmaps = false;
      return tex;
    }

    function drawMarkers(list, rescaleOnly = false) {
      coordsArray = list;
      if (rescaleOnly && markersMesh) {
        const r = baseMarkerRadius(list);
        const s = new THREE.Vector3(r, r, r);
        const q = new THREE.Quaternion();
        const m = new THREE.Matrix4();
        for (let i = 0; i < list.length; i++) {
          const [x, y, z] = list[i];
          m.compose(new THREE.Vector3(x, y, z), q, s);
          markersMesh.setMatrixAt(i, m);
        }
        markersMesh.instanceMatrix.needsUpdate = true;
        return;
      }

      if (markersMesh) {
        world.remove(markersMesh);
        markersMesh.geometry?.dispose();
        (Array.isArray(markersMesh.material) ? markersMesh.material : [markersMesh.material]).forEach((m) =>
          m.dispose?.()
        );
        markersMesh = null;
      }
      if (glowPoints) {
        world.remove(glowPoints);
        glowPoints.geometry?.dispose();
        (Array.isArray(glowPoints.material) ? glowPoints.material : [glowPoints.material]).forEach((m) =>
          m.dispose?.()
        );
        glowPoints = null;
      }

      if (!list?.length) return;

      const N = list.length;
      const r = baseMarkerRadius(list);
      const ico = new THREE.IcosahedronGeometry(1, 1);
      const mat = new THREE.MeshStandardMaterial({
        color: 0xff2a2a,
        emissive: 0x550000,
        metalness: 0.0,
        roughness: 0.35
      });
      const inst = new THREE.InstancedMesh(ico, mat, N);
      inst.instanceMatrix.setUsage(THREE.DynamicDrawUsage);

      const s = new THREE.Vector3(r, r, r);
      const q = new THREE.Quaternion();
      const m = new THREE.Matrix4();
      for (let i = 0; i < N; i++) {
        const [x, y, z] = list[i];
        m.compose(new THREE.Vector3(x, y, z), q, s);
        inst.setMatrixAt(i, m);
      }
      inst.instanceMatrix.needsUpdate = true;
      markersMesh = inst;
      world.add(markersMesh);

      const glowGeom = new THREE.BufferGeometry();
      const pos = new Float32Array(N * 3);
      for (let i = 0; i < N; i++) {
        const [x, y, z] = list[i];
        pos[i * 3 + 0] = x;
        pos[i * 3 + 1] = y;
        pos[i * 3 + 2] = z;
      }
      glowGeom.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      const glowMat = new THREE.PointsMaterial({
        map: makeGlowTexture(),
        size: 24,
        sizeAttenuation: false,
        transparent: true,
        depthWrite: false,
        depthTest: false,
        blending: THREE.AdditiveBlending
      });
      glowPoints = new THREE.Points(glowGeom, glowMat);
      world.add(glowPoints);
    }

    async function loadPointsFromUrl(url) {
      setLoading(true);
      try {
        const r = await fetch(url, { cache: "no-store" });
        const text = await r.text();
        const arr = parseCoordsText(text);
        drawMarkers(arr);
      } finally {
        setLoading(false);
      }
    }

    (async () => {
      try {
        if (plyUrl) await loadPLYFromUrl(plyUrl);
        // 궤적 비활성화: trajUrl 무시
        if (pointsUrl) await loadPointsFromUrl(pointsUrl);
      } catch (e) {
        console.error(e);
      }
    })();

    rescaleFnRef.current = () => {
      if (coordsArray?.length) drawMarkers(coordsArray, true);
    };

    let raf = 0;
    const tick = () => {
      controls.update();
      renderer.render(scene, camera);
      raf = requestAnimationFrame(tick);
    };
    tick();

    const onResize = () => {
      const w = container.clientWidth,
        h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentElement === container) container.removeChild(renderer.domElement);
      scene.traverse((o) => {
        if (o.geometry) o.geometry.dispose();
        const mats = Array.isArray(o.material) ? o.material : [o.material];
        mats.forEach((m) => m?.dispose?.());
      });
    };
  }, [plyUrl, pointsUrl]);

  return (
    <div style={{ position: "relative", width: "100%", height }}>
      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />
      {loading && (
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%,-50%)",
            background: "rgba(0,0,0,0.7)",
            color: "#fff",
            padding: "10px 14px",
            borderRadius: 8
          }}
        >
          로딩 중…
        </div>
      )}
    </div>
  );
}
