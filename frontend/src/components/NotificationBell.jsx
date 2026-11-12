import { useEffect, useState } from "react"
import { Bell, CheckCheck } from "lucide-react"
import { getNotifications, markAllNotificationsRead, markNotificationRead } from "../services/api"
import { useRealtime } from "../hooks/useRealtime"

export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [unread, setUnread] = useState(0)

  const load = async () => {
    try {
      const data = await getNotifications()
      setItems(data.items || [])
      setUnread(data.unread || 0)
    } catch { /* silent — the bell is non-critical */ }
  }

  useEffect(() => {
    // Deferred so the fetch resolves after mount rather than during the
    // synchronous effect body (avoids cascading renders flagged by the linter).
    const timer = setTimeout(load, 0)
    return () => clearTimeout(timer)
  }, [])

  useRealtime((event) => {
    if (event.type === "notification" || event.type === "notification_read") load()
  })

  const readAll = async () => {
    await markAllNotificationsRead()
    load()
  }

  const readOne = async (id) => {
    await markNotificationRead(id)
    load()
  }

  return (
    <div className="sc-bell-wrap">
      <button className="sc-bell" onClick={() => setOpen((v) => !v)} aria-label="Notifications" aria-expanded={open}>
        <Bell size={17} />
        {unread > 0 && <span className="sc-bell-count">{unread > 9 ? "9+" : unread}</span>}
      </button>
      {open && (
        <>
          <div className="sc-bell-backdrop" onClick={() => setOpen(false)} />
          <div className="sc-bell-panel" role="dialog" aria-label="Notifications">
            <div className="sc-bell-head">
              <strong>Notifications</strong>
              {unread > 0 && <button onClick={readAll}><CheckCheck size={14} /> Mark all read</button>}
            </div>
            <div className="sc-bell-list">
              {items.length === 0 && <p className="sc-bell-empty">You have no notifications yet.</p>}
              {items.map((n) => (
                <button key={n.id} className={`sc-bell-item ${n.is_read ? "" : "unread"}`} onClick={() => readOne(n.id)}>
                  <span className="sc-bell-item-title">{n.title}</span>
                  {n.body && <span className="sc-bell-item-body">{n.body}</span>}
                  <span className="sc-bell-item-time">{new Date(n.created_at).toLocaleString()}</span>
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
