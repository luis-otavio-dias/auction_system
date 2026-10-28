import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { fetchMe, login as loginRequest, logout as logoutRequest, register as registerRequest } from '../api/auth'
import { AuthContext } from './auth-context'
import type { AuthContextValue, RegisterInput } from './auth-context'
import type { User } from '../types/api'

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refreshUser = useCallback(async () => {
    const nextUser = await fetchMe()
    setUser(nextUser)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      try {
        const nextUser = await fetchMe(controller.signal)
        setUser(nextUser)
      } catch {
        setUser(null)
      } finally {
        setLoading(false)
      }
    }
    void load()
    const handleExpired = () => {
      setUser(null)
    }
    window.addEventListener('auth:expired', handleExpired)
    return () => {
      controller.abort()
      window.removeEventListener('auth:expired', handleExpired)
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    await loginRequest(email, password)
    const nextUser = await fetchMe()
    setUser(nextUser)
  }, [])

  const register = useCallback(async (input: RegisterInput) => {
    await registerRequest(input)
    await loginRequest(input.email, input.password)
    const nextUser = await fetchMe()
    setUser(nextUser)
  }, [])

  const logout = useCallback(async () => {
    try {
      await logoutRequest()
    } finally {
      setUser(null)
    }
  }, [])

  const value = useMemo<AuthContextValue>(() => ({
    user,
    loading,
    login,
    register,
    logout,
    refreshUser,
  }), [user, loading, login, register, logout, refreshUser])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
