import type { ReactNode } from 'react'
import type { Analysis, Basis, Evidence, Requirement, Sel, Span, Status } from './types'

export function spanLabel(s: Span) {
  const lines = s.line_start === s.line_end ? `L${s.line_start}` : `L${s.line_start}-${s.line_end}`
  return `p${s.page} ${lines}`
}

const STATUS: Record<Status, { icon: string; cls: string; gapTitle: string; gapCls: string }> = {
  supported: { icon: '✓', cls: 'bg-emerald-600 text-white', gapTitle: '', gapCls: '' },
  partial: {
    icon: '◐', cls: 'bg-amber-500 text-white',
    gapTitle: 'EVIDENCE INCOMPLETE', gapCls: 'border-amber-300 bg-amber-50 text-amber-800',
  },
  missing: {
    icon: '✕', cls: 'bg-red-600 text-white',
    gapTitle: 'EVIDENCE MISSING', gapCls: 'border-red-300 bg-red-50 text-red-800',
  },
  contradicted: {
    icon: '✕', cls: 'bg-red-600 text-white',
    gapTitle: 'RECORD INDICATES OTHERWISE', gapCls: 'border-red-300 bg-red-50 text-red-800',
  },
}

const COMPARATOR: Record<string, string> = { '>=': 'at least', '<=': 'at most', '>': 'more than', '<': 'less than', '==': 'exactly' }

function fmt(n: number | null, unit: string) {
  if (n === null) return 'nothing'
  return unit === 'USD' ? `$${n.toLocaleString('en-US')}` : `${n} ${unit}`
}

// The quote with its key phrases in bold.
function markQuote(quote: string, phrases: string[]): ReactNode[] {
  const marks: [number, number][] = []
  for (const p of phrases) {
    const i = quote.indexOf(p)
    if (i >= 0) marks.push([i, i + p.length])
  }
  marks.sort((a, b) => a[0] - b[0])
  const out: ReactNode[] = []
  let at = 0
  for (const [a, b] of marks) {
    if (a < at) continue
    out.push(quote.slice(at, a))
    out.push(<b key={a} className="font-semibold text-slate-900 bg-amber-100 rounded px-0.5">{quote.slice(a, b)}</b>)
    at = b
  }
  out.push(quote.slice(at))
  return out
}

function EvidenceDetail({ req, ev }: { req: Requirement; ev: Evidence }) {
  const all = req.evidence.flatMap((e) => e.key_phrases)
  const q = req.quantity_check
  return (
    <div className="mt-2 space-y-2 text-[13px] leading-snug">
      <p className="text-slate-700 border-l-2 border-amber-400 pl-2.5">
        “{markQuote(ev.quote, ev.key_phrases.map((k) => k.text))}”
      </p>
      <div className="flex flex-wrap gap-1.5">
        {req.facets.map((f) => {
          const kp = ev.key_phrases.find((k) => k.facet === f) ?? all.find((k) => k.facet === f)
          return (
            <span
              key={f}
              className={`px-2 py-0.5 rounded-full text-[11px] ${
                kp ? 'bg-slate-100 text-slate-700' : 'border border-dashed border-slate-400 text-slate-400'
              }`}
            >
              <span className="text-slate-500">{f.replace(/_/g, ' ')}:</span> {kp ? kp.text : 'not found'}
            </span>
          )
        })}
      </div>
      {q && (
        <p className={`text-xs font-medium ${q.passed ? 'text-emerald-700' : 'text-amber-700'}`}>
          {q.passed ? '✓' : '✕'} {q.label[0].toUpperCase() + q.label.slice(1)}: found {fmt(q.found, q.unit)}, required{' '}
          {COMPARATOR[q.comparator] ?? q.comparator} {fmt(q.required, q.unit)}
        </p>
      )}
      <p className="text-xs text-slate-500">{ev.rationale}</p>
    </div>
  )
}

function GapCard({ req, sel, onSelect }: { req: Requirement; sel: Sel | null; onSelect: (s: Sel) => void }) {
  const st = STATUS[req.status]
  const contra = req.status === 'contradicted'
  return (
    <div className={`mt-2.5 rounded-lg border ${st.gapCls} p-3 text-[13px] leading-snug slide-in`}>
      <div className="flex justify-between text-[11px] font-bold tracking-wider">
        <span>{st.gapTitle}</span>
        <span>{req.clause}</span>
      </div>
      {req.gap && (
        <>
          <p className="mt-1.5 font-semibold text-slate-900">{req.gap.summary}</p>
          <p className="mt-1 text-slate-600">
            <span className="font-medium text-slate-700">Would satisfy:</span> {req.gap.what_would_satisfy}
          </p>
        </>
      )}
      {req.quantity_check && !req.quantity_check.passed && req.evidence.length === 0 && (
        <p className="mt-1.5 text-xs font-semibold text-amber-800">
          ✕ {req.quantity_check.label}: found {fmt(req.quantity_check.found, req.quantity_check.unit)}, required{' '}
          {COMPARATOR[req.quantity_check.comparator]} {fmt(req.quantity_check.required, req.quantity_check.unit)}
        </p>
      )}
      {req.near_misses.length > 0 && (
        <div className="mt-2.5">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
            {contra ? 'What the record says' : 'Closest passages (none sufficient)'}
          </div>
          {req.near_misses.map((nm, i) => {
            const on = sel?.kind === 'near' && sel.reqId === req.req_id && sel.index === i
            return (
              <button
                key={i}
                data-ap={`nm-${req.req_id}-${i}`}
                onClick={(e) => {
                  e.stopPropagation()
                  onSelect({ kind: 'near', reqId: req.req_id, index: i })
                }}
                className={`mt-1.5 w-full text-left rounded-md border bg-white/80 px-2.5 py-1.5 transition ${
                  on ? 'border-slate-700 ring-2 ring-slate-300' : 'border-slate-200 hover:border-slate-400'
                }`}
              >
                <div className="flex gap-2">
                  <span className="shrink-0 font-mono text-[11px] text-slate-500 border border-dashed border-slate-400 rounded px-1 h-fit">
                    {spanLabel(nm.source)}
                  </span>
                  <span className="text-slate-700 line-clamp-2">“{nm.quote}”</span>
                </div>
                <div className="mt-1 text-xs text-slate-500">{nm.why_not}</div>
              </button>
            )
          })}
        </div>
      )}
      {req.gap && (
        <p className="mt-2.5 text-slate-700">
          <span className="font-semibold">Next step:</span> {req.gap.suggested_action}
        </p>
      )}
    </div>
  )
}

export function Requirements({
  analysis, phase, resolved, sel, openReq, usedBasis, onSelect, onOpen, onAnalyze,
}: {
  analysis: Analysis
  phase: 'idle' | 'running' | 'done'
  resolved: number
  sel: Sel | null
  openReq: string | null
  usedBasis: boolean
  onSelect: (s: Sel) => void
  onOpen: (reqId: string) => void
  onAnalyze: () => void
}) {
  if (phase === 'idle') {
    return (
      <section className="flex flex-col bg-white min-h-0">
        <div className="px-4 h-11 flex items-center border-b border-slate-200 text-[11px] font-semibold tracking-widest text-slate-500">
          REQUIREMENTS
        </div>
        <div className="flex-1 flex flex-col items-center justify-center gap-5 px-8 text-center">
          <p className="text-sm text-slate-500 leading-relaxed">
            Denial letter, payer policy and clinical record are loaded.
            <br />
            Break the denial into policy requirements and check each one against the record.
          </p>
          <button
            data-ap="analyze"
            onClick={onAnalyze}
            className="px-6 py-2.5 rounded-lg bg-indigo-600 text-white font-semibold shadow hover:bg-indigo-700"
          >
            Analyze
          </button>
        </div>
      </section>
    )
  }

  let n = 0
  return (
    <section className="flex flex-col bg-white min-h-0">
      <div className="px-4 h-11 flex items-center border-b border-slate-200 text-[11px] font-semibold tracking-widest text-slate-500">
        REQUIREMENTS
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {analysis.bases.map((b: Basis) => {
          const done = phase === 'done'
          const chosen = done && (b.kind === 'alternative' ? usedBasis && analysis.recommendation.basis_id === b.basis_id
            : analysis.recommendation.type === 'appeal_on_stated_basis')
          return (
            <div
              key={b.basis_id}
              data-basis={b.basis_id}
              className={`rounded-xl border transition-all duration-500 ${
                chosen ? 'border-indigo-500 ring-2 ring-indigo-200' : 'border-slate-200'
              }`}
            >
              <div className="flex items-center gap-2 px-3 py-2 bg-slate-50 rounded-t-xl border-b border-slate-200">
                <button
                  onClick={() => onSelect({ kind: 'basis', basisId: b.basis_id })}
                  className="text-left text-[13px] font-semibold text-slate-800 hover:text-indigo-700"
                >
                  {b.kind === 'stated' ? 'Stated basis' : 'Alternative basis'} {b.clause}
                  <span className="font-normal text-slate-500"> · {b.title}</span>
                </button>
                <span className="flex-1" />
                {chosen && (
                  <span className="pop-in text-[10px] font-bold tracking-wide text-indigo-700 bg-indigo-100 rounded-full px-2 py-0.5">
                    APPEAL BASIS
                  </span>
                )}
                {done && (
                  <span
                    className={`pop-in text-xs font-bold rounded-full px-2 py-0.5 ${
                      b.supportable ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'
                    }`}
                  >
                    {b.counts.supported}/{b.counts.total}
                  </span>
                )}
              </div>
              <div className="divide-y divide-slate-100">
                {b.requirements.map((r) => {
                  const isResolved = n++ < resolved
                  const open = openReq === r.req_id && isResolved
                  const st = STATUS[r.status]
                  const activeEv =
                    r.evidence.find((e) => sel?.kind === 'evidence' && sel.id === e.evidence_id) ?? r.evidence[0]
                  return (
                    <div
                      key={r.req_id}
                      data-ap={`req-${r.req_id}`}
                      onClick={() => isResolved && onOpen(r.req_id)}
                      className={`px-3 py-2.5 cursor-pointer transition-colors ${open ? 'bg-indigo-50/40' : 'hover:bg-slate-50'}`}
                    >
                      <div className="flex gap-2.5">
                        <span className="mt-0.5 w-5 h-5 shrink-0 flex items-center justify-center">
                          {isResolved ? (
                            <span className={`pop-in w-5 h-5 rounded-full text-[11px] font-bold flex items-center justify-center ${st.cls}`}>
                              {st.icon}
                            </span>
                          ) : (
                            <span className="spinner" />
                          )}
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="text-[13px] leading-snug">
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                onSelect({ kind: 'policy', reqId: r.req_id })
                              }}
                              className="font-mono text-xs font-semibold text-indigo-700 hover:underline mr-1.5"
                            >
                              {r.clause}
                            </button>
                            <span className="text-slate-800">{r.text}</span>
                          </div>
                          {isResolved && r.status !== 'supported' && !open && (
                            <div className={`pop-in mt-1 text-[11px] font-bold tracking-wide ${r.status === 'partial' ? 'text-amber-700' : 'text-red-700'}`}>
                              {st.gapTitle}
                              {r.near_misses.length > 0 && (
                                <span className="font-normal text-slate-500 normal-case tracking-normal">
                                  {' '}· {r.near_misses.length} closest passages
                                </span>
                              )}
                            </div>
                          )}
                          {isResolved && r.evidence.length > 0 && (
                            <div className="pop-in mt-1.5 flex flex-wrap gap-1.5">
                              {r.evidence.map((e) => {
                                const on = sel?.kind === 'evidence' && sel.id === e.evidence_id
                                return (
                                  <button
                                    key={e.evidence_id}
                                    data-ap={`ev-${e.evidence_id}`}
                                    onClick={(ev) => {
                                      ev.stopPropagation()
                                      onSelect({ kind: 'evidence', id: e.evidence_id })
                                    }}
                                    className={`font-mono text-[11px] rounded px-1.5 py-0.5 border transition ${
                                      on
                                        ? 'bg-amber-400 border-amber-500 text-slate-900 font-bold'
                                        : 'bg-amber-50 border-amber-300 text-amber-900 hover:bg-amber-100'
                                    }`}
                                  >
                                    {spanLabel(e.source)}
                                  </button>
                                )
                              })}
                            </div>
                          )}
                          {open && r.evidence.length > 0 && activeEv && <EvidenceDetail req={r} ev={activeEv} />}
                          {open && r.status !== 'supported' && <GapCard req={r} sel={sel} onSelect={onSelect} />}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}

export function Draft({
  analysis, ready, pending, sel, pulse, onSelect,
}: {
  analysis: Analysis
  ready: boolean
  pending: boolean // an alternative basis is recommended but not chosen yet
  sel: Sel | null
  pulse: number
  onSelect: (s: Sel) => void
}) {
  const { draft, bases } = analysis
  const basis = bases.find((b) => b.basis_id === draft.basis_id)
  const blocked = draft.status === 'blocked_on_gaps'
  const order: string[] = []
  for (const b of draft.blocks) for (const c of b.citations) if (!order.includes(c)) order.push(c)
  const stated = bases[0]
  const gaps = stated.requirements.filter((r) => r.status !== 'supported')

  const exportTxt = () => {
    const text = draft.blocks.map((b) => b.text).join('\n\n')
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain' }))
    a.download = `appeal-${analysis.case_id}-draft.txt`
    a.click()
  }

  const show = ready && !pending
  return (
    <section data-ap="draft" className="relative flex flex-col bg-white min-h-0">
      {pulse > 0 && <div key={pulse} className="pointer-events-none absolute inset-0 z-10 panel-pulse" />}
      <div className="px-4 h-11 flex items-center gap-2 border-b border-slate-200">
        <span className="text-[11px] font-semibold tracking-widest text-slate-500">APPEAL DRAFT</span>
        {show && basis && (
          <span className="pop-in text-[11px] font-mono font-semibold text-indigo-700 bg-indigo-50 rounded px-1.5 py-0.5">
            basis: {basis.clause}
          </span>
        )}
        <span className="flex-1" />
        <button
          disabled={!show || blocked}
          onClick={exportTxt}
          className="text-xs font-medium px-2.5 py-1 rounded-md border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Export
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-5">
        {!ready && <p className="text-sm text-slate-400 text-center mt-24">The draft appears after analysis.</p>}
        {ready && pending && (
          <div className="slide-in rounded-lg border-2 border-dashed border-amber-400 bg-amber-50 p-4 text-sm text-amber-900">
            <div className="text-[11px] font-bold tracking-wider">NOT READY ON {stated.clause}</div>
            {gaps.map((r) => (
              <p key={r.req_id} className="mt-1.5">
                {r.clause}: {r.gap?.summary}
              </p>
            ))}
            <p className="mt-2 text-amber-800/80">
              No letter is drafted on a basis the record does not support. Choose the recommended basis to draft.
            </p>
          </div>
        )}
        {show && (
          <div key={draft.basis_id} className="slide-in">
            {blocked && (
              <div className="mb-3 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm font-semibold text-red-800">
                Not ready to send
              </div>
            )}
            <div className="space-y-3 font-serif text-[15px] leading-relaxed text-slate-800">
              {draft.blocks.map((b, i) => {
                const chips = b.citations.map((c) => {
                  const on = sel?.kind === 'evidence' && sel.id === c
                  return (
                    <button
                      key={c}
                      data-ap={on ? 'draft-chip-active' : undefined}
                      title={c}
                      onClick={() => onSelect({ kind: 'evidence', id: c })}
                      className={`ml-1 align-baseline font-sans font-mono text-[11px] rounded px-1.5 border transition ${
                        on
                          ? 'bg-amber-400 border-amber-500 text-slate-900 font-bold scale-110'
                          : 'bg-amber-50 border-amber-300 text-amber-900 hover:bg-amber-100'
                      }`}
                    >
                      {order.indexOf(c) + 1}
                    </button>
                  )
                })
                if (b.type === 'gap')
                  return (
                    <p key={i} className="rounded-md border-2 border-dashed border-amber-400 bg-amber-50 px-3 py-2 font-sans text-sm text-amber-900">
                      {b.text}
                      {chips}
                    </p>
                  )
                return (
                  <p key={i}>
                    {b.text}
                    {chips}
                  </p>
                )
              })}
            </div>
          </div>
        )}
      </div>
      <div className="px-4 py-2 border-t border-slate-200 bg-slate-50 text-xs text-slate-600">
        <span className="font-semibold">Review required:</span> verify each passage before submission.
      </div>
    </section>
  )
}
