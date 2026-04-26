const KEY = 'giggle_auth'

export function getAuth() {
  try { return JSON.parse(localStorage.getItem(KEY) || 'null') } catch { return null }
}
export function setAuth(data) { localStorage.setItem(KEY, JSON.stringify(data)) }
export function clearAuth() { localStorage.removeItem(KEY) }
export function isAdmin() { return localStorage.getItem('giggle_admin') === '1' }
export function setAdmin() { localStorage.setItem('giggle_admin', '1') }
export function clearAdmin() { localStorage.removeItem('giggle_admin') }
