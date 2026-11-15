import { useRef, useState } from 'react'
import { Panel } from '../components/ui'
import { useStore } from '../store'
import type { CopilotReply } from '../types'

const SUGGESTIONS = [
  'Which site is best in June?',
  'Does the rover survive at Slater Plain?',
  'What does a 3-day slip cost at Malapert with a $40 million budget?',
  'Best landing for a 5-day mission at Mons Mouton in June?',
  'How dark does Haworth get in August?',
]

type Msg = { who: 'user'; text: string } | { who: 'bot'; reply: CopilotReply } | { who: 'err'; text: string }

export default function Copilot() {
  const { site } = useStore()
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const end = useRef<HTMLDivElement>(null)

  async function ask(question: string) {
    if (!question.trim() || busy) return
    setMsgs(m => [...m, { who: 'user', text: question }])
    setQ(''); setBusy(true)
    try {
      const res = await fetch('/api/copilot', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, site }) })
      const body = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(body.error || `The copilot answered with status ${res.status}.`)
      setMsgs(m => [...m, { who: 'bot', reply: body as CopilotReply }])
    } catch (e) {
      setMsgs(m => [...m, { who: 'err', text: `${e instanceof Error ? e.message : e} Try again in a moment, or pick a suggested question.` }])
    } finally {
      setBusy(false)
      setTimeout(() => end.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h2>Mission copilot</h2>
          <p>Ask in plain English. Answers come only from Sunchaser's computed data: every number is checked against the data before it's shown, and
            the facts it used are listed under each answer.</p>
        </div>
      </div>
      <Panel title="Try a question">
        <div className="suggest">{SUGGESTIONS.map(s => <button key={s} onClick={() => ask(s)} disabled={busy}>{s}</button>)}</div>
      </Panel>
      <div className="chat" aria-live="polite">
        {msgs.length === 0 && <div className="status">No questions yet. Pick one above, or type your own below.</div>}
        {msgs.map((m, i) => m.who === 'user'
          ? <div key={i} className="msg user">{m.text}</div>
          : m.who === 'err'
            ? <div key={i} className="msg bot" style={{ borderColor: 'var(--danger)' }}>{m.text}</div>
            : <div key={i} className="msg bot">
                {m.reply.answer}
                {m.reply.facts_used.length > 0 && <div className="facts">{m.reply.facts_used.map((f, j) => <span key={j} className="fact">{f.label}<b>{f.value}</b></span>)}</div>}
              </div>)}
        {busy && <div className="msg bot"><span className="spinner" /> Checking the data…</div>}
        <div ref={end} />
      </div>
      <form className="ask" onSubmit={e => { e.preventDefault(); ask(q) }}>
        <input className="input" value={q} onChange={e => setQ(e.target.value)} maxLength={500} placeholder="e.g. When should we land at Haworth in October?" aria-label="Your question" />
        <button className="btn primary" disabled={busy || !q.trim()}>Ask</button>
      </form>
    </>
  )
}
