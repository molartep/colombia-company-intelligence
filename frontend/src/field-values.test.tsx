import { render, screen } from '@testing-library/react'
import { RegistrationDate, TimestampValue } from './components/FieldValues'

it.each([
  ['20200115', 'Jan 15, 2020'],
  ['20240229', 'Feb 29, 2024'],
  ['2024-02-29', 'Feb 29, 2024'],
])('renders calendar date %s without a timezone day shift', (value, expected) => {
  render(<RegistrationDate value={value} />)
  expect(screen.getByText(expected)).toBeVisible()
})

it.each(['00000000', '99991231', '20250229', '20240431', '20241301', '2024-0229', 'not a date'])(
  'flags placeholder or invalid date %s instead of inventing a date',
  (value) => {
    render(<RegistrationDate value={value} />)
    expect(screen.getByText('Review')).toHaveClass('value-pill--review')
    expect(screen.getByText('Review')).toHaveAttribute('title', `Source value: ${value}`)
  },
)

it('distinguishes a missing date from a suspicious source value', () => {
  render(<RegistrationDate value={null} />)
  expect(screen.getByText('Missing')).toHaveClass('value-pill--missing')
  expect(screen.queryByText('Review')).not.toBeInTheDocument()
})

it.each(['1900-01-01T00:00:00Z', '1900-01-01T04:56:16Z', '1900-01-01T00:00:00-05:00'])(
  'recognizes RUES placeholder timestamp %s independently of display timezone',
  (value) => {
    render(<TimestampValue value={value} rues />)
    expect(screen.getByText('Review')).toHaveClass('value-pill--review')
  },
)

it.each([
  ['198705', 'May, 1987'],
  ['202612', 'Dec, 2026'],
  ['001', '001'],
  ['198713', '198713'],
  ['000001', '000001'],
  [null, 'No informada'],
])('formats only valid YYYYMM issuance values: %s', async (value, expected) => {
  const { issuanceMonth } = await import('./utils')
  expect(issuanceMonth(value)).toBe(expected)
})
