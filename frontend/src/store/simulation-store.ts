import { create } from 'zustand'
import type { SimulatedRecommendation } from '@/types/recommendation'

interface SimulationStore {
    // State
    simulatedItems: SimulatedRecommendation[]

    // Computed
    totalSavings: number

    // Actions
    toggleSimulation: (rec: SimulatedRecommendation) => void
    removeSimulation: (id: string) => void
    resetSimulation: () => void
    isSimulated: (id: string) => boolean
}

export const useSimulationStore = create<SimulationStore>((set, get) => ({
    simulatedItems: [],

    get totalSavings() {
        return get().simulatedItems.reduce((sum, item) => sum + item.savingsPerMonth, 0)
    },

    toggleSimulation: (rec: SimulatedRecommendation) => {
        const { simulatedItems } = get()
        const exists = simulatedItems.some(item => item.id === rec.id)

        if (exists) {
            set({
                simulatedItems: simulatedItems.filter(item => item.id !== rec.id)
            })
        } else {
            set({
                simulatedItems: [...simulatedItems, rec]
            })
        }
    },

    removeSimulation: (id: string) => {
        set({
            simulatedItems: get().simulatedItems.filter(item => item.id !== id)
        })
    },

    resetSimulation: () => {
        set({ simulatedItems: [] })
    },

    isSimulated: (id: string) => {
        return get().simulatedItems.some(item => item.id === id)
    }
}))
