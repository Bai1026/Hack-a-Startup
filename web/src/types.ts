export type Rect = [number, number, number, number]

export interface Span {
  doc_id: string
  page: number
  line_start: number
  line_end: number
  rects: Rect[]
}

export interface KeyPhrase { text: string; facet: string; rects: Rect[] }

export interface Evidence {
  evidence_id: string
  source: Span
  quote: string
  key_phrases: KeyPhrase[]
  rationale: string
}

export interface NearMiss { source: Span; quote: string; relation: string; why_not: string }

export interface QuantityCheck {
  label: string
  comparator: string
  required: number
  found: number | null
  unit: string
  passed: boolean
}

export interface Gap { summary: string; what_would_satisfy: string; suggested_action: string }

export type Status = 'supported' | 'partial' | 'missing' | 'contradicted'

export interface Requirement {
  req_id: string
  clause: string
  text: string
  policy_source: Span
  policy_text: string
  facets: string[]
  status: Status
  evidence: Evidence[]
  near_misses: NearMiss[]
  quantity_check?: QuantityCheck | null
  gap?: Gap | null
}

export interface Basis {
  basis_id: string
  kind: 'stated' | 'alternative'
  title: string
  clause: string
  policy_source: Span
  requirements: Requirement[]
  counts: { supported: number; total: number }
  supportable: boolean
}

export interface DocMeta { doc_id: string; file: string; title: string; pages: number; lines_file: string }

export interface DraftBlock { type: 'text' | 'claim' | 'gap'; text: string; citations: string[] }

export interface Analysis {
  case_id: string
  generated_by: string
  documents: DocMeta[]
  denial: {
    reason_text: string
    source: Span
    policy_ref: { policy_id: string; title: string; clause: string; source: Span }
  }
  bases: Basis[]
  recommendation: {
    type: 'appeal_on_stated_basis' | 'appeal_on_alternative_basis' | 'obtain_documentation'
    basis_id: string | null
    banner: string
    rationale: string
    human_actions: string[]
  }
  draft: { basis_id: string | null; status: 'ready_for_review' | 'blocked_on_gaps'; blocks: DraftBlock[] }
}

export interface CaseData {
  id: string
  title: string
  analysis: Analysis
  recordLines: number
  recordPages: number
}

// The one piece of shared state: what is selected. All three columns read it.
export type Sel =
  | { kind: 'evidence'; id: string }
  | { kind: 'near'; reqId: string; index: number }
  | { kind: 'policy'; reqId: string }
  | { kind: 'basis'; basisId: string }
  | { kind: 'denial' }
  | { kind: 'clause' }

export type Tone = 'evidence' | 'near' | 'contra' | 'blue'

export interface Highlight { span: Span; keyRects: Rect[]; tone: Tone; tick: number }
