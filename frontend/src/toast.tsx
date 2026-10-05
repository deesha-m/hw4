import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'

type Toast = { id: number; title: string; body?: string }
type ToastState = { notify: (title: string, body?: string) => void }

const ToastContext = createContext<ToastState | null>(null)

// Small pop-up confirmations (logged out, welcome back, college mode on). They slide in at
// the top, stay about 4 seconds, and can be dismissed. Screen readers announce them.
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)

  const dismiss = useCallback((id: number) => setToasts((list) => list.filter((t) => t.id !== id)), [])

  const notify = useCallback(
    (title: string, body?: string) => {
      const id = nextId.current++
      setToasts((list) => [...list.slice(-2), { id, title, body }])
      window.setTimeout(() => dismiss(id), 4200)
    },
    [dismiss],
  )

  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className="toast">
            <span className="toast-seal" aria-hidden="true">
              CC
            </span>
            <div>
              <strong>{toast.title}</strong>
              {toast.body && <p>{toast.body}</p>}
            </div>
            <button type="button" className="toast-close" onClick={() => dismiss(toast.id)} aria-label="Dismiss">
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastState {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used inside ToastProvider')
  return context
}
