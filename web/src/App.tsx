import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import SourceViewer from './SourceViewer'
import { Draft, Requirements, spanLabel } from './Panels'
import { useAutoplay, type DemoApi } from './autoplay'
import type { Analysis, CaseData, Highlight, Requirement, Sel } from './types'

const params = new URLSearchParams(location.search)
const SOURCE = params.get('source') // "gold" loads the answer key
const AUTOPLAY = params.get('autoplay') // 30 | 45 | 60
const RESOLVE_MS = 300
const BASE = import.meta.env.BASE_URL

async function fetchJson(url: string) {
  const r = await fetch(url)
  // The dev server answers unknown paths with index.html, so check the type too.
  if (!r.ok || !r.headers.get('content-type')?.includes('json')) return null
  return r.json()
}

async function loadCases(): Promise<CaseData[]> {
  const index = await fetchJson(`${BASE}cases/index.json`)
  return Promise.all(
    index.cases.map(async (c: { case_id: string; title: string }) => {
      const dir = `${BASE}cases/${c.case_id}`
      const analysis: Analysis =
        (SOURCE !== 'gold' && (await fetchJson(`${dir}/analysis.json`))) || (await fetchJson(`${dir}/analysis.gold.json`))
      const record = analysis.documents.find((d) => d.doc_id === 'CR')!
      const lines = await fetchJson(`${dir}/${record.lines_file}`)
      const recordLines = lines.pages.reduce((n: number, p: { lines: unknown[] }) => n + p.lines.length, 0)
      return { id: c.case_id, title: c.title, analysis, recordLines, recordPages: record.pages }
    }),
  )
}

function findReq(a: Analysis, reqId: string): Requirement | undefined {
  for (const b of a.bases) for (const r of b.requirements) if (r.req_id === reqId) return r
}

function findEvidence(a: Analysis, id: string) {
  for (const b of a.bases)
    for (const r of b.requirements) for (const e of r.evidence) if (e.evidence_id === id) return { req: r, ev: e }
}

const BANNER = {
  appeal_on_stated_basis: { cls: 'bg-emerald-50 border-emerald-300 text-emerald-900', icon: '✓', iconCls: 'bg-emerald-600' },
  appeal_on_alternative_basis: { cls: 'bg-amber-50 border-amber-300 text-amber-950', icon: '!', iconCls: 'bg-amber-500' },
  obtain_documentation: { cls: 'bg-red-50 border-red-300 text-red-900', icon: '✕', iconCls: 'bg-red-600' },
}

export default function App() {
  const [cases, setCases] = useState<CaseData[] | null>(null)
  const [caseId, setCaseId] = useState('B-3117')
  const [phase, setPhase] = useState<'idle' | 'running' | 'done'>('idle')
  const [resolved, setResolved] = useState(0)
  const [sel, setSel] = useState<{ s: Sel; tick: number } | null>(null)
  const [openReq, setOpenReq] = useState<string | null>(null)
  const [activeDoc, setActiveDoc] = useState('DL')
  const [usedBasis, setUsedBasis] = useState(false)
  const [draftPulse, setDraftPulse] = useState(0)
  const timers = useRef<number[]>([])

  useEffect(() => {
    loadCases().then(setCases)
  }, [])

  const current = cases?.find((c) => c.id === caseId)
  const a = current?.analysis

  const select = useCallback(
    (s: Sel, analysis = a) => {
      if (!analysis) return
      setSel((prev) => ({ s, tick: (prev?.tick ?? 0) + 1 }))
      if (s.kind === 'evidence') {
        const hit = findEvidence(analysis, s.id)
        if (hit) {
          setOpenReq(hit.req.req_id)
          setActiveDoc(hit.ev.source.doc_id)
        }
      } else if (s.kind === 'near') {
        const nm = findReq(analysis, s.reqId)?.near_misses[s.index]
        if (nm) setActiveDoc(nm.source.doc_id)
      } else if (s.kind === 'policy' || s.kind === 'basis') setActiveDoc('POL')
      else setActiveDoc('DL')
    },
    [a],
  )

  const openCase = useCallback(
    (id: string) => {
      timers.current.forEach(clearTimeout)
      const next = cases?.find((c) => c.id === id)?.analysis
      setCaseId(id)
      setPhase('idle')
      setResolved(0)
      setOpenReq(null)
      setUsedBasis(false)
      setDraftPulse(0)
      setSel(null)
      setActiveDoc('DL')
      if (next) select({ kind: 'denial' }, next)
    },
    [cases, select],
  )

  // Highlight the denial reason as soon as the first case is loaded.
  useEffect(() => {
    if (cases) openCase(caseId)
  }, [cases]) // eslint-disable-line react-hooks/exhaustive-deps

  const runAnalysis = useCallback(() => {
    if (!a) return
    const total = a.bases.reduce((n, b) => n + b.requirements.length, 0)
    setPhase('running')
    setResolved(0)
    for (let i = 1; i <= total; i++) timers.current.push(window.setTimeout(() => setResolved(i), 300 + i * RESOLVE_MS))
    timers.current.push(window.setTimeout(() => setPhase('done'), 300 + (total + 1) * RESOLVE_MS))
  }, [a])

  const openRequirement = useCallback(
    (reqId: string) => {
      if (!a) return
      const r = findReq(a, reqId)
      setOpenReq(reqId)
      if (r?.evidence[0]) select({ kind: 'evidence', id: r.evidence[0].evidence_id })
      requestAnimationFrame(() =>
        document.querySelector(`[data-ap="req-${reqId}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }),
      )
    },
    [a, select],
  )

  const useBasis = useCallback(() => {
    if (!a?.recommendation.basis_id) return
    setUsedBasis(true)
    document.querySelector(`[data-basis="${a.recommendation.basis_id}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [a])

  const api: DemoApi = useMemo(
    () => ({
      openCase,
      showDenial: () => select({ kind: 'denial' }),
      runAnalysis,
      selectEvidence: (id) => select({ kind: 'evidence', id }),
      selectRequirement: openRequirement,
      selectNearMiss: (reqId, index) => select({ kind: 'near', reqId, index }),
      useBasis,
      focusDraft: () => setDraftPulse((n) => n + 1),
    }),
    [openCase, select, runAnalysis, openRequirement, useBasis],
  )
  const overlay = useAutoplay(AUTOPLAY, api, !!cases)

  const highlight: Highlight | null = useMemo(() => {
    if (!a || !sel) return null
    const { s, tick } = sel
    if (s.kind === 'evidence') {
      const hit = findEvidence(a, s.id)
      return hit ? { span: hit.ev.source, keyRects: hit.ev.key_phrases.flatMap((k) => k.rects), tone: 'evidence', tick } : null
    }
    if (s.kind === 'near') {
      const nm = findReq(a, s.reqId)?.near_misses[s.index]
      return nm ? { span: nm.source, keyRects: [], tone: nm.relation === 'contradicts' ? 'contra' : 'near', tick } : null
    }
    const span =
      s.kind === 'policy' ? findReq(a, s.reqId)?.policy_source
      : s.kind === 'basis' ? a.bases.find((b) => b.basis_id === s.basisId)?.policy_source
      : s.kind === 'clause' ? a.denial.policy_ref.source
      : a.denial.source
    return span ? { span, keyRects: [], tone: 'blue', tick } : null
  }, [a, sel])

  if (!cases || !current || !a) return <div className="h-full flex items-center justify-center text-slate-400">Loading…</div>

  const done = phase === 'done'
  const rec = a.recommendation
  const banner = BANNER[rec.type]
  const reqs = a.bases.flatMap((b) => b.requirements)
  const cited = reqs.reduce((n, r) => n + r.evidence.length, 0)
  const near = reqs.reduce((n, r) => n + (r.status === 'supported' ? 0 : r.near_misses.length), 0)

  return (
    <div className="h-full flex flex-col">
      <header className="bg-slate-900 text-white px-5 pt-3 pb-3">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="w-7 h-7 rounded-lg bg-indigo-500 flex items-center justify-center font-black text-sm">A</span>
            <span className="text-lg font-bold tracking-tight">Appealio</span>
          </div>
          <span className="text-slate-600">|</span>
          <span className="text-sm">
            <span className="font-semibold">Case {current.id}</span>
            <span className="text-slate-400"> · {current.title.replace(/^Medical necessity appeal: /, '')}</span>
          </span>
          <span className="flex-1" />
          <span className="text-[11px] text-slate-400 mr-1">Synthetic demo data</span>
          {cases.map((c) => (
            <button
              key={c.id}
              data-ap={`case-${c.id}`}
              onClick={() => openCase(c.id)}
              className={`px-2.5 py-1 rounded-md text-xs font-mono font-semibold transition-colors ${
                c.id === caseId ? 'bg-white text-slate-900' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
              }`}
            >
              {c.id}
            </button>
          ))}
        </div>
        <div className="mt-2.5 flex items-center gap-3 text-sm">
          <span className="px-2 py-0.5 rounded bg-red-600 text-[11px] font-bold tracking-wider">DENIED</span>
          <button data-ap="denial-quote" onClick={() => select({ kind: 'denial' })} className="text-left text-slate-100 hover:underline truncate">
            “{a.denial.reason_text}”
          </button>
          <span className="shrink-0 text-xs text-slate-400 font-mono">Letter {spanLabel(a.denial.source)}</span>
          <button
            onClick={() => select({ kind: 'clause' })}
            className="shrink-0 px-2 py-0.5 rounded bg-slate-700 hover:bg-slate-600 text-xs font-mono font-semibold"
          >
            {a.denial.policy_ref.policy_id} {a.denial.policy_ref.clause}
          </button>
        </div>
      </header>

      {done && (
        <div className={`slide-in flex items-center gap-3 px-5 py-3 border-b ${banner.cls}`}>
          <span className={`w-6 h-6 shrink-0 rounded-full text-white text-sm font-bold flex items-center justify-center ${banner.iconCls}`}>
            {banner.icon}
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-[15px] font-semibold leading-snug">{rec.banner}</p>
            {rec.type === 'obtain_documentation' && (
              <ul className="mt-1 text-xs list-disc pl-4 opacity-90">
                {rec.human_actions.map((h) => (
                  <li key={h}>{h}</li>
                ))}
              </ul>
            )}
          </div>
          {rec.type === 'appeal_on_alternative_basis' && (
            <button
              data-ap="use-basis"
              onClick={useBasis}
              disabled={usedBasis}
              className="shrink-0 px-4 py-2 rounded-lg bg-slate-900 text-white text-sm font-semibold shadow hover:bg-slate-700 disabled:bg-emerald-600 disabled:opacity-100"
            >
              {usedBasis ? '✓ Basis selected' : 'Use this basis'}
            </button>
          )}
        </div>
      )}

      <main className="flex-1 min-h-0 grid grid-cols-[minmax(380px,26fr)_minmax(0,50fr)_minmax(360px,24fr)]">
        <Requirements
          analysis={a}
          phase={phase}
          resolved={resolved}
          sel={sel?.s ?? null}
          openReq={openReq}
          usedBasis={usedBasis}
          onSelect={select}
          onOpen={openRequirement}
          onAnalyze={runAnalysis}
        />
        <SourceViewer caseId={caseId} documents={a.documents} activeDoc={activeDoc} onTab={setActiveDoc} highlight={highlight} />
        <Draft
          analysis={a}
          ready={done}
          pending={rec.type === 'appeal_on_alternative_basis' && !usedBasis}
          sel={sel?.s ?? null}
          pulse={draftPulse}
          onSelect={select}
        />
      </main>

      <footer className="flex items-center gap-5 px-5 h-8 bg-white border-t border-slate-200 text-xs text-slate-500">
        {done ? (
          <>
            <span>Searched {current.recordLines} lines in {current.recordPages} pages</span>
            <span>{cited} passages cited</span>
            <span>{near} near misses</span>
          </>
        ) : (
          <span>{current.recordLines} record lines in {current.recordPages} pages loaded</span>
        )}
        <span className="flex-1" />
        <span>
          source: <span className="font-mono font-semibold text-slate-700">{a.generated_by}</span>
        </span>
      </footer>
      {overlay}
    </div>
  )
}
