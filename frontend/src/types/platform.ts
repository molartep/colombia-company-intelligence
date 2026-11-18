import type { DataSource } from './index'
import type { MarketSource } from './capitalMarkets'

export interface PlatformStatus {
  checked_at: string
  counts: Record<string, number>
  rues: DataSource
  sources: MarketSource[]
  directory_missing: boolean
  import_access: 'local' | 'admin_key' | 'disabled'
  parameter_verified_at: string
  parameter_options: number
}

export interface ImportResult {
  snapshot_id: string
  record_count: number
  retrieved_at: string
  content_hash: string | null
  complete_current: boolean
}
