import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { Grid, Route, RouteFile } from '../types'
import { visibleLoop } from './useScroll'

// The real Slater Plain operations area in 3D: LOLA heights (exaggerated 3x), coloured hour by
// hour with the computed sunlight, and two rovers driving their planned routes. Scrolling
// drives mission time; drag to orbit.
const EXAG = 3

function posAt(route: Route, t: number) {
  const st = route.steps
  let i = 0
  while (i + 1 < st.length && st[i + 1].t_h <= t) i++
  const a = st[i], b = st[i + 1]
  const frozen = route.frozen_at_index !== null && i >= route.frozen_at_index
  if (!b || frozen) return { r: a.row, c: a.col, batt: a.battery_wh, frozen, dir: 0 }
  const f = (t - a.t_h) / (b.t_h - a.t_h || 1)
  return { r: a.row + (b.row - a.row) * f, c: a.col + (b.col - a.col) * f, batt: a.battery_wh + (b.battery_wh - a.battery_wh) * f,
           frozen, dir: Math.atan2(b.col - a.col, b.row - a.row) }
}

function makeRover(color: number) {
  const g = new THREE.Group()
  const mat = new THREE.MeshStandardMaterial({ color: 0xd9dde4, roughness: 0.5, metalness: 0.4 })
  const accent = new THREE.MeshStandardMaterial({ color, roughness: 0.4, metalness: 0.2, emissive: color, emissiveIntensity: 0.35 })
  const body = new THREE.Mesh(new THREE.BoxGeometry(1.1, 0.45, 1.6), mat)
  body.position.y = 0.6
  const panel = new THREE.Mesh(new THREE.BoxGeometry(0.06, 1.2, 1.3), accent)   // vertical, sun-tracking panel
  panel.position.set(0, 1.4, 0)
  const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.8), mat)
  mast.position.set(0.35, 1.1, 0.6)
  g.add(body, panel, mast)
  for (const [x, z] of [[-0.62, -0.55], [0.62, -0.55], [-0.62, 0.55], [0.62, 0.55]]) {
    const w = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.28, 0.18, 16), new THREE.MeshStandardMaterial({ color: 0x2a2f38, roughness: 0.9 }))
    w.rotation.z = Math.PI / 2
    w.position.set(x, 0.28, z)
    g.add(w)
  }
  g.traverse(o => { o.castShadow = true })
  g.scale.setScalar(1.6)
  return { group: g, accent }
}

export function TerrainScene({ grid, rf, t }: { grid: Grid; rf: RouteFile; t: number }) {
  const mount = useRef<HTMLDivElement>(null)
  const tRef = useRef(t)
  tRef.current = t

  useEffect(() => {
    const el = mount.current!
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(Math.min(1.5, window.devicePixelRatio))
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    el.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    scene.fog = new THREE.Fog(0x0c111b, 90, 200)
    const camera = new THREE.PerspectiveCamera(38, 1, 0.5, 600)

    // Terrain: one vertex per grid cell, 1 unit = 1 cell (80 m); heights in cells x EXAG.
    const N = grid.rows, cell = grid.cell_size_m
    const elev = grid.elevation_m.flat()
    const min = Math.min(...elev)
    const geo = new THREE.PlaneGeometry(N - 1, N - 1, N - 1, N - 1)
    geo.rotateX(-Math.PI / 2)
    const pos = geo.attributes.position as THREE.BufferAttribute
    for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) pos.setY(r * N + c, ((grid.elevation_m[r][c] - min) / cell) * EXAG)
    geo.computeVertexNormals()
    const colors = new Float32Array(N * N * 3)
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    const terrain = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1, flatShading: false }))
    terrain.receiveShadow = true
    scene.add(terrain)
    const half = (N - 1) / 2
    const height = (r: number, c: number) => {
      const r0 = Math.max(0, Math.min(N - 1, Math.round(r))), c0 = Math.max(0, Math.min(N - 1, Math.round(c)))
      return ((grid.elevation_m[r0][c0] - min) / cell) * EXAG
    }
    const at = (r: number, c: number, lift = 0.4) => new THREE.Vector3(c - half, height(r, c) + lift, r - half)

    // Routes as glowing tubes just above the ground.
    const routeColor: Record<string, number> = { shortest: 0xf0605d, sunchaser_fast: 0xf2a541, sunchaser_safe: 0x4cc38a }
    for (const route of rf.routes) {
      const pts = route.steps.map(s => at(s.row, s.col, 0.35))
      if (pts.length < 2) continue
      const curve = new THREE.CatmullRomCurve3(pts, false, 'catmullrom', 0.1)
      const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, pts.length * 6, 0.16, 6),
        new THREE.MeshBasicMaterial({ color: routeColor[route.name], transparent: true, opacity: route.name === 'sunchaser_safe' ? 0.5 : 0.9 }))
      scene.add(tube)
    }
    // Start and target beacons.
    for (const p of [rf.start, rf.target]) {
      const beacon = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 6, 8), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.6 }))
      beacon.position.copy(at(p.row, p.col, 3))
      scene.add(beacon)
    }

    const rovers = rf.routes.filter(r => r.name !== 'sunchaser_safe').map(r => ({ route: r, ...makeRover(routeColor[r.name]) }))
    rovers.forEach(r => scene.add(r.group))

    // Grazing sunlight for real shadows on the 3D shapes; the terrain colour carries the computed shadows.
    const sun = new THREE.DirectionalLight(0xfff0d8, 2.2)
    sun.castShadow = true
    sun.shadow.mapSize.set(1024, 1024)
    Object.assign(sun.shadow.camera, { left: -45, right: 45, top: 45, bottom: -45, far: 300 })
    scene.add(sun, sun.target)
    scene.add(new THREE.HemisphereLight(0x8aa0c8, 0x0c111b, 0.55))

    camera.position.set(-48, 52, 62)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableZoom = false
    controls.enableDamping = true
    controls.autoRotate = true
    controls.autoRotateSpeed = 0.35
    controls.target.set(0, 4, 0)

    const resize = () => {
      const w = el.clientWidth, h = el.clientHeight
      renderer.setSize(w, h)
      camera.aspect = w / h
      camera.updateProjectionMatrix()
    }
    resize()
    window.addEventListener('resize', resize)

    const lit = new THREE.Color(0xd9cdb4), dark = new THREE.Color(0x111a2b), steep = new THREE.Color(0x6a3a3a), tmp = new THREE.Color()
    let lastStep = -1
    const frame = () => {
      const time = tRef.current
      const step = Math.min(grid.n_steps - 1, Math.floor(rf.depart_step + time))
      if (step !== lastStep) {
        const sp = grid.sun_pct[step]
        for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
          tmp.copy(dark).lerp(lit, sp[r][c] / 100)
          if (grid.slope_deg[r][c] > 15) tmp.lerp(steep, 0.25)
          const k = (r * N + c) * 3
          colors[k] = tmp.r; colors[k + 1] = tmp.g; colors[k + 2] = tmp.b
        }
        geo.attributes.color.needsUpdate = true
        lastStep = step
      }
      // Low sun circling the horizon, about half a degree per hour.
      const a = time * 0.0089 * Math.PI * 2 + 2.2
      sun.position.set(Math.cos(a) * 120, 22, Math.sin(a) * 120)
      for (const r of rovers) {
        const p = posAt(r.route, time)
        r.group.position.copy(at(p.r, p.c, 0))
        r.group.rotation.y = p.dir
        r.accent.emissiveIntensity = p.frozen ? 0.9 + 0.6 * Math.sin(performance.now() / 160) : 0.35
        if (p.frozen) r.accent.color.set(0x7fc8ff)          // frost blue
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

  return <div ref={mount} className="scene" aria-label="3D terrain of Slater Plain with the two rover routes; drag to orbit" />
}
