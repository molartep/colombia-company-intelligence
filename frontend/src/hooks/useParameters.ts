import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export function useParameters(enabled = true) {
  return useQuery({
    queryKey: ['parameters'],
    queryFn: ({ signal }) => api.parameters(signal),
    staleTime: Infinity,
    gcTime: 30 * 60_000,
    enabled,
  })
}
