import type { Dispatch, SetStateAction } from 'react'
import { createContext, useContext, useEffect } from 'react'
import type { Rate } from './currency'
import { toUsd } from './currency'
import { formatCurrency, formatDecimal } from '../i18n/format'

export const CurrencyContext = createContext({
  rate: null as Rate | null,
  params: new URLSearchParams(),
  ready: true,
})

/** Display-only projection: callers retain their original source amount/currency. */
export function useCurrencyAmounts() {
  const { rate } = useContext(CurrencyContext)
  const currency = (code: string | null | undefined) => (rate && code === 'COP' ? 'USD' : code)
  const format = (amount: string, code?: string | null, omitCode = false, codeAfter = false) => {
    const converted = rate && code === 'COP' ? toUsd(amount, rate.cop_per_usd) : null
    if (converted !== null)
      return `≈ ${omitCode ? formatDecimal(converted) : codeAfter ? `${formatDecimal(converted)} USD` : formatCurrency(converted, 'USD')}`
    return omitCode || !code
      ? formatDecimal(amount)
      : codeAfter
        ? `${formatDecimal(amount)} ${code}`
        : formatCurrency(amount, code)
  }
  return { currency, format }
}

export interface ContractExportTarget {
  companyId: string
  filters: string
  disabled: boolean
}
export const ExportTargetContext = createContext<{
  target: ContractExportTarget | null
  setTarget: Dispatch<SetStateAction<ContractExportTarget | null>>
}>({ target: null, setTarget: () => {} })

export function useContractExport(companyId: string, filters: string, disabled: boolean) {
  const { setTarget } = useContext(ExportTargetContext)
  useEffect(() => {
    setTarget({ companyId, filters, disabled })
    return () => setTarget(null)
  }, [companyId, filters, disabled, setTarget])
}
