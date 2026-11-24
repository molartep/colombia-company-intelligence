import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

export async function openDropdown(control: HTMLElement) {
  if (control.getAttribute('aria-expanded') !== 'true') await userEvent.click(control)
  return screen.getByRole('listbox', { name: control.getAttribute('aria-label')! })
}
export async function chooseOption(control: HTMLElement, value: string) {
  const popup = await openDropdown(control)
  const option = within(popup)
    .getAllByRole('option')
    .find((node) => node.getAttribute('value') === value)
  if (!option) throw new Error(`Dropdown option not found: ${value}`)
  await userEvent.click(option)
}
