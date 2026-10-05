import { createContext, useContext, useState, type ReactNode } from 'react'
import type { PageResults } from './api.ts'

type ChatResultsState = {
  // The latest search results the chat put on the page, or null to show the full catalogue.
  results: PageResults | null
  // Changes on every new result set, so the cards replay their entrance animation.
  version: number
  show: (results: PageResults) => void
  clear: () => void
}

const ChatResultsContext = createContext<ChatResultsState | null>(null)

// Shared between the chat widget (which receives results) and the Products page (which renders them).
export function ChatResultsProvider({ children }: { children: ReactNode }) {
  const [results, setResults] = useState<PageResults | null>(null)
  const [version, setVersion] = useState(0)

  const value: ChatResultsState = {
    results,
    version,
    show: (next) => {
      setResults(next)
      setVersion((v) => v + 1)
    },
    clear: () => setResults(null),
  }

  return <ChatResultsContext.Provider value={value}>{children}</ChatResultsContext.Provider>
}

export function useChatResults(): ChatResultsState {
  const context = useContext(ChatResultsContext)
  if (!context) throw new Error('useChatResults must be used inside ChatResultsProvider')
  return context
}
