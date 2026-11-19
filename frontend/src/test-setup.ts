import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach } from 'vitest'
import i18n from './i18n'
beforeEach(async () => {
  localStorage.clear()
  await i18n.changeLanguage('en')
})
afterEach(cleanup)

// JSDOM lacks native dialog behavior. Mirror open/close so UI lifecycle assertions remain meaningful.
HTMLDialogElement.prototype.showModal = function () {
  this.setAttribute('open', '')
}
HTMLDialogElement.prototype.close = function () {
  this.removeAttribute('open')
}
