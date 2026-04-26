export function toIST(dt) {
  if (!dt) return null
  const date = new Date(dt)
  // If no timezone in string, assume it's UTC from backend
  const utcDate = dt.toString().includes('Z') || dt.toString().includes('+') ? date : new Date(dt + 'Z')
  return utcDate
}

export function ago(dt) {
  const utcDate = toIST(dt)
  if (!utcDate) return '—'
  
  const s = Math.floor((Date.now() - utcDate) / 1000)
  if (s < 0) return 'Just now'
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  
  return utcDate.toLocaleDateString('en-IN', { 
    day: 'numeric', 
    month: 'short', 
    timeZone: 'Asia/Kolkata' 
  })
}

export function formatIST(dt, options = { day: '2-digit', month: 'short' }) {
  const utcDate = toIST(dt)
  if (!utcDate) return '—'
  return utcDate.toLocaleDateString('en-IN', { ...options, timeZone: 'Asia/Kolkata' })
}
