import React from 'react'
import ReactDOM from 'react-dom/client'
import i18n from 'i18next'
import { initReactI18next } from '../node_modules/react-i18next'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'
import en from './locales/en.json'
import ta from './locales/ta.json'
import hi from './locales/hi.json'
import { getAuth } from './hooks/useAuth'

const auth = getAuth()
const defaultLang = auth?.language_preference || 'ta'

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ta: { translation: ta },
    hi: { translation: hi },
  },
  lng: defaultLang,
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <App />
  </BrowserRouter>
)
