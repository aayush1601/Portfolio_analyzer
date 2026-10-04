import { createContext, useMemo } from 'react'
import type { Reference } from './api'

export type PlateInfo = { name?: string; sector?: string; effective?: number }
export const PlateContext = createContext<Record<string, PlateInfo>>({})

/** Name, sector and effective exposure per symbol (and name/category per fund), for <Plate>. */
export function usePlates(reference: Reference | null, effective: Record<string, number>) {
  return useMemo(() => {
    const m: Record<string, PlateInfo> = {}
    reference?.stocks.forEach((s) => (m[s.symbol] = { name: s.name, sector: s.sector, effective: effective[s.symbol] }))
    reference?.funds.forEach((f) => (m[f.scheme_code] = { name: f.name, sector: f.category }))
    return m
  }, [reference, effective])
}
