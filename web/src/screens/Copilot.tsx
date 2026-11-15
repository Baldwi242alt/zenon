import { useEffect, useRef, useState } from 'react'
import { useStore } from '../store'
import type { CopilotReply } from '../types'

// Chat with the mission copilot (Google Gemini). It answers anything conversationally; questions about
// Sunchaser's sites, dates and routes are answered from the computed data, with every number checked
// and the facts used shown under the answer. The last few messages go along so follow-ups work.
const SUGGESTIONS = [
  'Which site is best in June?',
  'Why is the lunar south pole so interesting?',
  'Does the rover survive at Slater Plain?',
  'What does a 3-day slip cost at Malapert with a $40 million budget?',
  'How cold do permanently shadowed craters get?',
  'What is Artemis III?',
]

type Msg = { who: 'user'; text: string } | { who: 'bot'; reply: CopilotReply } | { who: 'err'; text: string }

const KIND: Record<string, string> = { data: 'From Sunchaser data', general: 'General knowledge · Gemini', offline: 'Gemini offline · data only' }

export default function Copilot() {
  const { site } = useStore()
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const scroller = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)

  useEffect(() => { scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' }) }, [msgs, busy])

  async function ask(question: string) {
    const text = question.trim()
    if (!text || busy) return
    const history = msgs.slice(-8).flatMap(m => m.who === 'user' ? [{ role: 'user', text: m.text }]
      : m.who === 'bot' ? [{ role: 'assistant', text: m.reply.answer }] : [])
    setMsgs(m => [...m, { who: 'user', text }])
    setQ(''); setBusy(true)
    try {
      const res = await fetch('/api/copilot', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: text, site, history }) })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(body.error || `The copilot answered with status ${res.status}.`)
      setMsgs(m => [...m, { who: 'bot', reply: body as CopilotReply }])
    } catch (e) {
      setMsgs(m => [...m, { who: 'err', text: `${e instanceof Error ? e.message : e} Try again in a moment.` }])
    } finally {
      setBusy(false)
      input.current?.focus()
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Ask Gemini</h2>
          <p>Chat about anything: the Moon, the south pole, NASA missions, or your landing plan. When you ask about Sunchaser's sites, dates or
            routes, Gemini answers from the computed data, every number is checked, and the facts it used are listed.</p>
        </div>
      </div>
      <section className="gchat">
        <header className="gchat-head">
          <span className="gmark" aria-hidden="true" />
          <div><b>Sunchaser copilot</b><small>Google Gemini · lunar south pole mission planner</small></div>
          {msgs.length > 0 && <button className="gchat-clear" onClick={() => setMsgs([])}>New chat</button>}
        </header>
        <div className="gchat-log" ref={scroller} aria-live="polite">
          {msgs.length === 0 && (
            <div className="gchat-empty">
              <span className="gmark big" aria-hidden="true" />
              <p className="gchat-hello">Hi, I'm your lunar mission copilot.</p>
              <p className="gchat-sub">Ask me where and when to land at the south pole, how a rover survives the shadows, or anything about the Moon.</p>
              <div className="gchat-chips">{SUGGESTIONS.map(s => <button key={s} onClick={() => ask(s)}>{s}</button>)}</div>
            </div>
          )}
          {msgs.map((m, i) => m.who === 'user'
            ? <div key={i} className="gmsg me"><p>{m.text}</p></div>
            : m.who === 'err'
              ? <div key={i} className="gmsg bot err"><span className="gmark" aria-hidden="true" /><div><p>{m.text}</p></div></div>
              : <div key={i} className="gmsg bot"><span className="gmark" aria-hidden="true" /><div>
                  <p>{m.reply.answer}</p>
                  {m.reply.kind && <span className={`gkind ${m.reply.kind}`}>{KIND[m.reply.kind] ?? m.reply.kind}</span>}
                  {m.reply.facts_used.length > 0 && <div className="gfacts">{m.reply.facts_used.map((f, j) => <span key={j}>{f.label}<b>{f.value}</b></span>)}</div>}
                </div></div>)}
          {busy && <div className="gmsg bot"><span className="gmark spin" aria-hidden="true" /><div className="gtyping" aria-label="Gemini is typing"><i /><i /><i /></div></div>}
        </div>
        <form className="gchat-input" onSubmit={e => { e.preventDefault(); ask(q) }}>
          <textarea ref={input} rows={1} value={q} maxLength={500} placeholder="Message the copilot…" aria-label="Your message"
            onChange={e => setQ(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(q) } }} />
          <button disabled={busy || !q.trim()} aria-label="Send">↑</button>
        </form>
        <p className="gchat-note">Gemini can make mistakes about general topics. Numbers about Sunchaser's sites are checked against the data.</p>
      </section>
    </>
  )
}
