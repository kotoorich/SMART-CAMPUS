import { createContext, useContext, useEffect, useState } from "react"
import { getToken, getStoredUser, setAuth, clearAuth } from "../utils/session"

// This module intentionally exports both the provider component and the
// useAuth hook, so fast-refresh's component-only rule does not apply here.
/* eslint-disable react-refresh/only-export-components */

const AuthContext = createContext()

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => getStoredUser())

  // Token stored separately (per-tab) so api.js can always read it.
  const [token, setToken] = useState(() => getToken())

  const login = (userData) => {
    // userData from /login response: { access_token, role, id, name }
    const { access_token, ...userInfo } = userData
    setUser(userInfo)
    setToken(access_token)
    setAuth(access_token, userInfo)
  }

  const updateUser = (updates) => {
    setUser(current => {
      const merged = { ...(current || {}), ...updates }
      if (token) setAuth(token, merged)
      return merged
    })
  }

  const logout = () => {
    setUser(null)
    setToken(null)
    clearAuth()
  }

  useEffect(() => {
    const handleUnauthorized = () => logout()
    window.addEventListener("smart-campus:unauthorized", handleUnauthorized)
    return () => window.removeEventListener("smart-campus:unauthorized", handleUnauthorized)
  }, [])

  return (
    <AuthContext.Provider value={{ user, token, login, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}