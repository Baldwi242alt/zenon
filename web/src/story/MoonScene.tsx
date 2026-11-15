import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import moonTex from '../assets/moon.jpg'
import { reducedMotion, visibleLoop } from './useScroll'

// The Moon, lit by a Sun skimming its edge. As the page scrolls (progress 0 -> 1) the globe
// tilts until the south pole faces you and the camera moves in. Drag to turn it.
export function MoonScene({ progress }: { progress: number }) {
  const mount = useRef<HTMLDivElement>(null)
  const state = useRef({ progress: 0, dragX: 0, dragY: 0 })
  state.current.progress = progress

  useEffect(() => {
    const el = mount.current!
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(Math.min(1.5, window.devicePixelRatio))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    el.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100)

    const tex = new THREE.TextureLoader().load(moonTex)
    tex.colorSpace = THREE.SRGBColorSpace
    tex.anisotropy = 8
    const moon = new THREE.Mesh(
      new THREE.SphereGeometry(1, 96, 64),
      new THREE.MeshStandardMaterial({ map: tex, bumpMap: tex, bumpScale: 3.5, roughness: 1, metalness: 0 }),
    )
    const tilt = new THREE.Group()
    tilt.add(moon)
    scene.add(tilt)

    // Low, warm sun from the side: the terminator runs across the globe like the polar dawn.
    const sun = new THREE.DirectionalLight(0xfff1dc, 4.4)
    scene.add(sun)
    scene.add(new THREE.AmbientLight(0x6b7fa3, 0.3))

    // Stars.
    const starGeo = new THREE.BufferGeometry()
    const pts = new Float32Array(1500 * 3)
    for (let i = 0; i < pts.length; i += 3) {
      const v = new THREE.Vector3().randomDirection().multiplyScalar(30 + Math.random() * 20)
      pts.set([v.x, v.y, v.z], i)
    }
    starGeo.setAttribute('position', new THREE.BufferAttribute(pts, 3))
    scene.add(new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0xffffff, size: 0.06, transparent: true, opacity: 0.8 })))

    const resize = () => {
      const w = el.clientWidth, h = el.clientHeight
      renderer.setSize(w, h)
      camera.aspect = w / h
      camera.updateProjectionMatrix()
    }
    resize()
    window.addEventListener('resize', resize)

    // Drag to rotate.
    let down: { x: number; y: number } | null = null
    const onDown = (e: PointerEvent) => { down = { x: e.clientX, y: e.clientY } }
    const onMove = (e: PointerEvent) => {
      if (!down) return
      state.current.dragX += (e.clientX - down.x) * 0.006
      state.current.dragY += (e.clientY - down.y) * 0.004
      down = { x: e.clientX, y: e.clientY }
    }
    const onUp = () => { down = null }
    el.addEventListener('pointerdown', onDown)
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)

    const still = reducedMotion()
    let t = 0, eased = 0
    const frame = () => {
      t += still ? 0 : 0.0016
      eased += (state.current.progress - eased) * 0.08
      const p = eased
      moon.rotation.y = t + state.current.dragX
      // 0: equator-on view; 1: south pole facing the camera.
      tilt.rotation.x = -p * Math.PI * 0.46 + state.current.dragY
      const dist = 4.4 - p * 1.7
      camera.position.set(0.35 * (1 - p), 0, dist)
      camera.lookAt(0, -0.15 * p, 0)
      const a = 0.35 + Math.sin(t * 0.6) * 0.25   // light from the side: a terminator crosses the globe
      sun.position.set(Math.cos(a) * 5, -1.2 * p, Math.sin(a) * 5 - 1)
      renderer.render(scene, camera)
    }
    const stop = visibleLoop(el, frame)
    return () => {
      stop()
      window.removeEventListener('resize', resize)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      el.removeEventListener('pointerdown', onDown)
      renderer.dispose()
      el.removeChild(renderer.domElement)
    }
  }, [])

  return <div ref={mount} className="scene" aria-label="3D Moon, drag to turn" />
}
