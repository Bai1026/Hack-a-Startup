import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import * as pdfjs from 'pdfjs-dist'
import type { DocMeta, Highlight, Rect } from './types'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

const PAGE_W = 612
const PAGE_H = 792
const TAB_LABEL: Record<string, string> = { CR: 'Record', POL: 'Policy', DL: 'Letter' }
const TAB_ORDER = ['CR', 'POL', 'DL']

function PdfPage({ doc, pageNo, scale }: { doc: pdfjs.PDFDocumentProxy; pageNo: number; scale: number }) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    let task: pdfjs.RenderTask | null = null
    let cancelled = false
    doc.getPage(pageNo).then((page) => {
      const canvas = ref.current
      if (cancelled || !canvas) return
      const dpr = Math.max(window.devicePixelRatio || 1, 2)
      const viewport = page.getViewport({ scale: scale * dpr })
      canvas.width = viewport.width
      canvas.height = viewport.height
      task = page.render({ canvas, viewport })
      task.promise.catch(() => {})
    })
    return () => {
      cancelled = true
      task?.cancel()
    }
  }, [doc, pageNo, scale])
  return <canvas ref={ref} style={{ width: PAGE_W * scale, height: PAGE_H * scale }} className="block" />
}

function box(r: Rect, s: number, pad: number) {
  return {
    left: r[0] * s - pad,
    top: r[1] * s - pad,
    width: (r[2] - r[0]) * s + pad * 2,
    height: (r[3] - r[1]) * s + pad * 2,
  }
}

function PdfDoc({
  url, meta, scale, highlight, active,
}: { url: string; meta: DocMeta; scale: number; highlight: Highlight | null; active: boolean }) {
  const [doc, setDoc] = useState<pdfjs.PDFDocumentProxy | null>(null)
  const scroller = useRef<HTMLDivElement>(null)
  const [page, setPage] = useState(1)

  useEffect(() => {
    let cancelled = false
    const task = pdfjs.getDocument({ url })
    task.promise.then((d) => !cancelled && setDoc(d))
    return () => {
      cancelled = true
      task.destroy()
    }
  }, [url])

  const mine = highlight && highlight.span.doc_id === meta.doc_id ? highlight : null

  // Bring the first rect to about a third of the way down the viewport.
  useLayoutEffect(() => {
    const el = scroller.current
    if (!mine || !active || !el) return
    const pageEl = el.querySelector<HTMLElement>(`[data-page="${mine.span.page}"]`)
    if (!pageEl) return
    const top = pageEl.offsetTop + mine.span.rects[0][1] * scale - el.clientHeight / 3
    el.scrollTo({ top: Math.max(0, top), behavior: 'smooth' })
  }, [mine?.tick, active, scale]) // eslint-disable-line react-hooks/exhaustive-deps

  const onScroll = () => {
    const el = scroller.current
    if (!el) return
    const mid = el.scrollTop + el.clientHeight / 2
    setPage(Math.min(meta.pages, Math.max(1, Math.floor(mid / (PAGE_H * scale + 16)) + 1)))
  }

  return (
    <div className={active ? 'absolute inset-0 flex flex-col' : 'hidden'}>
      <div className="px-4 py-1 text-[11px] text-slate-500 bg-slate-100 border-b border-slate-200">
        {meta.title} · page {page} of {meta.pages}
      </div>
      <div ref={scroller} onScroll={onScroll} className="relative flex-1 overflow-y-auto bg-slate-200/70 py-4">
        {Array.from({ length: meta.pages }, (_, i) => i + 1).map((p) => (
          <div
            key={p}
            data-page={p}
            className="relative mx-auto mb-4 bg-white shadow-md"
            style={{ width: PAGE_W * scale, height: PAGE_H * scale }}
          >
            {doc && <PdfPage doc={doc} pageNo={p} scale={scale} />}
            {mine && mine.span.page === p && (
              <div key={mine.tick} className="absolute inset-0">
                {mine.span.rects.map((r, i) => (
                  <div key={`b${i}`} className={`hl hl-band-${mine.tone} hl-pulse`} style={box(r, scale, 3)} />
                ))}
                {mine.keyRects.map((r, i) => (
                  <div key={`k${i}`} className="hl hl-key-evidence hl-pulse" style={box(r, scale, 1.5)} />
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function SourceViewer({
  caseId, documents, activeDoc, onTab, highlight,
}: {
  caseId: string
  documents: DocMeta[]
  activeDoc: string
  onTab: (docId: string) => void
  highlight: Highlight | null
}) {
  const wrap = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1.4)

  useLayoutEffect(() => {
    const fit = () => {
      if (wrap.current) setScale(Math.min(1.6, Math.max(0.8, (wrap.current.clientWidth - 56) / PAGE_W)))
    }
    fit()
    window.addEventListener('resize', fit)
    return () => window.removeEventListener('resize', fit)
  }, [])

  const docs = TAB_ORDER.map((id) => documents.find((d) => d.doc_id === id)).filter(Boolean) as DocMeta[]

  return (
    <section ref={wrap} className="flex flex-col min-w-0 border-x border-slate-200 bg-white">
      <div className="flex items-center gap-1 px-4 h-11 border-b border-slate-200">
        <span className="text-[11px] font-semibold tracking-widest text-slate-500 mr-3">SOURCE</span>
        {docs.map((d) => (
          <button
            key={d.doc_id}
            onClick={() => onTab(d.doc_id)}
            className={`px-3 py-1 rounded-md text-sm font-medium transition-colors ${
              activeDoc === d.doc_id ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            {TAB_LABEL[d.doc_id] ?? d.title}
          </button>
        ))}
      </div>
      <div className="relative flex-1 min-h-0">
        {docs.map((d) => (
          <PdfDoc
            key={`${caseId}/${d.file}`}
            url={`${import.meta.env.BASE_URL}cases/${caseId}/${d.file}`}
            meta={d}
            scale={scale}
            highlight={highlight}
            active={activeDoc === d.doc_id}
          />
        ))}
      </div>
    </section>
  )
}
