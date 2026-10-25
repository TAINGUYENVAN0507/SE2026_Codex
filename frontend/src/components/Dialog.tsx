import {
  useEffect,
  useRef,
  type PropsWithChildren,
  type RefObject,
} from 'react'

const focusable =
  'button:not([disabled]),input:not([disabled]),textarea:not([disabled]),select:not([disabled]),a[href],[tabindex="0"]'

export function Dialog({
  title,
  onClose,
  children,
  returnFocusRef,
}: PropsWithChildren<{
  title: string
  onClose: () => void
  returnFocusRef?: RefObject<HTMLElement | null>
}>) {
  const panel = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const previous =
      returnFocusRef?.current ??
      (document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null)
    const first = panel.current?.querySelector<HTMLElement>(focusable)
    ;(first ?? panel.current)?.focus()
    return () => {
      if (previous?.isConnected) previous.focus()
    }
  }, [returnFocusRef])
  return (
    <div
      className="dialog-backdrop"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        ref={panel}
        className="app-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            event.preventDefault()
            event.stopPropagation()
            onClose()
            return
          }
          if (event.key !== 'Tab') return
          const elements = [
            ...(panel.current?.querySelectorAll<HTMLElement>(focusable) ?? []),
          ]
          const first = elements[0]
          const last = elements.at(-1)
          if (!first) {
            event.preventDefault()
            panel.current?.focus()
          } else if (
            event.shiftKey &&
            (document.activeElement === first ||
              document.activeElement === panel.current)
          ) {
            event.preventDefault()
            last?.focus()
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault()
            first.focus()
          }
        }}
      >
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  )
}
