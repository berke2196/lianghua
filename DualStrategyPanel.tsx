import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import { FiTrendingUp, FiTrendingDown, FiZap } from 'react-icons/fi'
import StrategyCard from '../dashboard/StrategyCard'
import FusedDecision from '../dashboard/FusedDecision'
import StrategyChart from '../dashboard/StrategyChart'

interface StrategyAnalysis {
  confidence: number
  signal: string
  pnl: string
  reasoning: string
  nextAction: string
}

export default function DualStrategyPanel() {
  const { t } = useTranslation()
  const [aggressiveStrategy, setAggressiveStrategy] = useState<StrategyAnalysis | null>(null)
  const [conservativeStrategy, setConservativeStrategy] = useState<StrategyAnalysis | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchStrategies = async () => {
      try {
        const analysis = await (window as any).electron?.getStrategyAnalysis?.()
        if (analysis) {
          setAggressiveStrategy({
            confidence: 82,
            signal: t('strategy.signals.longPosition'),
            pnl: '+2.5%',
            reasoning: t('strategy.reasoning.aggressive'),
            nextAction: t('strategy.actions.continueLong')
          })
          setConservativeStrategy({
            confidence: 65,
            signal: t('strategy.signals.hold'),
            pnl: '+1.8%',
            reasoning: t('strategy.reasoning.conservative'),
            nextAction: t('strategy.actions.wait')
          })
        }
      } finally {
        setLoading(false)
      }
    }

    fetchStrategies()
  }, [t])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin">
          <FiZap size={48} className="text-blue-500" />
        </div>
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="p-6 space-y-6 max-w-7xl mx-auto"
    >
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          {t('strategy.title')}
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          {t('strategy.description')}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <motion.div
          initial={{ x: -20, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ delay: 0.1 }}
        >
          <StrategyCard
            title={t('strategy.aggressive')}
            icon={<FiTrendingUp size={24} />}
            strategy={aggressiveStrategy}
            variant="aggressive"
          />
        </motion.div>

        <motion.div
          initial={{ x: 20, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          <StrategyCard
            title={t('strategy.conservative')}
            icon={<FiTrendingDown size={24} />}
            strategy={conservativeStrategy}
            variant="conservative"
          />
        </motion.div>
      </div>

      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.3 }}
      >
        <FusedDecision
          aggressive={aggressiveStrategy}
          conservative={conservativeStrategy}
        />
      </motion.div>

      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.4 }}
      >
        <StrategyChart />
      </motion.div>
    </motion.div>
  )
}
