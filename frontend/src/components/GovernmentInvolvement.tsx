import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { request } from '../api/client'
import { t, useLanguage } from '../i18n'
import { formatDate } from '../i18n/format'
import type { DecisionId, EvidenceNode, Involvement } from '../types/governmentInvolvement'

const dimensions: DecisionId[] = [
  'direct_participation',
  'historical_participation',
  'recent_participation',
  'currently_reported_execution',
]
const endpoint = (companyId?: string, runId?: string | null) =>
  companyId
    ? `/api/v1/companies/${encodeURIComponent(companyId)}/screening/secop/involvement${runId ? `?run_id=${encodeURIComponent(runId)}` : ''}`
    : '/api/v1/government-involvement/demo'
const label = (key: string) => t(`involvement.${key}`)
async function loadInvolvement(path: string, signal?: AbortSignal): Promise<Involvement> {
  const value = await request<Involvement>(path, signal)
  if (
    !value ||
    !Array.isArray(value.decisions) ||
    !value.engine ||
    !value.evaluation ||
    !value.source ||
    !['disabled', 'blocked', 'demo', 'completed', 'failed'].includes(value.status)
  )
    throw new Error('invalid_involvement_response')
  return value
}

function Tree({ node, demo }: { node: EvidenceNode; demo: boolean }) {
  const text = demo && !node.label.startsWith('SYNTHETIC-') ? label(node.label) : node.label
  return (
    <li className={`involvement-node involvement-node-${node.kind}`}>
      <details open={node.kind === 'decision'}>
        <summary>
          <span className="small muted">{label(node.kind)}</span> · {text}
        </summary>
        {node.children.length > 0 && (
          <ul>
            {node.children.map((child, index) => (
              <Tree key={`${child.id}-${index}`} node={child} demo={demo} />
            ))}
          </ul>
        )}
      </details>
    </li>
  )
}

function Evaluation({ value, selected }: { value: Involvement; selected?: string }) {
  return (
    <section aria-labelledby="involvement-evidence-title">
      <h3 id="involvement-evidence-title">{t('involvement.evidence')}</h3>
      {value.status === 'demo' && <p className="notice">{t('involvement.demoNotice')}</p>}
      {!value.decisions.length && (
        <>
          <p className="notice">{t('involvement.disabledNotice')}</p>
          <a
            className="text-link"
            href="/methodology/rae?demo=true"
            target="_blank"
            rel="noopener noreferrer"
          >
            {t('involvement.viewDemo')} ↗
          </a>
        </>
      )}
      {value.source.is_stale && <p className="notice warning">{t('involvement.stale')}</p>}
      <dl className="involvement-metadata">
        <div>
          <dt>{t('involvement.window')}</dt>
          <dd>{t('involvement.months', { count: value.evaluation.lookback_months })}</dd>
        </div>
        <div>
          <dt>{t('involvement.boundary')}</dt>
          <dd>
            {formatDate(value.evaluation.lookback_start_date)} —{' '}
            {formatDate(value.evaluation.as_of_date)}
          </dd>
        </div>
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
      {value.decisions.map((decision) => (
        <details
          className="involvement-decision-detail"
          key={decision.id}
          open={selected === decision.id || undefined}
        >
          <summary>
            {label(decision.id)} — {label(decision.outcome)}
          </summary>
          <p>
            {t('involvement.sufficiency')}: {label(decision.evidence_status)}
          </p>
          {decision.warnings.map((warning) => (
            <p key={warning}>{label(warning)}</p>
          ))}
          {decision.evidence_tree ? (
            <ul className="involvement-tree">
              <Tree node={decision.evidence_tree} demo={value.status === 'demo'} />
            </ul>
          ) : (
            <p>{t('involvement.missingTree')}</p>
          )}
          <p className="small">
            {t('involvement.contracts')}: {decision.supporting_contract_ids.join(', ') || '—'}
          </p>
          {value.status !== 'demo' &&
            value.company_id &&
            decision.supporting_contract_ids.map((id) => (
              <a
                key={id}
                className="text-link"
                href={`/companies/${encodeURIComponent(value.company_id!)}?tab=screening&contract=${encodeURIComponent(id)}&run_id=${encodeURIComponent(value.screening_run_id ?? '')}`}
              >
                {id}
              </a>
            ))}
        </details>
      ))}
    </section>
  )
}

export function RaeMethodology({ value, selected }: { value?: Involvement; selected?: string }) {
  useLanguage()
  return (
    <div className="rae-methodology">
      <section>
        <h2>{t('involvement.what')}</h2>
        <p>{t('involvement.whatText')}</p>
      </section>
      <section>
        <h2>{t('involvement.how')}</h2>
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
      <section>
        <h2>{t('involvement.methodology')}</h2>
        <p>{t('involvement.coexist')}</p>
        <dl className="involvement-methods">
          {dimensions.map((id) => (
            <div key={id}>
              <dt>{label(id)}</dt>
              <dd>{label(`${id}Text`)}</dd>
            </div>
          ))}
          <div>
            <dt>{t('involvement.sufficiency')}</dt>
            <dd>{t('involvement.sufficiencyText')}</dd>
          </div>
        </dl>
      </section>
      {value && <Evaluation value={value} selected={selected} />}
      <section>
        <h2>{t('involvement.interpretation')}</h2>
        <p>{t('involvement.interpretationText')}</p>
      </section>
      <section>
        <h2>{t('involvement.references')}</h2>
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
      </section>
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
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const element = dialog.current
    element?.showModal()
    return () => {
      element?.close()
      previous?.focus()
    }
  }, [])
  return (
    <dialog
      ref={dialog}
      className="involvement-dialog"
      aria-labelledby="rae-dialog-title"
      onCancel={close}
    >
      <div className="involvement-dialog-header">
        <h2 id="rae-dialog-title">{t('involvement.methodology')}</h2>
        <button className="refresh-button" onClick={close}>
          {t('involvement.close')}
        </button>
      </div>
      <a className="text-link" href={href} target="_blank" rel="noopener noreferrer">
        {t('involvement.newTab')} ↗
      </a>
      <RaeMethodology value={value} selected={selected} />
    </dialog>
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
  const query = useQuery({
    queryKey: ['involvement', companyId, runId],
    queryFn: ({ signal }) => loadInvolvement(endpoint(companyId, runId), signal),
  })
  const href = `/methodology/rae?${new URLSearchParams({ company: companyId, ...(runId ? { run: runId } : {}), ...(selection && selection !== 'all' ? { decision: selection } : {}) })}`
  return (
    <article className="panel involvement-card">
      <div className="involvement-heading">
        <div>
          <p className="eyebrow">{t('involvement.eyebrow')}</p>
          <h2>{t('involvement.title')}</h2>
        </div>
        <span className="involvement-pill neutral">
          {query.data?.status === 'completed'
            ? t('involvement.live')
            : query.data?.status === 'demo'
              ? t('involvement.demoLabel')
              : t('involvement.unavailable')}
        </span>
      </div>
      <p>{t('involvement.intro')}</p>
      {query.isPending ? (
        <p role="status">{t('involvement.loading')}</p>
      ) : query.isError ? (
        <p role="alert">{t('involvement.error')}</p>
      ) : (
        <>
          <p className="small muted">
            {query.data.status === 'demo'
              ? t('involvement.demoNotice')
              : query.data.decisions.length
                ? t('involvement.attribution')
                : t('involvement.disabledNotice')}
          </p>
          <div className="involvement-dimensions">
            {dimensions.map((id) => {
              const decision = query.data.decisions.find((item) => item.id === id)
              const outcome = decision?.outcome ?? 'undetermined'
              return (
                <button key={id} className="involvement-dimension" onClick={() => setSelection(id)}>
                  <strong>{label(id)}</strong>
                  <span
                    className={`involvement-pill ${outcome === 'documented' || outcome === 'reported' ? 'present' : 'neutral'}`}
                  >
                    {label(outcome)}
                  </span>
                  {decision && (
                    <span className="small muted">{label(decision.evidence_status)}</span>
                  )}
                </button>
              )
            })}
          </div>
        </>
      )}
      <button className="text-link" onClick={() => setSelection('all')}>
        {t('involvement.learnMore')} →
      </button>
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
  const query = useQuery({
    queryKey: ['involvement', company, params.get('run'), demo],
    queryFn: ({ signal }) => loadInvolvement(endpoint(company, params.get('run')), signal),
    enabled: !!company || demo,
  })
  return (
    <article className="panel rae-page">
      <p className="eyebrow">{t('involvement.eyebrow')}</p>
      <h1>{t('involvement.methodology')}</h1>
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
