import React, { useState, useEffect } from 'react';
import './App.css';
import LeftToolbar from './components/LeftToolbar';
import TradingChart from './components/TradingChart';
import RightPanel from './components/RightPanel';
import TopBar from './components/TopBar';

function App() {
  const [tradingState, setTradingState] = useState({
    isRunning: false,
    balance: 10000,
    pnl: 0,
    positions: []
  });

  const [selectedSymbol, setSelectedSymbol] = useState('BTC');

  return (
    <div className="app-container">
      <TopBar balance={tradingState.balance} pnl={tradingState.pnl} isRunning={tradingState.isRunning} />
      <div className="main-content">
        <LeftToolbar selectedSymbol={selectedSymbol} onSymbolChange={setSelectedSymbol} isRunning={tradingState.isRunning} />
        <TradingChart symbol={selectedSymbol} />
        <RightPanel tradingState={tradingState} />
      </div>
    </div>
  );
}

export default App;
