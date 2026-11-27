import { t } from '../i18n'
import { formatDate, formatNumber } from '../i18n/format'
import type { EvidenceNode, InvolvementDecision } from '../types/governmentInvolvement'

type Fact = { subject: string; relationship: string; object: string }
const groups: Record<string, string[]> = {
  identity: ['identity_verified', 'attribution_verified', 'contains_contract', 'eligible_contract'],
  dates: [
    'signature_date',
    'signature_band',
    'signature_conflict',
    'as_of_date',
    'lookback_start_date',
    'lookback_months',
    'scheduled_end_date',
    'historical_witness',
    'recent_witness',
    'temporal_coverage',
  ],
  execution: [
    'reported_status',
    'execution_status',
    'observation_available',
    'execution_status_conflict',
    'execution_witness',
    'execution_resolved_contract',
    'execution_coverage',
  ],
  coverage: [
    'query_complete',
    'contract_count',
    'source_stale',
    'direct_coverage',
    'incomplete_coverage_reason',
    'missing_coverage_fact',
  ],
}
function factsFromTree(root: EvidenceNode) {
  const facts: Fact[] = []
  const seen = new Set<string>()
  let unresolved = false
  function visit(node: EvidenceNode) {
    if (node.kind === 'unresolved') unresolved = true
    const parts = node.label.split(' → ')
    if (parts.length >= 3) {
      const fact = {
        subject: parts[0]!,
        relationship: parts[1]!,
        object: parts.slice(2).join(' → '),
      }
      const key = JSON.stringify(fact)
      // Terminal outputs are already displayed as conclusion and sufficiency pills.
      if (
        !seen.has(key) &&
        !/_participation$|^currently_reported_execution$|_sufficiency$/.test(fact.relationship)
      ) {
        seen.add(key)
        facts.push(fact)
      }
    }
    node.children.forEach(visit)
  }
  visit(root)
  return { facts, unresolved }
}
function factValue(fact: Fact, aliases: Record<string, string>) {
  if (aliases[fact.object]) return aliases[fact.object]
  if (fact.object === 'true' || fact.object === 'false')
    return t(`involvement.boolean.${fact.object}`)
  if (/^\d{4}-\d{2}-\d{2}$/.test(fact.object)) return formatDate(fact.object)
  if (['signature_band', 'execution_status'].includes(fact.relationship))
    return t(`involvement.factValues.${fact.object}`, { defaultValue: fact.object })
  if (
    ['lookback_months', 'contract_count'].includes(fact.relationship) &&
    /^\d+$/.test(fact.object)
  )
    return formatNumber(Number(fact.object))
  // Original source status text and other source values are never translated.
  return fact.object
}
function NativeTree({ node, demo }: { node: EvidenceNode; demo: boolean }) {
  const text =
    demo && !node.label.startsWith('SYNTHETIC-') ? t(`involvement.${node.label}`) : node.label
  return (
    <li>
      {node.children.length ? (
        <details>
          <summary>{text}</summary>
          <ul>
            {node.children.map((child, index) => (
              <NativeTree key={`${child.id}-${index}`} node={child} demo={demo} />
            ))}
          </ul>
        </details>
      ) : (
        <span>{text}</span>
      )}
    </li>
  )
}

/** A deterministic, deduplicated view of the actual native supporting facts. */
export function InvolvementEvidence({
  decision,
  demo,
}: {
  decision: InvolvementDecision
  demo: boolean
}) {
  if (!decision.evidence_tree) return <p>{t('involvement.missingTree')}</p>
  const { facts, unresolved } = factsFromTree(decision.evidence_tree)
  const aliases = Object.fromEntries(
    [...new Set(decision.supporting_aliases ?? [])].map((alias, index) => [
      alias,
      decision.source_references?.[index]?.contract_id ?? alias,
    ]),
  )
  const grouped = Object.entries(groups)
    .map(([id, relationships]) => ({
      id,
      facts: facts.filter((f) => relationships.includes(f.relationship)),
    }))
    .filter((group) => group.facts.length)
  const known = new Set(Object.values(groups).flat())
  const other = facts.filter((f) => !known.has(f.relationship))
  if (other.length) grouped.push({ id: 'other', facts: other })
  return (
    <div className="involvement-evidence-explorer">
      <h4>{t('involvement.whyConclusion')}</h4>
      {unresolved && (
        <p className="notice warning">{t('involvement.native_evidence_incomplete')}</p>
      )}
      {demo ? (
        <ol className="involvement-proof-steps">
          {decision.evidence_tree.children.map((node) => (
            <li key={node.id}>
              <strong>{t(`involvement.${node.label}`)}</strong>
              <p className="small muted">{t('involvement.synthetic_source')}</p>
            </li>
          ))}
        </ol>
      ) : grouped.length > 0 ? (
        <ol className="involvement-proof-steps">
          {grouped.map((group) => (
            <li key={group.id}>
              <details open={group.id === 'identity'}>
                <summary>
                  <strong>{t(`involvement.evidenceGroups.${group.id}`)}</strong>
                  <span className="small muted">
                    {t('involvement.factCount', { count: group.facts.length })}
                  </span>
                </summary>
                <dl className="involvement-facts">
                  {group.facts.map((fact) => (
                    <div key={JSON.stringify(fact)}>
                      <dt>
                        {t(`involvement.factLabels.${fact.relationship}`, {
                          defaultValue: fact.relationship,
                        })}
                        {fact.subject !== 'evaluation' && (
                          <span className="small muted">
                            {' '}
                            · {aliases[fact.subject] ?? fact.subject}
                          </span>
                        )}
                      </dt>
                      <dd>{factValue(fact, aliases)}</dd>
                    </div>
                  ))}
                </dl>
              </details>
            </li>
          ))}
        </ol>
      ) : (
        <p>{t('involvement.nativeDetailsAvailable')}</p>
      )}
      <details className="involvement-native-details">
        <summary>{t('involvement.inspectNative')}</summary>
        <p className="small muted">{t('involvement.nativePreserved')}</p>
        <ul className="involvement-tree">
          <NativeTree node={decision.evidence_tree} demo={demo} />
        </ul>
      </details>
    </div>
  )
}
