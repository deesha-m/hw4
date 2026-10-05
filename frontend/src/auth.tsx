import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { fetchCurrentUser, logIn, logOut, register, type RegisterInput, type User } from './api.ts'

type AuthState = {
  user: User | null
  loading: boolean
  logIn: (email: string, password: string) => Promise<User>
  register: (input: RegisterInput) => Promise<User>
  logOut: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

// Keeps track of who is logged in. The session itself lives in an HttpOnly cookie
// the browser sends automatically, so no token is ever stored in JavaScript.
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchCurrentUser()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  const value: AuthState = {
    user,
    loading,
    logIn: async (email, password) => {
      const signedIn = await logIn(email, password)
      setUser(signedIn)
      return signedIn
    },
    register: async (input) => {
      const created = await register(input)
      setUser(created)
      return created
    },
    logOut: async () => {
      await logOut()
      setUser(null)
    },
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
