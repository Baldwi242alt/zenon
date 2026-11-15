import { useEffect, useRef, useState, type RefObject } from 'react'

// Progress (0..1) of scrolling through a tall section: 0 when its top reaches the top of the
// viewport, 1 when its bottom reaches the bottom. Used to drive the sticky 3D scenes.
export function useSectionProgress(ref: RefObject<HTMLElement | null>): number {
  const [p, setP] = useState(0)
  useEffect(() => {
    let raf = 0
    const update = () => {
      raf = 0
      const el = ref.current
      if (!el) return
      const r = el.getBoundingClientRect()
      const total = r.height - window.innerHeight
      setP(total > 0 ? Math.min(1, Math.max(0, -r.top / total)) : 0)
    }
    const on = () => { if (!raf) raf = requestAnimationFrame(update) }
    update()
    window.addEventListener('scroll', on, { passive: true })
    window.addEventListener('resize', on)
    return () => { window.removeEventListener('scroll', on); window.removeEventListener('resize', on); cancelAnimationFrame(raf) }
  }, [ref])
  return p
}

// Adds the class "in" when an element scrolls into view (CSS does the animation).
export function useReveal<T extends HTMLElement>(): RefObject<T | null> {
  const ref = useRef<T | null>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { el.classList.add('in'); io.disconnect() } }, { threshold: 0.2 })
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return ref
}

export const reducedMotion = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

// Runs frame() every animation frame, but only while el is on screen and the tab is visible.
// Off-screen 3D scenes cost nothing, which keeps scrolling smooth.
export function visibleLoop(el: HTMLElement, frame: () => void): () => void {
  let raf = 0, onScreen = false
  const tick = () => { frame(); raf = requestAnimationFrame(tick) }
  const sync = () => {
    cancelAnimationFrame(raf)
    if (onScreen && !document.hidden) raf = requestAnimationFrame(tick)
  }
  const io = new IntersectionObserver(([e]) => { onScreen = e.isIntersecting; sync() }, { rootMargin: '100px' })
  io.observe(el)
  document.addEventListener('visibilitychange', sync)
  frame()
  return () => { io.disconnect(); document.removeEventListener('visibilitychange', sync); cancelAnimationFrame(raf) }
}
