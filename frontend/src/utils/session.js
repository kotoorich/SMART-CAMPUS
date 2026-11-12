// Authentication is stored per tab so multiple roles can be tested in
// separate tabs without overwriting one another.
// Versioned keys intentionally invalidate sessions created by older frontend
// builds. This prevents a stale access token from being replayed after upgrade.
const TOKEN_KEY = "smart_campus_access_token_v3"
const USER_KEY = "smart_campus_user_v3"
const LEGACY_KEYS = ["token", "user", "access_token", "smart-campus-token"]

try {
  for (const key of LEGACY_KEYS) sessionStorage.removeItem(key)
} catch { /* storage may be unavailable */ }

function isTokenExpired(token) {
  try {
    const part = token?.split(".")[1]
    if (!part) return true
    const normalized = part.replace(/-/g, "+").replace(/_/g, "/")
    const payload = JSON.parse(atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=")))
    // Treat tokens expiring within the next 30 seconds as expired to avoid
    // opening an SSE connection just as the server rejects it.
    return !payload.exp || Number(payload.exp) * 1000 <= Date.now() + 30_000
  } catch {
    return true
  }
}

export const clearAuth = () => {
  try {
    sessionStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(USER_KEY)
  } catch { /* storage may be unavailable */ }
}

export const getToken = () => {
  try {
    const token = sessionStorage.getItem(TOKEN_KEY)
    if (token && isTokenExpired(token)) {
      clearAuth()
      return null
    }
    return token
  } catch { return null }
}

export const getStoredUser = () => {
  // Never restore a protected user profile without a valid access token.
  if (!getToken()) return null
  try {
    const raw = sessionStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    clearAuth()
    return null
  }
}

export const setAuth = (token, user) => {
  try {
    if (!token || isTokenExpired(token)) {
      clearAuth()
      return
    }
    sessionStorage.setItem(TOKEN_KEY, token)
    sessionStorage.setItem(USER_KEY, JSON.stringify(user))
  } catch { /* storage may be unavailable */ }
}
