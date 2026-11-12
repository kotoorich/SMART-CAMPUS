import { useEffect, useRef, useState } from "react"
import { eventStreamUrl } from "../services/api"
import { getToken } from "../utils/session"

// EventSource cannot attach an Authorization header, so the backend accepts
// the short-lived access token as a query parameter. Decode only the exp claim
// client-side to avoid retrying a token that is already expired; the backend
// remains responsible for cryptographic validation.
function tokenIsExpired(token) {
  try {
    const part = token.split(".")[1]
    if (!part) return true
    const normalized = part.replace(/-/g, "+").replace(/_/g, "/")
    const payload = JSON.parse(atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=")))
    return !payload.exp || Number(payload.exp) * 1000 <= Date.now()
  } catch {
    return true
  }
}

export function useRealtime(onEvent, deps = []) {
  const [status, setStatus] = useState("connecting")
  const [lastEvent, setLastEvent] = useState(null)
  const token = getToken()
  const handlerRef = useRef(onEvent)
  handlerRef.current = onEvent

  useEffect(() => {
    if (!token) {
      setStatus("offline")
      return undefined
    }

    let source
    let retryTimer
    let closed = false
    let attempts = 0

    const stopForAuth = () => {
      closed = true
      clearTimeout(retryTimer)
      source?.close()
      setStatus("offline")
      window.dispatchEvent(new CustomEvent("smart-campus:unauthorized"))
    }

    const connect = () => {
      if (closed) return
      if (tokenIsExpired(token)) {
        stopForAuth()
        return
      }
      try {
        const url = eventStreamUrl(token)
        if (!url) { setStatus("offline"); return }
        source = new EventSource(url)
      } catch {
        setStatus("offline")
        return
      }
      source.onopen = () => { attempts = 0; setStatus("live") }
      source.onerror = () => {
        source?.close()
        if (closed) return
        if (tokenIsExpired(token)) {
          stopForAuth()
          return
        }
        setStatus("offline")
        attempts += 1
        // EventSource hides HTTP status codes. Bound retries so a server-side
        // token/secret mismatch cannot create an endless stream of 401s.
        if (attempts > 5) return
        retryTimer = setTimeout(connect, Math.min(5000 * attempts, 20000))
      }
      source.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)
          setLastEvent(payload)
          handlerRef.current?.(payload)
        } catch { /* ignore malformed frames */ }
      }
    }

    const handleUnauthorized = () => {
      closed = true
      clearTimeout(retryTimer)
      source?.close()
      setStatus("offline")
    }
    window.addEventListener("smart-campus:unauthorized", handleUnauthorized)
    connect()
    return () => {
      closed = true
      clearTimeout(retryTimer)
      source?.close()
      window.removeEventListener("smart-campus:unauthorized", handleUnauthorized)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, ...deps])

  return { status, lastEvent }
}
