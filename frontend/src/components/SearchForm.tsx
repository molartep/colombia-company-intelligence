import { useEffect, useRef, useState } from 'react'

export function SearchForm({
  initial = '',
  onSearch,
}: {
  initial?: string
  onSearch: (value: string) => void
}) {
  const [value, setValue] = useState(initial)
  const callback = useRef(onSearch)
  const previous = useRef(initial)
  useEffect(() => {
    callback.current = onSearch
  }, [onSearch])
  useEffect(() => {
    if (initial !== previous.current) {
      previous.current = initial
      // Synchronize browser back/forward navigation without remounting the focused input.
      setValue(initial)
    }
  }, [initial])
  useEffect(() => {
    const timer = setTimeout(() => {
      if (value.trim().length >= 2 && value.trim() !== previous.current) {
        previous.current = value.trim()
        callback.current(value.trim())
      }
    }, 500)
    return () => clearTimeout(timer)
  }, [value])
  return (
    <form
      className="search-form"
      onSubmit={(event) => {
        event.preventDefault()
        if (value.trim().length >= 2) {
          previous.current = value.trim()
          onSearch(value.trim())
        }
      }}
    >
      <label htmlFor="company-search">Company name or NIT</label>
      <div className="search-control">
        <span aria-hidden="true">⌕</span>
        <input
          id="company-search"
          name="q"
          type="search"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Enter a legal name or NIT"
          minLength={2}
          maxLength={160}
          autoComplete="off"
          required
        />
        <button type="submit">
          Search <span aria-hidden="true">↗</span>
        </button>
      </div>
      <p className="text-sm text-slate-500 mt-3">
        Use the registered legal name, or a NIT with an optional verification digit.
      </p>
    </form>
  )
}
