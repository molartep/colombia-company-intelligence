import { render, screen, within } from '@testing-library/react'
import { InvolvementEvidence } from './components/InvolvementEvidence'
import { changeLanguage } from './i18n'
import type { EvidenceNode, InvolvementDecision } from './types/governmentInvolvement'

beforeEach(async () => changeLanguage('en'))
const node = (label: string, id = label): EvidenceNode => ({
  id,
  label,
  kind: 'fact',
  children: [],
})
function decision(children: EvidenceNode[]): InvolvementDecision {
  return {
    id: 'direct_participation',
    outcome: 'documented',
    evidence_status: 'sufficient',
    supporting_aliases: ['contract_1'],
    supporting_contract_ids: ['CO1.PCCNTR.123'],
    supporting_evidence_ids: [],
    evidence_tree_id: 'root',
    warnings: [],
    source_references: [
      {
        contract_id: 'CO1.PCCNTR.123',
        evidence_id: 'source',
        source_url: 'https://example.com',
        observed_at: '2026-11-26',
      },
    ],
    evidence_tree: {
      id: 'root',
      kind: 'decision',
      label: 'evaluation → direct_participation → documented',
      children,
    },
  }
}
test('compact evidence deduplicates repeated facts while retaining conflicting values and raw status', () => {
  const { container } = render(
    <InvolvementEvidence
      demo={false}
      decision={decision([
        node('contract_1 → attribution_verified → true'),
        node('contract_1 → attribution_verified → true', 'repeat'),
        node('contract_1 → attribution_verified → false'),
        node('contract_1 → reported_status → En ejecución'),
      ])}
    />,
  )
  const facts = container.querySelector('.involvement-proof-steps') as HTMLElement
  expect(facts.querySelectorAll('dl > div')).toHaveLength(3)
  expect(within(facts).getByText('Yes')).toBeInTheDocument()
  expect(within(facts).getByText('No')).toBeInTheDocument()
  expect(within(facts).getByText('En ejecución')).toBeInTheDocument()
  expect(within(facts).getAllByText(/CO1.PCCNTR.123/)).toHaveLength(3)
  expect(container.querySelector('.involvement-native-details')).not.toHaveAttribute('open')
})
test('unresolved native evidence is explicit and original reasoning remains available', () => {
  render(
    <InvolvementEvidence
      demo={false}
      decision={decision([{ ...node('Unresolved reference'), kind: 'unresolved' }])}
    />,
  )
  expect(screen.getByText(/native evidence tree contains an unresolved branch/)).toBeInTheDocument()
  expect(screen.getByText('Unresolved reference')).toBeInTheDocument()
  expect(screen.getByText('Inspect original reasoning')).toBeInTheDocument()
})
