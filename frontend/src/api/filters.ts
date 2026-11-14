export const fixedFilterKeys = ['status', 'chamber', 'organization', 'category'] as const
export const scalarFilterKeys = [
  'ciiu',
  'ciiu_match',
  'ciiu_scope',
  'registration_from',
  'registration_to',
  'renewal_from',
  'renewal_to',
  'renewed_year',
  'renewed_year_mode',
] as const
export type FixedFilterKey = (typeof fixedFilterKeys)[number]
export type ScalarFilterKey = (typeof scalarFilterKeys)[number]
export type FilterValues = Record<FixedFilterKey, string[]> & Record<ScalarFilterKey, string>
export const emptyFilters: FilterValues = {
  status: [],
  chamber: [],
  organization: [],
  category: [],
  ciiu: '',
  ciiu_match: 'exact',
  ciiu_scope: 'primary',
  registration_from: '',
  registration_to: '',
  renewal_from: '',
  renewal_to: '',
  renewed_year: '',
  renewed_year_mode: 'exact',
}
export function readFilters(params: URLSearchParams): FilterValues {
  const values = { ...emptyFilters }
  for (const key of fixedFilterKeys) values[key] = [...new Set(params.getAll(key))].sort()
  for (const key of scalarFilterKeys) values[key] = params.get(key) ?? emptyFilters[key]
  return values
}
export function filterParams(values: FilterValues): URLSearchParams {
  const params = new URLSearchParams()
  for (const key of fixedFilterKeys) {
    for (const value of [...new Set(values[key])].sort()) params.append(key, value)
  }
  for (const key of scalarFilterKeys) {
    if (values[key] && values[key] !== emptyFilters[key]) params.set(key, values[key])
  }
  return params
}
export function searchKey(q: string, page: number, filters: string) {
  return filters ? ['search', q, page, filters] : ['search', q, page]
}
