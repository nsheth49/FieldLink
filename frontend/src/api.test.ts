import { describe, expect, it } from 'vitest'
import { money, title, utc } from './api'
describe('operator-facing units and clocks',()=>{
 it('shows historical scenario time explicitly in UTC',()=>expect(utc(0)).toBe('1970-01-01 00:00 UTC'))
 it('keeps negative savings visible',()=>expect(money(-250)).toBe('-$250'))
 it('formats machine states as readable labels',()=>expect(title('SIMULATED_DISPATCHED')).toBe('SIMULATED DISPATCHED'))
})
