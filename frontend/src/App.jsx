import React, { useState, useEffect } from 'react';
import { 
  Shield, 
  Settings, 
  Layers, 
  History, 
  TrendingUp, 
  User, 
  Activity, 
  RefreshCw, 
  Power, 
  AlertCircle,
  Play,
  Trash2,
  TrendingDown,
  DollarSign
} from 'lucide-react';

const BACKEND_URL = 'http://localhost:8000';

function App() {
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Settings Form State
  const [settingsForm, setSettingsForm] = useState({
    auto_buy: false,
    buy_budget_per_stock: 1000000,
    daily_budget_limit: 5000000,
    buy_time_from: '09:00',
    buy_time_to: '15:20',
    sell_time_from: '09:00',
    sell_time_to: '15:30',
    trailing_stop_pct: 1.5,
    stop_loss_pct: 2.0
  });

  // Manual Order Form State
  const [manualOrder, setManualOrder] = useState({
    stk_cd: '005930',
    quantity: 10,
    price: 0,
    trade_type: '3', // Market
    side: 'buy'
  });

  // Fetch State from Backend
  const fetchState = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/state`);
      if (!response.ok) throw new Error('Failed to connect to trading backend');
      const data = await response.json();
      setState(data);
      // Initialize settings form if not edited
      if (data.settings) {
        setSettingsForm(data.settings);
      }
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Poll state every 1 second
  useEffect(() => {
    fetchState();
    const interval = setInterval(fetchState, 1000);
    return () => clearInterval(interval);
  }, []);

  // Update Settings Handler
  const handleSaveSettings = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch(`${BACKEND_URL}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: json_stringify_numbers(settingsForm)
      });
      const data = await response.json();
      if (data.status === 'success') {
        alert('설정이 저장되었습니다.');
      }
    } catch (err) {
      alert(`설정 저장 실패: ${err.message}`);
    }
  };

  // Convert input fields to numbers where appropriate
  const json_stringify_numbers = (form) => {
    return JSON.stringify({
      ...form,
      buy_budget_per_stock: Number(form.buy_budget_per_stock),
      daily_budget_limit: Number(form.daily_budget_limit),
      trailing_stop_pct: Number(form.trailing_stop_pct),
      stop_loss_pct: Number(form.stop_loss_pct)
    });
  };

  // Toggle Condition Connection
  const handleToggleCondition = async (conditionId) => {
    try {
      await fetch(`${BACKEND_URL}/api/conditions/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ condition_id: conditionId })
      });
      fetchState();
    } catch (err) {
      alert(`조건 토글 실패: ${err.message}`);
    }
  };

  // Toggle Simulation/Live Mode
  const handleToggleMode = async (mode) => {
    try {
      await fetch(`${BACKEND_URL}/api/simulation/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ simulation_mode: mode })
      });
      fetchState();
    } catch (err) {
      alert(`모드 전환 실패: ${err.message}`);
    }
  };

  // Reset Simulation
  const handleResetSimulation = async () => {
    if (!window.confirm("시뮬레이션 이력 및 보유잔고를 초기화하시겠습니까?")) return;
    try {
      await fetch(`${BACKEND_URL}/api/simulation/reset`, { method: 'POST' });
      fetchState();
    } catch (err) {
      alert(`초기화 실패: ${err.message}`);
    }
  };

  // Place Order Handler
  const handlePlaceOrder = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch(`${BACKEND_URL}/api/order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...manualOrder,
          quantity: Number(manualOrder.quantity),
          price: Number(manualOrder.price)
        })
      });
      const data = await response.json();
      if (response.ok && data.status === 'success') {
        alert('주문이 전송되었습니다.');
      } else {
        alert(`주문 실패: ${data.detail || '오류 발생'}`);
      }
    } catch (err) {
      alert(`주문 에러: ${err.message}`);
    }
  };

  // Instant Sell Handler
  const handleInstantSell = async (holding) => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          stk_cd: holding.stk_cd,
          quantity: holding.rmnd_qty,
          price: 0,
          trade_type: '3', // Market
          side: 'sell'
        })
      });
      const data = await response.json();
      if (response.ok && data.status === 'success') {
        logger.info('Immediate sell succeeded');
      } else {
        alert(`매도 실패: ${data.detail}`);
      }
    } catch (err) {
      alert(`에러: ${err.message}`);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen" style={{ backgroundColor: '#0a0a0a', color: '#fff' }}>
        <RefreshCw className="animate-spin text-white mb-4" size={40} />
        <p className="text-sm font-medium tracking-wider">주식 자동 매매 시스템 서버 연결 중...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen" style={{ backgroundColor: '#0a0a0a', color: '#fff', padding: '20px' }}>
        <AlertCircle className="text-red-500 mb-4" size={48} style={{ color: '#ff4444' }} />
        <h1 className="text-lg font-bold mb-2">백엔드 서버와 통신할 수 없습니다.</h1>
        <p className="text-sm text-gray-500 mb-6 text-center max-w-md">주식 자동매매 백엔드 서버(FastAPI)가 실행되고 있는지 확인해 주십시오.<br/>(실행 명령: python -m uvicorn src.app:app --reload)</p>
        <button onClick={fetchState} className="btn btn-primary">다시 시도</button>
      </div>
    );
  }

  const { general_info, settings, condition_search_list, active_conditions, detected_history, trade_history, holdings, simulation_mode } = state;

  return (
    <div className="min-h-screen flex flex-col" style={{ padding: '20px', maxWidth: '1600px', margin: '0 auto' }}>
      
      {/* 1. Header (메인 헤더 영역) */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-gray-800 pb-4 mb-6" style={{ borderColor: '#222' }}>
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ letterSpacing: '-0.03em' }}>
            AUTOSTOCK <span className="text-xs font-normal px-2 py-0.5 ml-2 border border-gray-700 text-gray-400 rounded">ALGO SYSTEM</span>
          </h1>
          <p className="text-xs text-gray-500 mt-1">로컬 물리 PC 키움증권 Open API 연동 자동 거래 데스크</p>
        </div>
        
        <div className="flex flex-wrap gap-3 mt-4 md:mt-0 items-center">
          {/* Mode Switcher */}
          <div className="flex bg-neutral-900 border border-neutral-800 rounded p-1">
            <button 
              onClick={() => handleToggleMode(true)}
              className={`text-xs px-3 py-1.5 rounded transition-all ${simulation_mode ? 'bg-white text-black font-semibold' : 'text-gray-400 hover:text-white'}`}
            >
              모의 시뮬레이션
            </button>
            <button 
              onClick={() => handleToggleMode(false)}
              className={`text-xs px-3 py-1.5 rounded transition-all ${!simulation_mode ? 'bg-white text-black font-semibold' : 'text-gray-400 hover:text-white'}`}
            >
              실거래 (Kiwoom Live)
            </button>
          </div>

          {simulation_mode && (
            <button 
              onClick={handleResetSimulation} 
              className="btn btn-secondary text-xs flex items-center gap-1 text-red-500 border-red-950/40 hover:bg-red-950/20"
              style={{ borderColor: 'rgba(255, 68, 68, 0.2)', color: '#ff4444' }}
            >
              <Trash2 size={13} />
              시뮬레이터 리셋
            </button>
          )}

          {/* Connection Indicator */}
          <div className="flex items-center gap-2 border border-neutral-800 px-3 py-1.5 rounded bg-neutral-900/50">
            <div className={`w-2 h-2 rounded-full ${general_info.is_connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} style={{ backgroundColor: general_info.is_connected ? '#22c55e' : '#ff4444' }}></div>
            <span className="text-xs text-gray-400 font-medium">
              {general_info.is_connected ? 'API 연결완료' : 'API 연결끊김'}
            </span>
          </div>
        </div>
      </header>

      {/* 2. Top Banner - Account summary (일반적인 정보 영역) */}
      <section className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <div className="card flex items-center gap-3">
          <div className="p-2.5 bg-neutral-900 rounded border border-neutral-800">
            <User size={18} className="text-gray-400" />
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">거래 계좌번호</p>
            <p className="font-semibold text-sm mono tracking-wide">{general_info.account_no}</p>
          </div>
        </div>

        <div className="card flex items-center gap-3">
          <div className="p-2.5 bg-neutral-900 rounded border border-neutral-800">
            <DollarSign size={18} className="text-gray-400" />
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">총 잔고평가액</p>
            <p className="font-bold text-sm tracking-tight">{general_info.balance.toLocaleString()} 원</p>
          </div>
        </div>

        <div className="card flex items-center gap-3">
          <div className="p-2.5 bg-neutral-900 rounded border border-neutral-800">
            <Activity size={18} className="text-gray-400" />
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">주문 가능 금액</p>
            <p className="font-bold text-sm tracking-tight">{general_info.available_funds.toLocaleString()} 원</p>
          </div>
        </div>

        <div className="card flex items-center gap-3">
          <div className="p-2.5 bg-neutral-900 rounded border border-neutral-800">
            <Shield size={18} className="text-gray-400" />
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">로그인 일자</p>
            <p className="text-xs font-medium mono text-gray-300">{general_info.login_date}</p>
          </div>
        </div>

        <div className="card flex items-center gap-3 col-span-2 md:col-span-1">
          <div className="p-2.5 bg-neutral-900 rounded border border-neutral-800">
            <Layers size={18} className="text-gray-400" />
          </div>
          <div>
            <p className="text-xs text-gray-500 uppercase font-medium">영업 요일</p>
            <p className="text-sm font-semibold">{general_info.day_of_week}</p>
          </div>
        </div>
      </section>

      {/* Main Grid Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* Left column: Conditions & Settings (3) & Settings Area (7) */}
        <div className="lg:col-span-4 flex flex-col gap-6">
          
          {/* 3) 조건검색 연결/해제 영역 */}
          <div className="card">
            <div className="card-title">
              <span>조건검색 실시간 연동</span>
              <span className="text-xs font-normal text-gray-500">{active_conditions.length}개 활성</span>
            </div>
            <p className="text-xs text-gray-400 mb-4">키움증권 서버에서 조건에 감지된 종목을 연동합니다. 클릭하여 조건 실시간 탐지를 활성화/비활성화 하십시오.</p>
            
            <div className="flex flex-col gap-2">
              {condition_search_list.map((cond) => {
                const isActive = active_conditions.includes(cond.id);
                return (
                  <button 
                    key={cond.id}
                    onClick={() => handleToggleCondition(cond.id)}
                    className={`flex items-center justify-between p-3 rounded border text-left transition-all ${
                      isActive 
                        ? 'bg-white text-black border-white font-medium' 
                        : 'bg-neutral-900 text-gray-300 border-neutral-800 hover:border-neutral-700'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <Power size={14} className={isActive ? 'text-black' : 'text-gray-500'} />
                      <span className="text-xs font-medium">{cond.name}</span>
                    </div>
                    <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded ${
                      isActive ? 'bg-black text-white' : 'bg-neutral-950 text-gray-500 border border-neutral-800'
                    }`}>
                      {isActive ? 'ACTIVE' : 'OFF'}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 7) 상세 거래 설정 영역 */}
          <div className="card">
            <div className="card-title">주식 자동매매 조건 설정</div>
            <form onSubmit={handleSaveSettings} className="flex flex-col gap-4">
              
              <div className="flex justify-between items-center p-3 rounded bg-neutral-900 border border-neutral-800">
                <div>
                  <p className="text-xs font-semibold">조건 포착 시 자동 매수</p>
                  <p className="text-[10px] text-gray-500">감지 즉시 시장가 자동 주문 실행</p>
                </div>
                <input 
                  type="checkbox"
                  checked={settingsForm.auto_buy}
                  onChange={(e) => setSettingsForm({ ...settingsForm, auto_buy: e.target.checked })}
                  className="w-4 h-4 accent-white"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] uppercase tracking-wider text-gray-400 mb-1.5">종목당 매수 예산</label>
                  <input 
                    type="number"
                    value={settingsForm.buy_budget_per_stock}
                    onChange={(e) => setSettingsForm({ ...settingsForm, buy_budget_per_stock: e.target.value })}
                    className="input font-medium mono"
                    placeholder="예: 1000000"
                  />
                  <span className="text-[10px] text-gray-500 mt-1 block">{(settingsForm.buy_budget_per_stock / 10000).toLocaleString()}만 원</span>
                </div>

                <div>
                  <label className="block text-[11px] uppercase tracking-wider text-gray-400 mb-1.5">당일 최대 매수 한도</label>
                  <input 
                    type="number"
                    value={settingsForm.daily_budget_limit}
                    onChange={(e) => setSettingsForm({ ...settingsForm, daily_budget_limit: e.target.value })}
                    className="input font-medium mono"
                    placeholder="예: 5000000"
                  />
                  <span className="text-[10px] text-gray-500 mt-1 block">{(settingsForm.daily_budget_limit / 10000).toLocaleString()}만 원</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] uppercase tracking-wider text-gray-400 mb-1.5">매수 가능 시간 (FROM)</label>
                  <input 
                    type="text"
                    value={settingsForm.buy_time_from}
                    onChange={(e) => setSettingsForm({ ...settingsForm, buy_time_from: e.target.value })}
                    className="input font-medium mono text-center"
                    placeholder="09:00"
                  />
                </div>
                <div>
                  <label className="block text-[11px] uppercase tracking-wider text-gray-400 mb-1.5">매수 마감 시간 (TO)</label>
                  <input 
                    type="text"
                    value={settingsForm.buy_time_to}
                    onChange={(e) => setSettingsForm({ ...settingsForm, buy_time_to: e.target.value })}
                    className="input font-medium mono text-center"
                    placeholder="15:20"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] uppercase tracking-wider text-gray-400 mb-1.5">청산 매도 시간 (FROM)</label>
                  <input 
                    type="text"
                    value={settingsForm.sell_time_from}
                    onChange={(e) => setSettingsForm({ ...settingsForm, sell_time_from: e.target.value })}
                    className="input font-medium mono text-center"
                    placeholder="09:00"
                  />
                </div>
                <div>
                  <label className="block text-[11px] uppercase tracking-wider text-gray-400 mb-1.5">청산 마감 시간 (TO)</label>
                  <input 
                    type="text"
                    value={settingsForm.sell_time_to}
                    onChange={(e) => setSettingsForm({ ...settingsForm, sell_time_to: e.target.value })}
                    className="input font-medium mono text-center"
                    placeholder="15:30"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] uppercase tracking-wider text-gray-400 mb-1.5">손절선 하락폭 (%)</label>
                  <div className="relative">
                    <input 
                      type="number"
                      step="0.1"
                      value={settingsForm.stop_loss_pct}
                      onChange={(e) => setSettingsForm({ ...settingsForm, stop_loss_pct: e.target.value })}
                      className="input font-medium mono"
                      placeholder="2.0"
                    />
                    <span className="absolute right-3 top-2.5 text-xs text-gray-500">%</span>
                  </div>
                  <span className="text-[10px] text-gray-500 mt-1 block">매입가 대비 하락 시 즉시 손절</span>
                </div>

                <div>
                  <label className="block text-[11px] uppercase tracking-wider text-gray-400 mb-1.5">익절 트레일링 스톱 (%)</label>
                  <div className="relative">
                    <input 
                      type="number"
                      step="0.1"
                      value={settingsForm.trailing_stop_pct}
                      onChange={(e) => setSettingsForm({ ...settingsForm, trailing_stop_pct: e.target.value })}
                      className="input font-medium mono"
                      placeholder="1.5"
                    />
                    <span className="absolute right-3 top-2.5 text-xs text-gray-500">%</span>
                  </div>
                  <span className="text-[10px] text-gray-500 mt-1 block">최고 수익률 대비 하락 시 매도</span>
                </div>
              </div>

              <button type="submit" className="btn btn-primary w-full mt-2 font-semibold">
                <Settings size={15} />
                거래 파라미터 저장
              </button>
            </form>
          </div>

        </div>

        {/* Right column: Holdings (6) & Manual Order (optional) */}
        <div className="lg:col-span-8 flex flex-col gap-6">
          
          {/* 6) 보유 종목 정보 영역 */}
          <div className="card">
            <div className="card-title">
              <span>내 보유 주식 포트폴리오</span>
              <span className="text-xs font-mono font-medium border border-gray-800 bg-neutral-950 px-2.5 py-1 text-gray-300 rounded">
                보유종목: {holdings.length}개
              </span>
            </div>
            
            {holdings.length === 0 ? (
              <div className="flex flex-col items-center justify-center p-12 bg-neutral-900/30 border border-dashed border-neutral-800 rounded-lg">
                <TrendingUp size={28} className="text-neutral-700 mb-3" />
                <p className="text-sm text-neutral-500">현재 보유 중인 포지션이 없습니다.</p>
                <p className="text-xs text-neutral-600 mt-1">실시간 조건 검색 탐지 또는 수동 주문을 통해 주식을 매수하십시오.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {holdings.map((item) => {
                  const isProfit = item.prft_rt >= 0;
                  return (
                    <div 
                      key={item.stk_cd} 
                      className="p-4 rounded border bg-neutral-900 border-neutral-800 flex flex-col justify-between"
                      style={{ borderLeft: `4px solid ${isProfit ? 'var(--color-profit)' : 'var(--color-loss)'}` }}
                    >
                      <div>
                        {/* Title details */}
                        <div className="flex justify-between items-start mb-2">
                          <div>
                            <h3 className="font-bold text-sm tracking-tight">{item.stk_nm}</h3>
                            <p className="text-xs font-mono text-gray-500">{item.stk_cd}</p>
                          </div>
                          <span 
                            className="text-xs font-bold font-mono px-2 py-0.5 rounded" 
                            style={{ 
                              backgroundColor: isProfit ? 'rgba(255, 68, 68, 0.1)' : 'rgba(51, 136, 255, 0.1)', 
                              color: isProfit ? 'var(--color-profit)' : 'var(--color-loss)' 
                            }}
                          >
                            {isProfit ? '+' : ''}{item.prft_rt}%
                          </span>
                        </div>

                        {/* Financial figures */}
                        <div className="grid grid-cols-2 gap-y-2 gap-x-4 py-3 border-t border-b border-neutral-800/60 my-2 text-xs">
                          <div>
                            <p className="text-[10px] text-gray-500 uppercase">보유 수량</p>
                            <p className="font-semibold mono">{item.rmnd_qty.toLocaleString()} 주</p>
                          </div>
                          <div>
                            <p className="text-[10px] text-gray-500 uppercase">매입 총금액</p>
                            <p className="font-semibold mono">{item.pur_amt.toLocaleString()} 원</p>
                          </div>
                          <div>
                            <p className="text-[10px] text-gray-500 uppercase">매입 단가</p>
                            <p className="font-semibold mono">{item.pur_pric.toLocaleString()} 원</p>
                          </div>
                          <div>
                            <p className="text-[10px] text-gray-500 uppercase">평가 금액</p>
                            <p className="font-semibold mono">{item.evlt_amt.toLocaleString()} 원</p>
                          </div>
                          <div>
                            <p className="text-[10px] text-gray-500 uppercase">현재 가격</p>
                            <p className="font-semibold mono">{item.cur_prc.toLocaleString()} 원</p>
                          </div>
                          <div>
                            <p className="text-[10px] text-gray-500 uppercase">최고 PEAK율 (가)</p>
                            <p className="font-semibold mono" style={{ color: item.peak_profit_rate >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }}>
                              {item.peak_profit_rate}% ({item.peak_price.toLocaleString()}원)
                            </p>
                          </div>
                        </div>
                      </div>

                      {/* Sell button and time details */}
                      <div className="flex justify-between items-center mt-3 pt-2">
                        <span className="text-[10px] text-gray-500">진입시간: {item.buy_time}</span>
                        <button 
                          onClick={() => handleInstantSell(item)}
                          className="btn btn-danger text-xs py-1 px-3 border-red-500/30 hover:bg-red-500/10 font-medium"
                          style={{ borderColor: 'rgba(255, 68, 68, 0.3)', color: 'var(--color-profit)' }}
                        >
                          즉시 시장가 매도
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Simulated Manual Order Form (수동 주문 발주) */}
          <div className="card">
            <div className="card-title">수동 매도/매수 주문 실행</div>
            <form onSubmit={handlePlaceOrder} className="grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
              <div className="md:col-span-1">
                <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-1.5">주문 구분</label>
                <select 
                  value={manualOrder.side}
                  onChange={(e) => setManualOrder({ ...manualOrder, side: e.target.value })}
                  className="input font-medium"
                >
                  <option value="buy">매수</option>
                  <option value="sell">매도</option>
                </select>
              </div>

              <div className="md:col-span-1">
                <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-1.5">종목코드</label>
                <input 
                  type="text"
                  value={manualOrder.stk_cd}
                  onChange={(e) => setManualOrder({ ...manualOrder, stk_cd: e.target.value })}
                  className="input font-medium mono text-center"
                  placeholder="005930"
                />
              </div>

              <div className="md:col-span-1">
                <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-1.5">수량 (주)</label>
                <input 
                  type="number"
                  value={manualOrder.quantity}
                  onChange={(e) => setManualOrder({ ...manualOrder, quantity: e.target.value })}
                  className="input font-medium mono"
                  placeholder="10"
                />
              </div>

              <div className="md:col-span-1">
                <label className="block text-[10px] uppercase tracking-wider text-gray-500 mb-1.5">주문단가 (0: 시장가)</label>
                <input 
                  type="number"
                  value={manualOrder.price}
                  onChange={(e) => setManualOrder({ ...manualOrder, price: e.target.value })}
                  className="input font-medium mono"
                  placeholder="0"
                />
              </div>

              <div className="md:col-span-1">
                <button type="submit" className="btn btn-primary w-full py-2.5 font-bold text-xs uppercase tracking-wider">
                  주문 전송
                </button>
              </div>
            </form>
          </div>

        </div>

      </div>

      {/* Logs and Histories Row */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        
        {/* 2 & 4) 조건검색 실시간 탐지 결과 및 이력 영역 */}
        <div className="card flex flex-col" style={{ minHeight: '350px' }}>
          <div className="card-title">
            <span>실시간 조건 탐지 및 해제 이력</span>
            <span className="text-xs text-gray-500">최근 감지순</span>
          </div>
          
          <div className="overflow-x-auto flex-grow">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="text-gray-500 border-b border-neutral-800">
                  <th className="py-2.5">시간</th>
                  <th className="py-2.5">조건명</th>
                  <th className="py-2.5">종목</th>
                  <th className="py-2.5">포착가</th>
                  <th className="py-2.5 text-right">상태</th>
                </tr>
              </thead>
              <tbody>
                {detected_history.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="text-center py-8 text-neutral-600">
                      실시간 조건 탐지 이력이 아직 존재하지 않습니다.
                    </td>
                  </tr>
                ) : (
                  detected_history.map((log, idx) => (
                    <tr key={idx} className="border-b border-neutral-900 hover:bg-neutral-900/30">
                      <td className="py-2.5 text-gray-400 font-mono">{log.time}</td>
                      <td className="py-2.5 text-gray-300 font-medium">{log.condition_name}</td>
                      <td className="py-2.5">
                        <span className="font-semibold text-white">{log.stk_nm}</span>
                        <span className="text-gray-500 font-mono ml-1 text-[10px]">({log.stk_cd})</span>
                      </td>
                      <td className="py-2.5 font-mono">{log.price.toLocaleString()} 원</td>
                      <td className="py-2.5 text-right font-bold" style={{ color: log.status === '탐지' ? 'var(--color-profit)' : 'var(--color-loss)' }}>
                        {log.status}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* 5) 매수/매도 거래 주문 이력 영역 */}
        <div className="card flex flex-col" style={{ minHeight: '350px' }}>
          <div className="card-title">
            <span>체결 및 거래 집행 이력</span>
            <span className="text-xs text-gray-500">최근 체결순</span>
          </div>

          <div className="overflow-x-auto flex-grow">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="text-gray-500 border-b border-neutral-800">
                  <th className="py-2.5">시간</th>
                  <th className="py-2.5">종목</th>
                  <th className="py-2.5">구분</th>
                  <th className="py-2.5">수량/단가</th>
                  <th className="py-2.5">체결금액</th>
                  <th className="py-2.5">수익률</th>
                  <th className="py-2.5 text-right">사유</th>
                </tr>
              </thead>
              <tbody>
                {trade_history.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="text-center py-8 text-neutral-600">
                      체결된 거래 이력이 존재하지 않습니다.
                    </td>
                  </tr>
                ) : (
                  trade_history.map((trade, idx) => {
                    const isBuy = trade.side === '매수';
                    const hasPnl = !isBuy && trade.pnl_rate !== 0;
                    const pnlColor = trade.pnl_rate >= 0 ? 'var(--color-profit)' : 'var(--color-loss)';
                    return (
                      <tr key={idx} className="border-b border-neutral-900 hover:bg-neutral-900/30">
                        <td className="py-2.5 text-gray-400 font-mono">{trade.time}</td>
                        <td className="py-2.5">
                          <span className="font-semibold text-white">{trade.stk_nm}</span>
                          <span className="text-gray-500 font-mono ml-1 text-[10px]">({trade.stk_cd})</span>
                        </td>
                        <td className="py-2.5 font-bold" style={{ color: isBuy ? 'var(--color-profit)' : 'var(--color-loss)' }}>
                          {trade.side}
                        </td>
                        <td className="py-2.5 font-mono">
                          {trade.qty}주 / {trade.price.toLocaleString()}원
                        </td>
                        <td className="py-2.5 font-mono">{(trade.price * trade.qty).toLocaleString()} 원</td>
                        <td className="py-2.5 font-semibold font-mono" style={{ color: pnlColor }}>
                          {isBuy ? '-' : `${trade.pnl_rate >= 0 ? '+' : ''}${trade.pnl_rate}%`}
                        </td>
                        <td className="py-2.5 text-right text-gray-400 text-[10px] font-medium">{trade.reason || '수동 주문'}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

      </section>

      {/* Footer */}
      <footer className="mt-12 mb-4 text-center border-t border-neutral-900 pt-6 text-[10px] text-gray-600">
        <p>© 2026 AutoStock Algorithmic Trading Desk. All rights reserved.</p>
        <p className="mt-1">보안 수칙: 계좌 비밀번호 및 앱 키 시크릿은 로컬 PC 설정 디렉토리 내에 독립된 파일로만 격리되어 로드됩니다.</p>
      </footer>

    </div>
  );
}

export default App;
