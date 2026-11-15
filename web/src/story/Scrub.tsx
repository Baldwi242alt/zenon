import { useEffect, useRef } from 'react'

// Scroll-scrubbed image sequence: frame = progress x (frames - 1), drawn to a canvas.
// Frames are decoded once up front, so scrubbing backwards and forwards is instant.
// (The same technique as an Apple product page, and the Neptune storm sequence in our old project.)
export function Scrub({ frames, progress, alt }: { frames: string[]; progress: number; alt: string }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const images = useRef<HTMLImageElement[]>([])
  const shown = useRef(-1)

  // Start downloading frames only when the sequence is about a screen away.
  useEffect(() => {
    const c = canvas.current
    if (!c) return
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { load(); io.disconnect() } }, { rootMargin: '150% 0px' })
    io.observe(c)
    return () => io.disconnect()
  }, [frames])

  const load = () => {
    images.current = frames.map((src, i) => {
      const img = new Image()
      img.decoding = 'async'
      img.src = src
      // Draw the first frame as soon as it arrives.
      if (i === 0) img.onload = () => draw(0, true)
      return img
    })
  }

  const draw = (i: number, force = false) => {
    const c = canvas.current, img = images.current[i]
    if (!c || !img || !img.complete || !img.naturalWidth || (i === shown.current && !force)) return
    if (c.width !== img.naturalWidth) { c.width = img.naturalWidth; c.height = img.naturalHeight }
    c.getContext('2d')!.drawImage(img, 0, 0)
    shown.current = i
  }

  useEffect(() => {
    let i = Math.round(Math.min(1, Math.max(0, progress)) * (frames.length - 1))
    // If that frame is still loading, show the nearest earlier one that has loaded.
    while (i > 0 && !images.current[i]?.complete) i--
    draw(i)
  })

  return <canvas ref={canvas} className="scrub" role="img" aria-label={alt} />
}
