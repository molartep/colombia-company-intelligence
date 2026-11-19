export interface ActivityGroup {
  label: string
  count: number
  values: Record<string, string>
}
export interface Contract {
  contract_id: string
  process_id: string | null
  reference: string | null
  original_supplier_identifier: string
  normalized_supplier_identifier: string
  supplier_document_type: string
  source_identifier: string
  match_method: string
  match_status: string
  buyer: string | null
  buyer_nit: string | null
  description: string | null
  value: string | null
  currency: string | null
  currency_basis?: string
  raw_status: string | null
  status: string
  contract_type: string | null
  modality: string | null
  signature_date: string | null
  start_date: string | null
  end_date: string | null
  department: string | null
  city: string | null
  source_url: string
  source_link_label: string
  retrieved_at: string
  source_updated_at: string | null
  evidence_id: string | null
}
export interface SecopScreening {
  company_id: string
  company_name: string
  nit: string | null
  source_id: string
  source_url: string
  publisher: string
  outcome:
    | 'completed_with_matches'
    | 'completed_no_matches'
    | 'source_unavailable'
    | 'failed'
    | 'stale'
    | 'not_screened'
    | 'missing_nit'
    | 'running'
  run_id: string | null
  run_status: string | null
  last_attempted_at: string | null
  last_successful_at: string | null
  source_updated_at: string | null
  cache_age_seconds: number | null
  cache_ttl_seconds: number
  warnings: string[]
  error_code: string | null
  summary: null | {
    total_contracts: number
    total_values: Record<string, string>
    monetary_contracts: number
    missing_or_invalid_values: number
    unknown_currency_contracts: number
    zero_value_contracts: number
    distinct_buyers: number
    latest_signature_date: string | null
    annual: ActivityGroup[]
    statuses: ActivityGroup[]
    top_buyers: ActivityGroup[]
    modalities: ActivityGroup[]
    departments: ActivityGroup[]
    executive_summary: string
  }
}
export interface ContractPage {
  items: Contract[]
  page: number
  page_size: number
  total: number
  has_more: boolean
  run_id: string | null
}
