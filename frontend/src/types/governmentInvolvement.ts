export type DecisionId =
  | 'direct_participation'
  | 'historical_participation'
  | 'recent_participation'
  | 'currently_reported_execution'
export type EvidenceNode = {
  id: string
  kind: 'decision' | 'rule' | 'fact' | 'source' | 'unresolved'
  label: string
  children: EvidenceNode[]
}
export type InvolvementDecision = {
  id: DecisionId
  outcome: string
  evidence_status: string
  supporting_contract_ids: string[]
  supporting_evidence_ids: string[]
  evidence_tree_id: string | null
  evidence_tree: EvidenceNode | null
  warnings: string[]
}
export type Involvement = {
  company_id: string | null
  screening_run_id: string | null
  status: 'disabled' | 'blocked' | 'demo' | 'completed' | 'failed'
  engine: {
    provider: string
    product: string
    model_id: string | null
    model_version: string | number | null
    execution_mode: string
  }
  evaluation: {
    evaluated_at: string
    as_of_date: string
    lookback_months: number
    lookback_start_date: string
    policy_version: string
  }
  decisions: InvolvementDecision[]
  source: { snapshot_completed_at?: string | null; is_stale?: boolean }
  diagnostics: string[]
}
