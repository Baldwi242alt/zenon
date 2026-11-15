// App-wide selection: which site, which month, the mission budget. Shared by every screen.
import { createContext, useContext, useState, type ReactNode } from 'react'

interface AppState {
  site: string; setSite: (s: string) => void
  month: number; setMonth: (m: number) => void          // 0-11, year 2027
  budget: number; setBudget: (b: number) => void
}
const Ctx = createContext<AppState | null>(null)

export function StoreProvider({ children }: { children: ReactNode }) {
  const [site, setSite] = useState('slater_plain')
  const [month, setMonth] = useState(5)                    // June: the month scores.json ranks
  const [budget, setBudget] = useState(0)                  // 0 = not entered yet; we never invent a price
  return <Ctx.Provider value={{ site, setSite, month, setMonth, budget, setBudget }}>{children}</Ctx.Provider>
}

export function useStore(): AppState {
  const s = useContext(Ctx)
  if (!s) throw new Error('useStore outside StoreProvider')
  return s
}
