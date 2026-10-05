import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

// Yale's 14 residential colleges. Accent colors are this site's design choices for
// college mode, not official college colors.
export const COLLEGES: { name: string; accent: string }[] = [
  { name: 'Benjamin Franklin', accent: '#2f5d8c' },
  { name: 'Berkeley', accent: '#8c1d2f' },
  { name: 'Branford', accent: '#6b2737' },
  { name: 'Davenport', accent: '#1e5b3a' },
  { name: 'Ezra Stiles', accent: '#4b3f72' },
  { name: 'Grace Hopper', accent: '#1d6f75' },
  { name: 'Jonathan Edwards', accent: '#7b2d26' },
  { name: 'Morse', accent: '#8a6d1f' },
  { name: 'Pauli Murray', accent: '#5a3e85' },
  { name: 'Pierson', accent: '#a6761d' },
  { name: 'Saybrook', accent: '#2d3e6b' },
  { name: 'Silliman', accent: '#b04a2f' },
  { name: 'Timothy Dwight', accent: '#2f6b4f' },
  { name: 'Trumbull', accent: '#6e2233' },
]

const STORAGE_KEY = 'cc-college'
const DEFAULT_ACCENT = '#00356b' // Yale Blue

type CollegeState = {
  college: string | null
  setCollege: (name: string | null) => void
}

const CollegeContext = createContext<CollegeState | null>(null)

// College mode: the shopper picks their residential college, and the whole site takes on
// its accent color, shows its pieces first, and tells the chat assistant.
export function CollegeProvider({ children }: { children: ReactNode }) {
  const [college, setCollegeState] = useState<string | null>(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    return COLLEGES.some((c) => c.name === saved) ? saved : null
  })

  useEffect(() => {
    const accent = COLLEGES.find((c) => c.name === college)?.accent ?? DEFAULT_ACCENT
    document.documentElement.style.setProperty('--accent', accent)
    document.documentElement.dataset.college = college ?? ''
  }, [college])

  const setCollege = (name: string | null) => {
    setCollegeState(name)
    if (name) localStorage.setItem(STORAGE_KEY, name)
    else localStorage.removeItem(STORAGE_KEY)
  }

  return <CollegeContext.Provider value={{ college, setCollege }}>{children}</CollegeContext.Provider>
}

export function useCollege(): CollegeState {
  const context = useContext(CollegeContext)
  if (!context) throw new Error('useCollege must be used inside CollegeProvider')
  return context
}

// Products that belong to a college, matched by name (e.g. "Davenport College Crewneck").
export function isCollegeProduct(name: string, college: string | null): boolean {
  return !!college && name.toLowerCase().includes(college.toLowerCase())
}
