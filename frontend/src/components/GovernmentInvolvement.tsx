import { useEffect, useId, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { useRefreshFeedback } from '../hooks/useRefreshFeedback'
import { request } from '../api/client'
import { t, useLanguage } from '../i18n'
import { formatDate } from '../i18n/format'
import { ContractDetail } from './ContractDetail'
import { PopupActions } from './PopupActions'
import { FilterHelp } from './AdvancedFilters'
import { InvolvementEvidence } from './InvolvementEvidence'
import type { DecisionId, Involvement, InvolvementDecision } from '../types/governmentInvolvement'

const dimensions: DecisionId[] = [
  'direct_participation',
  'historical_participation',
  'recent_participation',
  'currently_reported_execution',
]
const sufficiency = ['sufficient', 'limited', 'missing', 'stale', 'contradictory', 'incomplete']
const label = (key: string) => t(`involvement.${key}`)
function endpoint(companyId?: string, runId?: string | null, months = 24) {
  const params = new URLSearchParams({ lookback_months: String(months) })
  if (runId) params.set('run_id', runId)
  return companyId
    ? `/api/v1/companies/${encodeURIComponent(companyId)}/screening/secop/involvement?${params}`
    : '/api/v1/government-involvement/demo'
}
async function loadInvolvement(path: string, signal?: AbortSignal): Promise<Involvement> {
  const value = await request<Involvement>(path, signal)
  if (
    !value ||
    !Array.isArray(value.decisions) ||
    !value.engine ||
    !value.evaluation ||
    !value.source ||
    !['disabled', 'blocked', 'demo', 'completed', 'failed', 'running'].includes(value.status)
  )
    throw new Error('invalid_involvement_response')
  return value
}
function availability(value: Involvement) {
  if (value.status === 'failed') return t('involvement.error')
  if (value.status === 'running') return t('involvement.running')
  if (value.status === 'disabled') return t('involvement.disabledNotice')
  return t(`involvement.availability.${value.diagnostics[0]}`, {
    defaultValue: t('involvement.notReady'),
  })
}
function OutcomePill({ outcome }: { outcome: string }) {
  return (
    <span
      className={`involvement-pill ${['documented', 'reported'].includes(outcome) ? 'present' : 'neutral'}`}
    >
      {label(outcome)}
    </span>
  )
}
function SufficiencyPill({ status }: { status: string }) {
  return (
    <span className={`involvement-pill evidence-${status}`}>
      {t(`involvement.sufficiencyLabels.${status}`)}
    </span>
  )
}
function ConclusionTitle({ id }: { id: DecisionId }) {
  return (
    <div className="involvement-conclusion-title">
      <strong>{label(id)}</strong>
      <FilterHelp label={label(id)} text={t(`involvement.brief.${id}`)} />
    </div>
  )
}
function Conclusions({
  value,
  masked = false,
  selected,
  onSelect,
}: {
  value?: Involvement
  masked?: boolean
  selected?: string
  onSelect: (id: DecisionId) => void
}) {
  return (
    <div className="involvement-dimensions" aria-busy={masked}>
      {dimensions.map((id) => {
        const decision = value?.decisions.find((item) => item.id === id)
        return (
          <article
            key={id}
            className={`involvement-dimension${selected === id ? ' is-selected' : ''}`}
          >
            <ConclusionTitle id={id} />
            {masked ? (
              <div
                className="involvement-result-skeleton"
                aria-label={t('involvement.pendingResult')}
              >
                <span />
                <span />
              </div>
            ) : (
              <>
                <button
                  className="involvement-outcome-button"
                  onClick={() => onSelect(id)}
                  aria-label={`${label(id)} — ${label(decision?.outcome ?? 'undetermined')}`}
                  aria-pressed={selected ? selected === id : undefined}
                >
                  <OutcomePill outcome={decision?.outcome ?? 'undetermined'} />
                </button>
                {decision && (
                  <span className="small muted">
                    {t('involvement.evidenceLabel')}:{' '}
                    {t(`involvement.sufficiencyLabels.${decision.evidence_status}`)}
                  </span>
                )}
              </>
            )}
          </article>
        )
      })}
    </div>
  )
}
function SourceReferences({
  decision,
  demo,
  openContract,
}: {
  decision: InvolvementDecision
  demo: boolean
  openContract: (id: string) => void
}) {
  return (
    <details className="involvement-supporting-sources">
      <summary>{t('involvement.supportingSources')}</summary>
      {decision.source_references?.length ? (
        decision.source_references.map((ref) => (
          <article key={ref.evidence_id}>
            <button className="text-link" onClick={() => openContract(ref.contract_id)}>
              {ref.contract_id}
            </button>
            <span className="small muted">{formatDate(ref.observed_at, true)}</span>
            <a
              className="text-link small"
              href={ref.source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {t('involvement.officialSource')} ↗
            </a>
          </article>
        ))
      ) : (
        <p className="small muted">
          {demo ? t('involvement.synthetic_source') : t('involvement.noSupportingSource')}
        </p>
      )}
    </details>
  )
}
function Evaluation({ value, selected }: { value: Involvement; selected?: string }) {
  const [active, setActive] = useState<DecisionId>(
    dimensions.includes(selected as DecisionId) ? (selected as DecisionId) : 'direct_participation',
  )
  const [detail, setDetail] = useState<string | null>(null)
  const decision = value.decisions.find((item) => item.id === active)
  return (
    <section aria-labelledby="involvement-evidence-title">
      <h2 id="involvement-evidence-title">{t('involvement.conclusions')}</h2>
      {value.status === 'demo' && <p className="notice">{t('involvement.demoNotice')}</p>}
      {!value.decisions.length && <p className="notice">{availability(value)}</p>}
      {value.source.is_stale && <p className="notice warning">{t('involvement.stale')}</p>}
      {value.source.evaluation_is_stale && (
        <p className="notice warning">{t('involvement.previousEvaluation')}</p>
      )}
      <p className="small muted">
        {t('involvement.months', { count: value.evaluation.lookback_months })} ·{' '}
        {formatDate(value.evaluation.lookback_start_date)} —{' '}
        {formatDate(value.evaluation.as_of_date)}
      </p>
      <Conclusions value={value} selected={active} onSelect={setActive} />
      {decision && (
        <section
          className="involvement-selected-evidence"
          aria-label={t('involvement.evidenceFor', { name: label(active) })}
        >
          <div className="involvement-evidence-heading">
            <h3>{label(active)}</h3>
            <OutcomePill outcome={decision.outcome} />
          </div>
          <p className="small">
            {t('involvement.sufficiency')}: <SufficiencyPill status={decision.evidence_status} />
          </p>
          {decision.warnings.map((warning) => (
            <p className="small" key={warning}>
              {label(warning)}
            </p>
          ))}
          <InvolvementEvidence decision={decision} demo={value.status === 'demo'} />
          <SourceReferences
            decision={decision}
            demo={value.status === 'demo'}
            openContract={setDetail}
          />
          {!!decision.native_diagnostics?.length && (
            <details>
              <summary>{t('involvement.modelDiagnostics')}</summary>
              <ul>
                {decision.native_diagnostics.map((item, index) => (
                  <li key={index}>{item.object}</li>
                ))}
              </ul>
            </details>
          )}
        </section>
      )}
      {detail && value.company_id && value.screening_run_id && (
        <ContractDetail
          companyId={value.company_id}
          runId={value.screening_run_id}
          id={detail}
          close={() => setDetail(null)}
        />
      )}
      <details className="involvement-evaluation-details">
        <summary>{t('involvement.evaluationDetails')}</summary>
        <dl className="involvement-metadata">
          <div>
            <dt>{t('involvement.model')}</dt>
            <dd>
              {value.engine.model_id ?? t('involvement.unconfigured')} ·{' '}
              {value.engine.model_version ?? '—'}
            </dd>
          </div>
          <div>
            <dt>{t('involvement.policy')}</dt>
            <dd>{value.evaluation.policy_version}</dd>
          </div>
          <div>
            <dt>{t('involvement.evaluated')}</dt>
            <dd>{formatDate(value.evaluation.evaluated_at, true)}</dd>
          </div>
          <div>
            <dt>{t('involvement.observed')}</dt>
            <dd>
              {value.source.snapshot_completed_at
                ? formatDate(value.source.snapshot_completed_at, true)
                : '—'}
            </dd>
          </div>
        </dl>
      </details>
    </section>
  )
}

export function RaeMethodology({ value, selected }: { value?: Involvement; selected?: string }) {
  useLanguage()
  return (
    <div className="rae-methodology">
      {value ? (
        <Evaluation value={value} selected={selected} />
      ) : (
        <section>
          <h2>{t('involvement.conclusions')}</h2>
          <p>{t('involvement.coexist')}</p>
          <div className="involvement-method-list">
            {dimensions.map((id) => (
              <ConclusionTitle key={id} id={id} />
            ))}
          </div>
        </section>
      )}
      <section aria-labelledby="sufficiency-title">
        <h2 id="sufficiency-title">{t('involvement.sufficiency')}</h2>
        <dl className="involvement-sufficiency-guide">
          {sufficiency.map((status) => (
            <div key={status}>
              <dt>
                <SufficiencyPill status={status} />
              </dt>
              <dd>{t(`involvement.sufficiencyDescriptions.${status}`)}</dd>
            </div>
          ))}
        </dl>
      </section>
      <details className="involvement-about">
        <summary>{t('involvement.aboutRae')}</summary>
        <section>
          <h3>{t('involvement.what')}</h3>
          <p>{t('involvement.whatText')}</p>
        </section>
        <section>
          <h3>{t('involvement.how')}</h3>
          <p>{t('involvement.howText')}</p>
          <ol className="involvement-flow">
            {['officialSources', 'verification', 'reasoning', 'outputs', 'title'].map(
              (key, index) => (
                <li key={key}>
                  <span className="small muted">{index + 1}</span> {label(key)}
                </li>
              ),
            )}
          </ol>
        </section>
      </details>
      <details className="involvement-references">
        <summary>{t('involvement.references')}</summary>
        <ul>
          {[
            ['https://www.rainbird.ai/', 'Rainbird AI'],
            ['https://docs.rainbird.ai/rainbird', t('involvement.docs')],
            ['https://www.datos.gov.co/d/jbjy-vk9h', 'SECOP II · jbjy-vk9h'],
            [
              'https://github.com/molartep/colombia-company-intelligence/blob/main/docs/secop-screening.md',
              t('involvement.secopMethodology'),
            ],
            [
              'https://github.com/molartep/colombia-company-intelligence/blob/main/docs/RaeManual.md',
              t('involvement.manual'),
            ],
          ].map(([url, text]) => (
            <li key={url}>
              <a className="text-link" href={url} target="_blank" rel="noopener noreferrer">
                {text} ↗
              </a>
            </li>
          ))}
        </ul>
      </details>
    </div>
  )
}
function MethodologyDialog({
  close,
  href,
  value,
  selected,
}: {
  close: () => void
  href: string
  value?: Involvement
  selected?: string
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const startedOutside = useRef(false)
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const element = dialog.current
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    element?.showModal()
    return () => {
      element?.close()
      document.body.style.overflow = overflow
      previous?.focus()
    }
  }, [])
  const outside = (event: { clientX: number; clientY: number }) => {
    const box = dialog.current?.getBoundingClientRect()
    return (
      !!box &&
      (event.clientX < box.left ||
        event.clientX > box.right ||
        event.clientY < box.top ||
        event.clientY > box.bottom)
    )
  }
  return (
    <dialog
      ref={dialog}
      className="involvement-dialog"
      aria-labelledby="rae-dialog-title"
      onCancel={(event) => {
        event.preventDefault()
        close()
      }}
      onPointerDown={(event) => {
        startedOutside.current = event.target === event.currentTarget && outside(event)
      }}
      onClick={(event) => {
        if (startedOutside.current && event.target === event.currentTarget && outside(event))
          close()
      }}
    >
      <div className="involvement-dialog-header">
        <h2 id="rae-dialog-title">{t('involvement.title')}</h2>
        <PopupActions close={close} href={href} />
      </div>
      <RaeMethodology value={value} selected={selected} />
    </dialog>
  )
}
function LookbackControl({
  draft,
  onChange,
  applied,
  onApply,
  busy,
}: {
  draft: string
  onChange: (value: string) => void
  applied: number
  onApply: () => void
  busy: boolean
}) {
  const id = useId()
  const numeric = Number(draft)
  const valid = /^\d+$/.test(draft) && numeric >= 1 && numeric <= 120
  const dirty = draft !== String(applied)
  return (
    <form
      className="involvement-lookback"
      onSubmit={(event) => {
        event.preventDefault()
        if (valid && dirty) onApply()
      }}
    >
      <div className="involvement-lookback-heading">
        <label htmlFor={`${id}-months`}>{t('involvement.window')}</label>
        <span className="small muted">{t('involvement.lookbackRange')}</span>
      </div>
      <div className="involvement-lookback-inputs">
        <input
          type="range"
          min="1"
          max="120"
          step="1"
          value={valid ? numeric : applied}
          aria-label={t('involvement.lookbackSlider')}
          aria-valuetext={t('involvement.months', { count: valid ? numeric : applied })}
          onChange={(event) => onChange(event.target.value)}
        />
        <div className="involvement-month-input">
          <input
            id={`${id}-months`}
            type="number"
            required
            min="1"
            max="120"
            step="1"
            value={draft}
            onChange={(event) => onChange(event.target.value)}
            aria-invalid={!valid}
            aria-describedby={!valid ? `${id}-error` : undefined}
          />
          <span>{t('involvement.monthsUnit')}</span>
        </div>
        {dirty && (
          <button
            className="refresh-button involvement-apply"
            type="submit"
            disabled={!valid || busy}
          >
            {t('involvement.apply')}
          </button>
        )}
      </div>
      {!valid && (
        <p className="small" id={`${id}-error`} role="alert">
          {t('involvement.lookbackInvalid')}
        </p>
      )}
      {dirty && valid && (
        <p className="small muted" role="status">
          {t('involvement.applyHint')}
        </p>
      )}
    </form>
  )
}

export function GovernmentInvolvement({
  companyId,
  runId,
}: {
  companyId: string
  runId: string | null
}) {
  useLanguage()
  const [selection, setSelection] = useState<string | null>(null)
  const [appliedMonths, setAppliedMonths] = useState(24)
  const [draft, setDraft] = useState('24')
  const client = useQueryClient()
  const key = ['involvement', companyId, runId, appliedMonths]
  const query = useQuery({
    queryKey: key,
    queryFn: ({ signal }) => loadInvolvement(endpoint(companyId, runId, appliedMonths), signal),
    refetchInterval: (query) => (query.state.data?.status === 'running' ? 2000 : false),
  })
  const feedback = useRefreshFeedback()
  const refresh = useMutation({
    onError: feedback.onError,
    mutationFn: () =>
      request<Involvement>(
        `${endpoint(companyId, null, appliedMonths).split('?')[0]}/refresh?${new URLSearchParams({ lookback_months: String(appliedMonths), ...(runId ? { run_id: runId } : {}) })}`,
        undefined,
        { method: 'POST' },
      ),
    onSuccess: (data) => client.setQueryData(key, data),
  })
  const dirty = draft !== String(appliedMonths)
  const masked = dirty || query.isPending
  const href = `/methodology/rae?${new URLSearchParams({ company: companyId, lookback_months: String(appliedMonths), ...(runId ? { run: runId } : {}), ...(selection && selection !== 'all' ? { decision: selection } : {}) })}`
  return (
    <article className="panel involvement-card">
      <div className="involvement-heading">
        <h2>{t('involvement.title')}</h2>
        <a
          className="text-link involvement-powered"
          href="https://docs.rainbird.ai/rainbird"
          target="_blank"
          rel="noopener noreferrer"
        >
          {t('involvement.poweredBy')}
        </a>
      </div>
      <LookbackControl
        draft={draft}
        onChange={setDraft}
        applied={appliedMonths}
        busy={refresh.isPending}
        onApply={() => {
          setDraft(String(Number(draft)))
          setAppliedMonths(Number(draft))
          refresh.reset()
        }}
      />
      {query.isError && !dirty && <p role="alert">{t('involvement.error')}</p>}
      {query.data && !dirty && (
        <>
          {query.data.status === 'demo' && (
            <p className="small muted">{t('involvement.demoNotice')}</p>
          )}
          {!query.data.decisions.length && (
            <p className="small muted">{availability(query.data)}</p>
          )}
          {query.data.source.is_stale && <p className="notice warning">{t('involvement.stale')}</p>}
          {query.data.source.evaluation_is_stale && (
            <p className="notice warning">{t('involvement.previousEvaluation')}</p>
          )}
        </>
      )}
      {query.isPending && (
        <p className="sr-only" role="status">
          {t('involvement.loading')}
        </p>
      )}
      <Conclusions value={query.data} masked={masked} onSelect={setSelection} />
      {refresh.isError && !dirty && (
        <p role="alert">{feedback.message(refresh.error) ?? t('involvement.refreshError')}</p>
      )}
      <div className="involvement-actions">
        {runId && ['completed', 'failed'].includes(query.data?.status ?? '') && (
          <button
            className="refresh-button"
            disabled={masked || refresh.isPending || feedback.seconds > 0}
            aria-busy={refresh.isPending}
            onClick={() => refresh.mutate()}
          >
            {refresh.isPending
              ? t('involvement.running')
              : feedback.seconds > 0
                ? t('common.refreshInSeconds', { count: feedback.seconds })
                : t('involvement.refresh')}
          </button>
        )}
        <button className="text-link" disabled={masked} onClick={() => setSelection('all')}>
          {t('involvement.learnMore')} →
        </button>
      </div>
      {selection && (
        <MethodologyDialog
          close={() => setSelection(null)}
          href={href}
          value={query.data}
          selected={selection}
        />
      )}
    </article>
  )
}
export function RaePage() {
  useLanguage()
  const [params] = useSearchParams()
  const company = params.get('company') ?? undefined
  const demo = params.get('demo') === 'true' && !company
  const requested = Number(params.get('lookback_months') ?? '24')
  const months = Number.isInteger(requested) && requested >= 1 && requested <= 120 ? requested : 24
  const query = useQuery({
    queryKey: ['involvement', company, params.get('run'), months, demo],
    queryFn: ({ signal }) => loadInvolvement(endpoint(company, params.get('run'), months), signal),
    enabled: !!company || demo,
    refetchInterval: (query) => (query.state.data?.status === 'running' ? 2000 : false),
  })
  return (
    <article className="panel rae-page">
      <h1>{t('involvement.title')}</h1>
      {!company && !demo && (
        <a className="text-link" href="/methodology/rae?demo=true">
          {t('involvement.viewDemo')} →
        </a>
      )}
      {query.isFetching && <p role="status">{t('involvement.loading')}</p>}
      {query.isError && <p role="alert">{t('involvement.error')}</p>}
      <RaeMethodology value={query.data} selected={params.get('decision') ?? undefined} />
    </article>
  )
}
