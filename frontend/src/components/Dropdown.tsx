import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { CSSProperties, KeyboardEvent } from 'react'

export interface DropdownOption {
  value: string
  label: string
  disabled?: boolean
}

/** Select-only combobox. Focus stays on the trigger while the listbox is open. */
export function Dropdown({
  value,
  onChange,
  options: suppliedOptions,
  id,
  className = '',
  disabled = false,
  editable = false,
  maxLength,
  'aria-label': label,
}: {
  value: string
  onChange: (value: string) => void
  options: readonly DropdownOption[]
  id?: string
  className?: string
  disabled?: boolean
  'aria-label': string
  editable?: boolean
  maxLength?: number
}) {
  const options =
    editable && value
      ? suppliedOptions.filter((option) =>
          option.label.toLocaleLowerCase().includes(value.toLocaleLowerCase()),
        )
      : suppliedOptions
  const generated = useId()
  const popupId = `${generated}-options`
  const trigger = useRef<HTMLButtonElement | HTMLInputElement>(null)
  const popup = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [position, setPosition] = useState<CSSProperties>({
    position: 'fixed',
    visibility: 'hidden',
  })
  const search = useRef({ text: '', time: 0 })
  const selected = options.findIndex((option) => option.value === value)
  const visible = open && !disabled && options.length > 0
  const activeIndex = options[active] && !options[active].disabled ? active : Math.max(0, selected)
  const show = (fallback = 0) => {
    search.current = { text: '', time: 0 }
    setActive(selected >= 0 ? selected : fallback)
    setOpen(true)
  }
  const choose = (index: number) => {
    const option = options[index]
    if (!option || option.disabled) return
    setOpen(false)
    onChange(option.value)
    trigger.current?.focus()
  }
  useLayoutEffect(() => {
    if (!visible) return
    const place = () => {
      const button = trigger.current
      if (!button) return
      const rect = button.getBoundingClientRect()
      const below = window.innerHeight - rect.bottom - 12
      const above = rect.top - 12
      const up = below < Math.min(240, options.length * 44 + 8) && above > below
      const width = Math.min(Math.max(rect.width, 160), window.innerWidth - 16)
      setPosition({
        position: 'fixed',
        visibility: 'visible',
        width,
        left: Math.max(8, Math.min(rect.left, window.innerWidth - width - 8)),
        maxHeight: Math.max(44, Math.min(320, up ? above : below)),
        ...(up ? { bottom: window.innerHeight - rect.top + 4 } : { top: rect.bottom + 4 }),
      })
    }
    place()
    const resize = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(place)
    if (trigger.current) resize?.observe(trigger.current)
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    return () => {
      resize?.disconnect()
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
    }
  }, [visible, options.length])
  useLayoutEffect(() => {
    const item = document.getElementById(`${popupId}-${activeIndex}`)
    const list = popup.current
    if (!visible || !item || !list) return
    if (item.offsetTop < list.scrollTop) list.scrollTop = item.offsetTop
    else if (item.offsetTop + item.offsetHeight > list.scrollTop + list.clientHeight)
      list.scrollTop = item.offsetTop + item.offsetHeight - list.clientHeight
  }, [visible, activeIndex, popupId])
  useEffect(() => {
    if (!visible) return
    const outside = (event: PointerEvent) => {
      if (
        !trigger.current?.contains(event.target as Node) &&
        !popup.current?.contains(event.target as Node)
      )
        setOpen(false)
    }
    document.addEventListener('pointerdown', outside)
    return () => document.removeEventListener('pointerdown', outside)
  }, [visible])
  const keyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (
      ['ArrowDown', 'ArrowUp'].includes(event.key) ||
      (!editable && ['Home', 'End'].includes(event.key))
    ) {
      event.preventDefault()
      if (!visible) {
        const fallback = event.key === 'End' || event.key === 'ArrowUp' ? options.length - 1 : 0
        setActive(
          event.key === 'Home' || event.key === 'End'
            ? fallback
            : selected >= 0
              ? selected
              : fallback,
        )
        setOpen(true)
        return
      }
      const step = event.key === 'ArrowUp' || event.key === 'End' ? -1 : 1
      let next =
        event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1 : activeIndex + step
      while (next >= 0 && next < options.length && options[next]?.disabled) next += step
      if (next >= 0 && next < options.length) setActive(next)
    } else if (event.key === 'Enter' || (event.key === ' ' && !editable)) {
      event.preventDefault()
      if (visible) choose(activeIndex)
      else show()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      setOpen(false)
    } else if (event.key === 'Tab') {
      setOpen(false)
    } else if (
      !editable &&
      event.key.length === 1 &&
      !event.altKey &&
      !event.ctrlKey &&
      !event.metaKey
    ) {
      event.preventDefault()
      const now = Date.now()
      const text = now - search.current.time < 700 ? search.current.text + event.key : event.key
      search.current = { text, time: now }
      const normalize = (s: string) => s.normalize('NFD').replace(/\p{M}/gu, '').toLocaleLowerCase()
      const query = normalize(text)
      const repeat = [...query].every((character) => character === query.charAt(0))
      const prefix = repeat ? query.charAt(0) : query
      const start = visible ? activeIndex + 1 : Math.max(0, selected + 1)
      const match = options
        .map((_, i) => (start + i) % options.length)
        .find((i) => !options[i]?.disabled && normalize(options[i]?.label ?? '').startsWith(prefix))
      if (match !== undefined) {
        setActive(match)
        setOpen(true)
      }
    }
  }
  return (
    <>
      {editable ? (
        <input
          type="text"
          className={`dropdown-trigger ${className}`}
          id={id}
          ref={(element) => {
            trigger.current = element
          }}
          role="combobox"
          aria-label={label}
          aria-autocomplete="list"
          aria-expanded={visible}
          aria-controls={popupId}
          aria-activedescendant={
            visible && options[activeIndex] ? `${popupId}-${activeIndex}` : undefined
          }
          value={value}
          maxLength={maxLength}
          disabled={disabled}
          onKeyDown={keyDown}
          onChange={(event) => {
            onChange(event.target.value)
            setActive(0)
            setOpen(true)
          }}
          onFocus={() => show()}
          onBlur={() => setOpen(false)}
        />
      ) : (
        <button
          type="button"
          className={`dropdown-trigger ${className}`}
          id={id}
          ref={(element) => {
            trigger.current = element
          }}
          role="combobox"
          aria-label={label}
          aria-describedby={`${generated}-value`}
          title={options[selected]?.label ?? value}
          aria-haspopup="listbox"
          aria-expanded={visible}
          aria-controls={popupId}
          aria-activedescendant={visible ? `${popupId}-${activeIndex}` : undefined}
          value={value}
          disabled={disabled}
          onKeyDown={keyDown}
          onClick={() => (visible ? setOpen(false) : show())}
          onBlur={() => setOpen(false)}
        >
          <span id={`${generated}-value`}>{options[selected]?.label ?? value}</span>
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
      )}
      {visible &&
        options.length > 0 &&
        createPortal(
          <div
            ref={popup}
            id={popupId}
            role="listbox"
            aria-label={label}
            className="dropdown-panel"
            style={position}
          >
            {options.map((option, index) => (
              <button
                key={option.value}
                id={`${popupId}-${index}`}
                role="option"
                type="button"
                tabIndex={-1}
                value={option.value}
                aria-selected={option.value === value}
                aria-disabled={option.disabled || undefined}
                className="dropdown-option"
                data-active={index === activeIndex || undefined}
                onPointerDown={(event) => event.preventDefault()}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => choose(index)}
              >
                <span>{option.label}</span>
                <span aria-hidden="true">{option.value === value ? '✓' : ''}</span>
              </button>
            ))}
          </div>,
          document.body,
        )}
    </>
  )
}
