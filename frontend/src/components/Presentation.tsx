import { Dropdown } from './Dropdown'
import type { ContractExportTarget } from '../presentation/context'
import { FilterHelp } from './AdvancedFilters'
import { CurrencyContext, ExportTargetContext } from '../presentation/context'
import { useContext, useState, useEffect, useRef, useId } from 'react'
import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { t, useLanguage } from '../i18n'
import { formatDate } from '../i18n/format'
import { errorMessage } from '../i18n/messages'
import { ApiError } from '../api/client'
import { validRate } from '../presentation/currency'
import type { Rate } from '../presentation/currency'

const today = () =>
  new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Bogota',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())

export function Presentation({
  children,
  companyInformation,
  companyId,
}: {
  children: ReactNode
  companyInformation?: ReactNode
  companyId?: string
}) {
  useLanguage()
  const [target, setTarget] = useState<ContractExportTarget | null>(null)
  const [selection, setSelection] = useState('COP')
  // Null means follow the published effective TRM; editing creates an explicit override.
  const [override, setOverride] = useState<{ value: string; enteredOn: string } | null>(null)
  const reference = useQuery<Rate>({
    queryKey: ['usd-reference-rate'],
    queryFn: async ({ signal }) => {
      const response = await fetch('/api/v1/presentation/usd-rate', { signal })
      if (!response.ok) throw new Error(t('presentation.unavailable'))
      return response.json() as Promise<Rate>
    },
    enabled: selection === 'USD',
    staleTime: 0,
    refetchInterval: selection === 'USD' ? 60_000 : false,
    retry: false,
  })
  const published = reference.data
  const usable =
    published &&
    validRate(published.cop_per_usd) &&
    !published.manual &&
    !published.stale &&
    !published.provider_failed &&
    published.effective_date <= today() &&
    published.effective_until >= today() &&
    !reference.isError
  const referenceRate = usable ? published : null
  const rate: Rate | null =
    selection !== 'USD'
      ? null
      : override !== null
        ? validRate(override.value)
          ? {
              cop_per_usd: override.value,
              source: t('presentation.manualSource'),
              source_url: null,
              effective_date: override.enteredOn,
              effective_until: override.enteredOn,
              retrieved_at: new Date().toISOString(),
              manual: true,
              stale: false,
              provider_failed: false,
            }
          : null
        : referenceRate
  const params = new URLSearchParams({
    fx_mode: selection === 'COP' ? 'cop' : override !== null ? 'manual' : 'reference',
  })
  if (override && rate) {
    params.set('manual_rate', override.value)
    // Manual entry date is audit context, never a claimed historical market rate date.
    params.set('rate_date', override.enteredOn)
  }
  const help = override
    ? t('presentation.manualHelp', { date: formatDate(override.enteredOn) })
    : published
      ? t('presentation.referenceHelp', {
          source: published.source,
          from: formatDate(published.effective_date),
          until: formatDate(published.effective_until),
        })
      : t('presentation.rateHelp')
  return (
    <ExportTargetContext.Provider value={{ target, setTarget }}>
      <CurrencyContext.Provider value={{ rate, params, ready: selection === 'COP' || !!rate }}>
        {companyId && <ExportButtons companyId={companyId} />}
        <div className="company-information">
          {companyInformation}
          <aside className="panel presentation-controls" aria-label={t('presentation.title')}>
            <div className="currency-card-heading">
              <label htmlFor="presentation-currency">{t('presentation.title')}</label>
              <FilterHelp label={t('presentation.title')} text={t('presentation.explanation')} />
            </div>
            <Dropdown
              id="presentation-currency"
              aria-label={t('presentation.title')}
              value={selection}
              onChange={setSelection}
              options={[
                { value: 'COP', label: 'COP' },
                { value: 'USD', label: 'USD' },
              ]}
            />
            {selection === 'USD' && (
              <>
                <div className="currency-rate-label">
                  <label htmlFor="presentation-rate">{t('presentation.rate')}</label>
                  <FilterHelp label={t('presentation.rate')} text={help} />
                </div>
                <div className="currency-rate-input">
                  <input
                    id="presentation-rate"
                    inputMode="decimal"
                    value={override?.value ?? referenceRate?.cop_per_usd ?? ''}
                    onChange={(e) => setOverride({ value: e.target.value, enteredOn: today() })}
                    aria-invalid={override !== null && !validRate(override.value)}
                  />
                  <button
                    className="refresh-button"
                    type="button"
                    aria-label={t('presentation.retry')}
                    title={t('presentation.retry')}
                    disabled={reference.isFetching}
                    aria-busy={reference.isFetching}
                    onClick={() => {
                      setOverride(null)
                      void reference.refetch()
                    }}
                  >
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.6"
                      aria-hidden="true"
                    >
                      <path
                        d="M20 7v5h-5M20 12a8 8 0 1 0-2 5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </button>
                </div>
                <p className="small muted currency-rate-status" role="status">
                  {override ? (
                    rate ? (
                      t('presentation.manualSource')
                    ) : (
                      t('presentation.invalid')
                    )
                  ) : reference.isPending ? (
                    t('presentation.loading')
                  ) : !rate ? (
                    t('presentation.unavailable')
                  ) : (
                    <>
                      {t('presentation.effectiveTrm')} · {formatDate(rate.effective_date)}
                    </>
                  )}
                </p>
              </>
            )}
          </aside>
        </div>
        {children}
      </CurrencyContext.Provider>
    </ExportTargetContext.Provider>
  )
}

export function ExportButtons({ companyId }: { companyId: string }) {
  useLanguage()
  const currency = useContext(CurrencyContext)
  const { target: registeredTarget } = useContext(ExportTargetContext)
  const target = registeredTarget?.companyId === companyId ? registeredTarget : null
  const [chosenScope, setChosenScope] = useState<'research' | 'contracts' | null>(null)
  const scope = target && chosenScope !== 'research' ? 'contracts' : 'research'
  const filters = scope === 'contracts' && target ? new URLSearchParams(target.filters) : undefined
  const blocked = !currency.ready || (scope === 'contracts' && !!target?.disabled)
  const [open, setOpen] = useState(false)
  const dropdown = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const popupId = useId()
  useEffect(() => {
    if (!open) return
    const dismiss = (event: PointerEvent) => {
      if (!dropdown.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', dismiss)
    return () => document.removeEventListener('pointerdown', dismiss)
  }, [open])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function save(format: 'csv' | 'json') {
    setBusy(true)
    setError('')
    try {
      const params = new URLSearchParams(filters)
      params.delete('page')
      params.delete('page_size')
      currency.params.forEach((value, key) => params.set(key, value))
      params.set('format', format)
      const response = await fetch(
        `/api/v1/companies/${encodeURIComponent(companyId)}/exports/${scope}?${params}`,
      )
      if (!response.ok) {
        const payload = await response.json().catch(() => null)
        throw new ApiError(
          payload?.error?.message ?? t('presentation.exportFailed'),
          payload?.error?.code ?? 'export_failed',
          response.status,
        )
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${scope}-${companyId}.${format}`
      link.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 413
          ? t('presentation.tooLarge')
          : err instanceof ApiError && err.status === 409
            ? t('presentation.changed')
            : errorMessage(err instanceof Error ? err : new Error(t('presentation.exportFailed'))),
      )
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="export-area">
      <div className="export-controls" aria-label={t('presentation.exportAction')}>
        <Dropdown
          className="export-scope"
          aria-label={t('presentation.exportScope')}
          value={scope}
          onChange={(value) => {
            setChosenScope(value as 'research' | 'contracts')
            setOpen(false)
          }}
          options={[
            { value: 'research', label: t('presentation.researchScope') },
            ...(target ? [{ value: 'contracts', label: t('presentation.contractScope') }] : []),
          ]}
        />
        <span className="export-limit small muted">{t('presentation.exportLimit')}</span>
        <FilterHelp
          label={t('presentation.exportAction')}
          text={t(
            scope === 'contracts' ? 'presentation.contractExport' : 'presentation.researchExport',
          )}
        />
        <div
          className="export-dropdown"
          ref={dropdown}
          onBlur={(e) => {
            if (!e.currentTarget.contains(e.relatedTarget)) setOpen(false)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              setOpen(false)
              trigger.current?.focus()
            }
          }}
        >
          <button
            className="refresh-button export-trigger"
            ref={trigger}
            type="button"
            disabled={blocked || busy}
            aria-expanded={open && !blocked && !busy}
            aria-controls={popupId}
            aria-busy={busy}
            onClick={() => setOpen((value) => !value)}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') {
                e.preventDefault()
                setOpen(true)
                requestAnimationFrame(() =>
                  dropdown.current
                    ?.querySelector<HTMLButtonElement>('.export-options button')
                    ?.focus(),
                )
              }
            }}
          >
            {t(busy ? 'presentation.exporting' : 'presentation.exportAction')}
            <svg
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              aria-hidden="true"
            >
              <path d="m4 6 4 4 4-4" />
            </svg>
          </button>
          {open && !blocked && !busy && (
            <div
              className="export-options dropdown-panel"
              id={popupId}
              role="group"
              aria-label={t('presentation.exportFormats')}
            >
              {(['csv', 'json'] as const).map((format) => (
                <button
                  key={format}
                  type="button"
                  className="dropdown-option"
                  onClick={() => {
                    setOpen(false)
                    trigger.current?.focus()
                    void save(format)
                  }}
                >
                  {format.toUpperCase()}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
      <p className="small export-status" role="status">
        {error}
      </p>
    </div>
  )
}
