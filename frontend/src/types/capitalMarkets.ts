export type RegistrationStatus =
  | 'registered_active'
  | 'registered_cancelled'
  | 'historical'
  | 'not_found_in_checked_source'
  | 'unknown'
export type ListingStatus =
  'verified_listed' | 'verified_delisted' | 'not_found_in_checked_source' | 'unknown'
export const categories = {
  common_equity: 'Acciones ordinarias',
  preferred_equity: 'Acciones preferenciales',
  other_equity: 'Otras acciones',
  corporate_bonds: 'Bonos corporativos',
  commercial_paper: 'Papeles comerciales',
  securitized_instruments: 'Titularizaciones',
  collective_investment_instruments: 'Inversión colectiva',
  other_debt: 'Otros valores de deuda',
  other_or_unknown: 'Otro / sin clasificación verificada',
} as const
export interface MarketIssuer {
  id: string
  nit: string | null
  source_nit: string | null
  verification_digit: string | null
  issuer_name: string
  regulator_entity_code: string | null
  regulator_entity_type: string | null
  regulator_entity_type_description?: string | null
  contacts?: {
    institutional_email: string | null
    address: string | null
    city: string | null
    phone: string | null
    website: string | null
    social_networks: string[]
  }
  administration?: {
    board_members_count: number | null
    legal_representative: string | null
    rnve_information_representative: string | null
  }
  contacts_source_url?: string | null
  contacts_retrieved_at?: string | null
  administration_source_url?: string | null
  administration_retrieved_at?: string | null
  details_availability?: 'available' | 'not_yet_checked' | 'failed_to_retrieve' | 'stale'
  details_last_attempt_at?: string | null
  details_last_attempt_failed?: boolean
  registration_status: RegistrationStatus
  last_verified_at: string
  source_url: string
  match_status: 'verified' | 'potential' | 'rejected' | null
  snapshot_id: string
}
export interface Instrument {
  id: string
  security_name: string
  security_type_raw: string
  security_category: keyof typeof categories
  ticker: string | null
  isin: string | null
  ann_code: string | null
  issuance_number: string | null
  exchange: string | null
  rnve_registration_date: string | null
  bvc_registration_date: string | null
  listing_status: ListingStatus
  authorized_amount: string | null
  currency: string | null
  credit_rating: string | null
  source_url: string
  last_verified_at: string
  stale: boolean
  quality_notes?: string[]
  observation_status?: string
  source_values: Record<string, string>
  snapshot_id: string
}
export interface MarketSource {
  id: string
  name: string
  institution: string
  source_url: string
  availability: string
  last_ingestion_status?: string
  last_error?: string | null
  last_attempt_at: string | null
  last_success_at: string | null
  stale: boolean
  latest_snapshot: {
    id: string
    retrieved_at: string
    published_at: string | null
    observed_at: string | null
    complete_current: boolean
    content_hash: string | null
  } | null
}
export interface MarketsProfile {
  company_id: string
  rnve: { status: RegistrationStatus; match_status: string }
  exchange_listing: { status: ListingStatus; explanation: string; availability: string }
  equity_listed: boolean | null
  ownership: { type: string; verification_status: string }
  issuers: MarketIssuer[]
  instruments: Instrument[]
  sources: MarketSource[]
  securities_availability: string
  stale: boolean
  summary: string
  limitations: string[]
}
export interface SecuritiesPage {
  total: number
  unfiltered_total: number
  items: Instrument[]
  page: number
  page_size: number
  has_more: boolean
  availability: string
}
