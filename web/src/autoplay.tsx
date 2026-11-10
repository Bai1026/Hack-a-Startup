import { useEffect, useRef, useState, type ReactNode } from 'react'

// Replays data/demo/demo_script.json so every take of the recording is identical.
// ?autoplay=30|45|60   &captions=0 hides the presenter lines   &cursor=0 hides the pointer

export interface DemoApi {
  openCase: (id: string) => void
  showDenial: () => void
  runAnalysis: () => void
  selectEvidence: (id: string) => void
  selectRequirement: (reqId: string) => void
  selectNearMiss: (reqId: string, index: number) => void
  useBasis: () => void
  focusDraft: () => void
}

interface Step {
  t: number
  action: string
  target?: string
  index?: number
  case_id?: string
  say?: string
  cuts?: string[]
}

// Start times for the 30 second cut, from cut_notes in the script.
const CUT_30 = [0, 2, 4, 9, 12, 16, 19, 24, 30]
const LEAD = 0.75 // seconds the pointer starts moving before its click

function selectorFor(s: Step): string | null {
  switch (s.action) {
    case 'open_case': return s.t > 0 ? `[data-ap="case-${s.case_id}"]` : null
    case 'show_source': return '[data-ap="denial-quote"]'
    case 'run_analysis': return '[data-ap="analyze"]'
    case 'select_evidence': return `[data-ap="ev-${s.target}"]`
    case 'select_requirement': return `[data-ap="req-${s.target}"]`
    case 'select_near_miss': return `[data-ap="nm-${s.target}-${s.index}"]`
    case 'use_basis': return '[data-ap="use-basis"]'
    case 'focus_draft': return '[data-ap="draft-chip-active"]'
    default: return null
  }
}

function run(s: Step, api: DemoApi) {
  switch (s.action) {
    case 'open_case': return api.openCase(s.case_id!)
    case 'show_source': return api.showDenial()
    case 'run_analysis': return api.runAnalysis()
    case 'select_evidence': return api.selectEvidence(s.target!)
    case 'select_requirement': return api.selectRequirement(s.target!)
    case 'select_near_miss': return api.selectNearMiss(s.target!, s.index!)
    case 'use_basis': return api.useBasis()
    case 'focus_draft': return api.focusDraft()
  }
}

export function useAutoplay(cut: string | null, api: DemoApi, ready: boolean): ReactNode {
  const params = new URLSearchParams(location.search)
  const showCaptions = params.get('captions') !== '0'
  const showCursor = params.get('cursor') !== '0'
  const apiRef = useRef(api)
  apiRef.current = api
  const [state, setState] = useState<'waiting' | 'playing' | 'ended'>('waiting')
  const [caption, setCaption] = useState('')
  const [cursor, setCursor] = useState({ x: window.innerWidth / 2, y: window.innerHeight / 2 })
  const [ripples, setRipples] = useState<{ id: number; x: number; y: number }[]>([])
  const [steps, setSteps] = useState<Step[] | null>(null)

  useEffect(() => {
    if (!cut) return
    fetch(`${import.meta.env.BASE_URL}demo/demo_script.json`)
      .then((r) => r.json())
      .then((script) => {
        let list: Step[] = script.steps.filter((s: Step) => !s.cuts || s.cuts.includes(cut))
        if (cut === '30') list = list.map((s, i) => ({ ...s, t: CUT_30[i] ?? s.t }))
        setSteps(list)
      })
  }, [cut])

  useEffect(() => {
    if (!cut || !ready || !steps || state !== 'waiting') return
    const onKey = (e: KeyboardEvent) => {
      if (e.code !== 'Space') return
      e.preventDefault()
      setState('playing')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [cut, ready, steps, state])

  useEffect(() => {
    if (state !== 'playing' || !steps) return
    const timers: number[] = []
    const at = (sec: number, fn: () => void) => timers.push(window.setTimeout(fn, Math.max(0, sec * 1000)))
    const centre = (sel: string) => {
      const el = document.querySelector(sel)
      if (!el) return null
      const r = el.getBoundingClientRect()
      // Click near the left of wide targets, the way a person would.
      return { x: r.left + Math.min(r.width / 2, 60), y: r.top + Math.min(r.height / 2, 16) }
    }
    for (const s of steps) {
      const sel = selectorFor(s)
      if (sel) {
        at(s.t - LEAD, () => {
          document.querySelector(sel)?.scrollIntoView({ block: 'nearest' })
          const p = centre(sel)
          if (p) setCursor(p)
        })
      }
      at(s.t, () => {
        if (s.say) setCaption(s.say)
        if (s.action === 'end') return setState('ended')
        const p = sel && centre(sel)
        if (p) {
          const id = Math.random()
          setRipples((r) => [...r, { id, ...p }])
          window.setTimeout(() => setRipples((r) => r.filter((x) => x.id !== id)), 600)
        }
        run(s, apiRef.current)
      })
    }
    return () => timers.forEach(clearTimeout)
  }, [state, steps])

  if (!cut) return null
  return (
    <>
      {state === 'waiting' && (
        <div className="fixed bottom-14 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-full bg-slate-900/90 text-white text-sm shadow-lg">
          {ready && steps ? (
            <>Autoplay {cut}s ready. Start recording, then press <kbd className="px-1.5 py-0.5 rounded bg-white/20 font-mono">Space</kbd></>
          ) : (
            'Loading…'
          )}
        </div>
      )}
      {state === 'playing' && showCaptions && caption && (
        <div key={caption} className="slide-in fixed bottom-12 inset-x-0 z-40 flex justify-center pointer-events-none">
          <p className="max-w-[1100px] mx-6 px-6 py-3 rounded-xl bg-slate-900/92 text-white text-[22px] leading-snug text-center shadow-2xl">
            {caption}
          </p>
        </div>
      )}
      {state === 'playing' && showCursor && (
        <svg
          width="26" height="26" viewBox="0 0 24 24"
          className="fixed z-[70] pointer-events-none drop-shadow-md"
          style={{ left: cursor.x, top: cursor.y, transition: 'left 0.55s cubic-bezier(.3,.1,.2,1), top 0.55s cubic-bezier(.3,.1,.2,1)' }}
        >
          <path d="M4 2l16 9-7 2-3 7z" fill="#0f172a" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round" />
        </svg>
      )}
      {ripples.map((r) => (
        <span key={r.id} className="ripple" style={{ left: r.x, top: r.y }} />
      ))}
      {state === 'ended' && (
        <div className="slide-in fixed inset-0 z-[80] bg-slate-900/95 flex flex-col items-center justify-center text-white">
          <div className="flex items-center gap-4">
            <span className="w-16 h-16 rounded-2xl bg-indigo-500 flex items-center justify-center font-black text-4xl">A</span>
            <span className="text-6xl font-bold tracking-tight">Appealio</span>
          </div>
          <p className="mt-8 text-3xl text-slate-200">Every claim links back to the record.</p>
          <p className="mt-3 text-xl text-slate-400">Missing evidence is shown as missing. Staff review and submit.</p>
        </div>
      )}
    </>
  )
}
