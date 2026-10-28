import { createContext, useContext } from 'react'
import type { User } from '../types/api'

export interface RegisterInput {
  email: string
  password: string
  role: 'BIDDER' | 'SELLER'
  public_alias: string
}

export interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (input: RegisterInput) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (context === null) {
    throw new Error('useAuth precisa estar dentro de AuthProvider.')
  }
  return context
}
