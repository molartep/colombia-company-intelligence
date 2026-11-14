export interface Company {
  id: string
  nit: string | null
  verification_digit: string | null
  legal_name: string
  legal_form: string | null
  registration_status: string | null
  primary_ciiu: string | null
  department: string | null
  municipality: string | null
}
export interface SearchItem extends Company {
  registration_number: string | null
  chamber: string | null
  chamber_code: string | null
  registration_date: string | null
  renewal_date: string | null
  match_type: 'exact_nit' | 'exact_legal_name' | 'normalized_name' | 'partial_name' | 'unresolved'
  evidence: string[]
  data_source: string
}
export interface SearchPage {
  items: SearchItem[]
  page: number
  page_size: number
  has_more: boolean
  stale: boolean
  warning: string | null
  ranking_scope: string
}
export interface DataSource {
  id: string
  name: string
  description: string
  provider: string
  dataset_url: string
  last_checked_at: string | null
  last_updated_at: string | null
  enabled: boolean
  availability: string
}
export interface RecordView {
  id: string
  external_record_id: string | null
  source_id: string
  source_url: string | null
  retrieved_at: string
  source_updated_at: string | null
  payload_hash: string
  fields: Record<string, string>
  field_mapping: Record<string, string>
}
export interface Profile extends Company {
  registration: Record<string, string | null>
  attributes: Record<
    string,
    { state: string; source_field: string | null; record_id: string | null; note: string | null }
  >
  sources: DataSource[]
  retrieved_at: string | null
  source_updated_at: string | null
  dataset_updated_at: string | null
  resolution_note: string
  conflicting_registration_count: number
}
