import { useLayoutEffect, useRef } from 'react'

/** Fit the exact, unabridged metric on one line without rounding its value. */
export function FitMetricValue({ value }: { value: string }) {
  const container = useRef<HTMLElement>(null)
  const text = useRef<HTMLSpanElement>(null)
  useLayoutEffect(() => {
    const outer = container.current
    const inner = text.current
    if (!outer || !inner) return
    let disposed = false
    const fit = () => {
      if (disposed || !outer.clientWidth) return
      const maximum = parseFloat(getComputedStyle(outer).fontSize)
      inner.style.fontSize = `${maximum}px`
      const width = inner.getBoundingClientRect().width
      if (width > outer.clientWidth) {
        inner.style.fontSize = `${Math.max(1, (maximum * (outer.clientWidth - 1)) / width)}px`
      }
    }
    fit()
    const observer = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(fit)
    observer?.observe(outer)
    window.addEventListener('resize', fit)
    void document.fonts?.ready.then(fit)
    return () => {
      disposed = true
      observer?.disconnect()
      window.removeEventListener('resize', fit)
    }
  }, [value])
  return (
    <strong className="fit-metric-value" ref={container} title={value}>
      <span ref={text}>{value}</span>
    </strong>
  )
}
