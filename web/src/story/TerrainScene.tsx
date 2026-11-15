import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import regolithUrl from '../assets/viz/regolith.jpg'
import type { Grid, Route, RouteFile } from '../types'
import { visibleLoop } from './useScroll'

// The real Slater Plain operations area as a 3D diorama: LRO LOLA heights (exaggerated 3x),
// coloured hour by hour with the sunlight our pipeline computed for every cell, and the two
// rovers driving their planned routes. Scrolling drives mission time; drag to orbit.
//
// The 64 x 64 grid (80 m cells) is upsampled 3x with bilinear interpolation and lightly smoothed
// so the surface reads as terrain rather than blocks; sunlight is interpolated the same way, so
// shadow edges are soft. A tiling regolith texture adds surface grain (illustrative detail only).
const EXAG = 3
const UP = 3

function posAt(route: Route, t: number) {
  const st = route.steps
  let i = 0
  while (i + 1 < st.length && st[i + 1].t_h <= t) i++
  const a = st[i], b = st[i + 1]
  const frozen = route.frozen_at_index !== null && i >= route.frozen_at_index
  if (!b || frozen) return { r: a.row, c: a.col, frozen, dir: null as number | null }
  const f = (t - a.t_h) / (b.t_h - a.t_h || 1)
  const moving = a.row !== b.row || a.col !== b.col
  return { r: a.row + (b.row - a.row) * f, c: a.col + (b.col - a.col) * f, frozen, dir: moving ? Math.atan2(b.col - a.col, b.row - a.row) : null }
}

function makeRover(color: number) {
  const g = new THREE.Group()
  const hull = new THREE.MeshStandardMaterial({ color: 0xe8e4da, roughness: 0.45, metalness: 0.35 })
  const dark = new THREE.MeshStandardMaterial({ color: 0x23262c, roughness: 0.8 })
  const panelMat = new THREE.MeshStandardMaterial({ color: 0x1b2433, roughness: 0.25, metalness: 0.7, emissive: color, emissiveIntensity: 0.25 })
  const body = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.42, 1.6), hull)
  body.position.y = 0.62
  const panel = new THREE.Mesh(new THREE.BoxGeometry(0.06, 1.3, 1.2), panelMat)   // vertical, sun-tracking panel
  panel.position.set(0, 1.55, 0)
  const frameMat = new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.6 })
  const frame = new THREE.Mesh(new THREE.BoxGeometry(0.05, 1.36, 1.26), frameMat)
  frame.position.copy(panel.position)
  const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 0.9), hull)
  mast.position.set(0.38, 1.2, 0.62)
  const dish = new THREE.Mesh(new THREE.SphereGeometry(0.16, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2), hull)
  dish.position.set(0.38, 1.66, 0.62); dish.rotation.x = Math.PI
  g.add(body, frame, panel, mast, dish)
  for (const [x, z] of [[-0.62, -0.6], [0.62, -0.6], [-0.62, 0], [0.62, 0], [-0.62, 0.6], [0.62, 0.6]]) {
    const w = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.24, 0.16, 16), dark)
    w.rotation.z = Math.PI / 2
    w.position.set(x, 0.26, z)
    g.add(w)
  }
  g.traverse(o => { o.castShadow = true })
  g.scale.setScalar(2)
  const glow = new THREE.PointLight(color, 6, 9, 2)
  glow.position.set(0, 2.2, 0)
  g.add(glow)
  return { group: g, frameMat, glow }
}

// Bilinear sample of an N x N field at fractional (r, c).
function bilerp(f: (r: number, c: number) => number, N: number, r: number, c: number) {
  const r0 = Math.max(0, Math.min(N - 1, Math.floor(r))), c0 = Math.max(0, Math.min(N - 1, Math.floor(c)))
  const r1 = Math.min(N - 1, r0 + 1), c1 = Math.min(N - 1, c0 + 1)
  const fr = Math.max(0, Math.min(1, r - r0)), fc = Math.max(0, Math.min(1, c - c0))
  return (f(r0, c0) * (1 - fc) + f(r0, c1) * fc) * (1 - fr) + (f(r1, c0) * (1 - fc) + f(r1, c1) * fc) * fr
}

export function TerrainScene({ grid, rf, t }: { grid: Grid; rf: RouteFile; t: number }) {
  const mount = useRef<HTMLDivElement>(null)
  const tRef = useRef(t)
  tRef.current = t

  useEffect(() => {
    const el = mount.current!
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(Math.min(1.5, window.devicePixelRatio))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.35
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    el.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    scene.fog = new THREE.Fog(0x030303, 110, 230)
    const camera = new THREE.PerspectiveCamera(34, 1, 0.5, 600)

    // --- terrain: upsampled, smoothed heights; 1 unit = 1 grid cell (80 m) ---
    const N = grid.rows, cell = grid.cell_size_m
    const M = (N - 1) * UP + 1
    const min = Math.min(...grid.elevation_m.flat())
    const raw = new Float32Array(M * M)
    for (let i = 0; i < M; i++) for (let j = 0; j < M; j++) raw[i * M + j] = bilerp((r, c) => grid.elevation_m[r][c], N, i / UP, j / UP)
    const hgt = new Float32Array(M * M)   // one 3x3 box-blur pass
    for (let i = 0; i < M; i++) for (let j = 0; j < M; j++) {
      let s = 0, n = 0
      for (let di = -1; di <= 1; di++) for (let dj = -1; dj <= 1; dj++) {
        const a = i + di, b = j + dj
        if (a >= 0 && a < M && b >= 0 && b < M) { s += raw[a * M + b]; n++ }
      }
      hgt[i * M + j] = (((s / n) - min) / cell) * EXAG
    }
    const geo = new THREE.PlaneGeometry(N - 1, N - 1, M - 1, M - 1)
    geo.rotateX(-Math.PI / 2)
    const pos = geo.attributes.position as THREE.BufferAttribute
    for (let k = 0; k < M * M; k++) pos.setY(k, hgt[k])
    geo.computeVertexNormals()
    const uv = geo.attributes.uv as THREE.BufferAttribute   // repeat the regolith grain across the area
    for (let k = 0; k < uv.count; k++) uv.setXY(k, uv.getX(k) * 7, uv.getY(k) * 7)
    const colors = new Float32Array(M * M * 3)
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    const grain = new THREE.TextureLoader().load(regolithUrl)
    grain.wrapS = grain.wrapT = THREE.RepeatWrapping
    grain.colorSpace = THREE.SRGBColorSpace
    grain.anisotropy = 8
    const terrain = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ vertexColors: true, map: grain, bumpMap: grain, bumpScale: 0.6, roughness: 1, metalness: 0 }))
    terrain.receiveShadow = true
    scene.add(terrain)
    const half = (N - 1) / 2
    const heightAt = (r: number, c: number) => bilerp((a, b) => hgt[a * M + b], M, r * UP, c * UP)
    const at = (r: number, c: number, lift = 0.4) => new THREE.Vector3(c - half, heightAt(r, c) + lift, r - half)

    // --- diorama base: skirts down to a plinth, so the block reads as a cut model ---
    const BASE = -5
    const skirtMat = new THREE.MeshStandardMaterial({ color: 0x17150f, roughness: 0.95, side: THREE.DoubleSide })
    const edges: [number, number][][] = [
      Array.from({ length: M }, (_, j): [number, number] => [0, j]), Array.from({ length: M }, (_, j): [number, number] => [M - 1, j]),
      Array.from({ length: M }, (_, i): [number, number] => [i, 0]), Array.from({ length: M }, (_, i): [number, number] => [i, M - 1]),
    ]
    for (const edge of edges) {
      const verts: number[] = [], idx: number[] = []
      edge.forEach(([i, j], k) => {
        const x = j / UP - half, z = i / UP - half
        verts.push(x, hgt[i * M + j], z, x, BASE, z)
        if (k) idx.push(2 * k - 2, 2 * k - 1, 2 * k, 2 * k - 1, 2 * k + 1, 2 * k)
      })
      const g = new THREE.BufferGeometry()
      g.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3))
      g.setIndex(idx)
      g.computeVertexNormals()
      scene.add(new THREE.Mesh(g, skirtMat))
    }
    const plinth = new THREE.Mesh(new THREE.BoxGeometry(N + 5, 1.2, N + 5), new THREE.MeshStandardMaterial({ color: 0x0b0b0a, roughness: 0.6, metalness: 0.3 }))
    plinth.position.y = BASE - 0.6
    plinth.receiveShadow = true
    scene.add(plinth)
    const rim = new THREE.LineSegments(new THREE.EdgesGeometry(plinth.geometry), new THREE.LineBasicMaterial({ color: 0xf2a541, transparent: true, opacity: 0.35 }))
    rim.position.copy(plinth.position)
    scene.add(rim)

    // --- routes: a bright core and a soft additive glow ---
    const routeColor: Record<string, number> = { shortest: 0xf0605d, sunchaser_fast: 0xf2a541, sunchaser_safe: 0x4cc38a }
    for (const route of rf.routes) {
      const pts = route.steps.filter((s, i, a) => !i || s.row !== a[i - 1].row || s.col !== a[i - 1].col).map(s => at(s.row, s.col, 0.45))
      if (pts.length < 2) continue
      const curve = new THREE.CatmullRomCurve3(pts, false, 'catmullrom', 0.2)
      const segs = Math.min(600, pts.length * 8)
      const col = routeColor[route.name]
      scene.add(new THREE.Mesh(new THREE.TubeGeometry(curve, segs, 0.11, 6), new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: route.name === 'sunchaser_safe' ? 0.4 : 0.95 })))
      scene.add(new THREE.Mesh(new THREE.TubeGeometry(curve, segs, 0.42, 8),
        new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.16, blending: THREE.AdditiveBlending, depthWrite: false })))
    }
    // Start and target: rings of light with a faint beam.
    const marker = (p: { row: number; col: number }, color: number) => {
      const g = new THREE.Group()
      const ring = new THREE.Mesh(new THREE.RingGeometry(1.1, 1.35, 48), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.9, side: THREE.DoubleSide }))
      ring.rotation.x = -Math.PI / 2
      const beam = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.5, 9, 16, 1, true),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.16, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }))
      beam.position.y = 4.5
      g.add(ring, beam)
      g.position.copy(at(p.row, p.col, 0.3))
      scene.add(g)
      return ring
    }
    const rings = [marker(rf.start, 0xffffff), marker(rf.target, 0x4cc38a)]

    const rovers = rf.routes.filter(r => r.name !== 'sunchaser_safe').map(r => ({ route: r, color: routeColor[r.name], ...makeRover(routeColor[r.name]) }))
    rovers.forEach(r => scene.add(r.group))

    // Low, warm sunlight for relief shading and rover shadows; the computed shadows are in the terrain colour.
    const sun = new THREE.DirectionalLight(0xffe3b8, 2.4)
    sun.castShadow = true
    sun.shadow.mapSize.set(1024, 1024)
    Object.assign(sun.shadow.camera, { left: -45, right: 45, top: 45, bottom: -45, far: 300 })
    scene.add(sun, sun.target)
    scene.add(new THREE.HemisphereLight(0x9fb3d9, 0x0a0806, 0.45))

    camera.position.set(-60, 54, 78)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableZoom = false
    controls.enableDamping = true
    controls.autoRotate = true
    controls.autoRotateSpeed = 0.3
    controls.maxPolarAngle = Math.PI * 0.42
    controls.target.set(0, 2, 0)

    const resize = () => {
      const w = el.clientWidth, h = el.clientHeight
      renderer.setSize(w, h)
      camera.aspect = w / h
      camera.fov = w / h < 1 ? 52 : 34   // pull back on tall, narrow screens
      camera.updateProjectionMatrix()
    }
    resize()
    window.addEventListener('resize', resize)

    // Computed sunlight -> colour: shadow is a cold blue-black, light is warm regolith.
    const lit = new THREE.Color(0xe9dcc2), dark = new THREE.Color(0x0b1220), steep = new THREE.Color(0x7a3b30), tmp = new THREE.Color()
    let lastStep = -1
    const frame = () => {
      const time = tRef.current
      const step = Math.min(grid.n_steps - 1, Math.floor(rf.depart_step + time))
      if (step !== lastStep) {
        const sp = grid.sun_pct[step]
        for (let i = 0; i < M; i++) for (let j = 0; j < M; j++) {
          const r = i / UP, c = j / UP
          const s = bilerp((a, b) => sp[a][b], N, r, c) / 100
          tmp.copy(dark).lerp(lit, s * s * (3 - 2 * s))   // smoothstep: crisp but soft shadow edge
          if (bilerp((a, b) => grid.slope_deg[a][b], N, r, c) > 15) tmp.lerp(steep, 0.22)
          const k = (i * M + j) * 3
          colors[k] = tmp.r; colors[k + 1] = tmp.g; colors[k + 2] = tmp.b
        }
        geo.attributes.color.needsUpdate = true
        lastStep = step
      }
      const a = time * 0.0089 * Math.PI * 2 + 2.2      // low Sun circling, about half a degree per hour
      sun.position.set(Math.cos(a) * 120, 20, Math.sin(a) * 120)
      const pulse = 0.5 + 0.5 * Math.sin(performance.now() / 400)
      rings.forEach(r => ((r.material as THREE.MeshBasicMaterial).opacity = 0.55 + 0.4 * pulse))
      for (const r of rovers) {
        const p = posAt(r.route, time)
        r.group.position.copy(at(p.r, p.c, 0))
        if (p.dir !== null) r.group.rotation.y = p.dir
        const c = p.frozen ? 0x8fd0ff : r.color   // frost blue: the battery hit zero
        r.frameMat.color.set(c); r.frameMat.emissive.set(c); r.glow.color.set(c)
        r.frameMat.emissiveIntensity = p.frozen ? 0.8 + 0.8 * pulse : 0.6
      }
      controls.update()
      renderer.render(scene, camera)
    }
    const stop = visibleLoop(el, frame)
    return () => {
      stop()
      window.removeEventListener('resize', resize)
      controls.dispose()
      renderer.dispose()
      el.removeChild(renderer.domElement)
    }
  }, [grid, rf])

  return <div ref={mount} className="scene" aria-label="3D model of the Slater Plain terrain with the two rover routes; drag to orbit" />
}
