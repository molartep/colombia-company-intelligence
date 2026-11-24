import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { vi } from 'vitest'
import { Dropdown } from './components/Dropdown'

const options = [
  { value: '', label: 'All' },
  { value: 'Ábaco', label: 'ÁBACO' },
  { value: 'blocked', label: 'Blocked', disabled: true },
  { value: 'Beta Original', label: 'BETA' },
  { value: 'Zero', label: 'ZETA' },
]
function Example({ disabled = false }: { disabled?: boolean }) {
  const [value, setValue] = useState('')
  return (
    <>
      <Dropdown
        aria-label="Filter"
        value={value}
        onChange={setValue}
        options={options}
        disabled={disabled}
      />
      <button>After</button>
      <output data-testid="raw">{value}</output>
    </>
  )
}

test('custom combobox navigation skips disabled choices and commits only on Enter', async () => {
  const user = userEvent.setup()
  render(<Example />)
  const trigger = screen.getByRole('combobox', { name: 'Filter' })
  trigger.focus()
  await user.keyboard('{ArrowDown}{ArrowDown}{ArrowDown}')
  expect(trigger).toHaveFocus()
  expect(screen.getByTestId('raw')).toBeEmptyDOMElement()
  const current = document.getElementById(trigger.getAttribute('aria-activedescendant')!)
  expect(current).toHaveTextContent('BETA')
  await user.keyboard('{Enter}')
  expect(trigger).toHaveValue('Beta Original')
  expect(screen.getByTestId('raw')).toHaveTextContent('Beta Original')
  expect(trigger).toHaveFocus()
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
})

test('Home/End, accented type-ahead, Escape, Tab and outside clicks preserve selection semantics', async () => {
  const user = userEvent.setup()
  render(<Example />)
  const trigger = screen.getByRole('combobox')
  trigger.focus()
  await user.keyboard('{End}{Enter}')
  expect(trigger).toHaveValue('Zero')
  await user.keyboard('{Home}{Enter}')
  expect(trigger).toHaveValue('')
  await user.keyboard('a')
  expect(document.getElementById(trigger.getAttribute('aria-activedescendant')!)).toHaveTextContent(
    'ÁBACO',
  )
  await user.keyboard('{Escape}')
  expect(trigger).toHaveValue('')
  await user.click(trigger)
  await user.tab()
  expect(screen.getByRole('button', { name: 'After' })).toHaveFocus()
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  await user.click(trigger)
  await user.click(screen.getByText('After'))
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
})

test('Unicode/raw values survive pointer selection and listboxes are portaled beyond clipping parents', async () => {
  const user = userEvent.setup()
  const { container } = render(
    <div style={{ overflow: 'hidden' }}>
      <Example />
    </div>,
  )
  const trigger = screen.getByRole('combobox')
  await user.click(trigger)
  const popup = screen.getByRole('listbox', { name: 'Filter' })
  expect(container.contains(popup)).toBe(false)
  expect(popup).toHaveStyle({ position: 'fixed' })
  await user.click(within(popup).getByRole('option', { name: 'ÁBACO' }))
  expect(trigger).toHaveValue('Ábaco')
  expect(trigger).toHaveFocus()
  await user.click(trigger)
  expect(screen.getByRole('option', { name: 'ÁBACO' })).toHaveAttribute('aria-selected', 'true')
})

test('disabled selectors cannot open or change a value', async () => {
  render(<Example disabled />)
  await userEvent.click(screen.getByRole('combobox'))
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
})

test('editable suggestions retain arbitrary input and choose the exact external value', async () => {
  const change = vi.fn()
  function Editable() {
    const [value, setValue] = useState('')
    return (
      <Dropdown
        aria-label="Buyer"
        editable
        value={value}
        onChange={(value) => {
          change(value)
          setValue(value)
        }}
        options={options}
      />
    )
  }
  render(<Editable />)
  const input = screen.getByRole('combobox')
  await userEvent.type(input, 'BE')
  expect(screen.getAllByRole('option')).toHaveLength(1)
  await userEvent.click(screen.getByRole('option', { name: 'BETA' }))
  expect(change).toHaveBeenLastCalledWith('Beta Original')
  expect(input).toHaveValue('Beta Original')
  await userEvent.clear(input)
  await userEvent.type(input, 'unlisted buyer')
  expect(input).toHaveValue('unlisted buyer')
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
})
