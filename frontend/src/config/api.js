import axios from 'axios'

export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
export const ADMIN_KEY = 'gigshield-admin-2026'

export const api = axios.create({
  baseURL: API_BASE,
  headers: { 'X-Admin-Key': ADMIN_KEY },
  timeout: 10000,
})
