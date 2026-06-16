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
  Trash2,
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
        body: JSON.stringify({
          ...settingsForm,
          buy_budget_per_stock: Number(settingsForm.buy_budget_per_stock),
          daily_budget_limit: Number(settingsForm.daily_budget_limit),
          trailing_stop_pct: Number(settingsForm.trailing_stop_pct),
          stop_loss_pct: Number(settingsForm.stop_loss_pct)
        })
      });
      const data = await response.json();
      if (data.status === 'success') {
        alert('거래 파라미터가 저장되었습니다.');
      }
    } catch (err) {
      alert(`설정 저장 실패: ${err.message}`);
    }
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

  // Refresh Registered Conditions from Kiwoom
  const handleRefreshConditions = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/conditions/refresh`, { method: 'POST' });
      const data = await response.json();
      if (response.ok && data.status === 'success') {
        alert('실제 키움 조건검색 식 목록이 정상적으로 동기화되었습니다.');
        fetchState();
      } else {
        alert(`동기화 실패: ${data.detail || '오류 발생'}`);
      }
    } catch (err) {
      alert(`에러: ${err.message}`);
    }
  };

  // Reset Simulation
  const handleResetSimulation = async () => {
    if (!window.confirm("시뮬레이션 데이터(잔고 및 매매이력)를 초기화하시겠습니까?")) return;
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
        alert('주문 전송 완료');
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
      if (!response.ok) {
        alert(`매도 실패: ${data.detail}`);
      }
    } catch (err) {
      alert(`에러: ${err.message}`);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen" style={{ backgroundColor: '#f6f8fa', color: '#1a1f26' }}>
        <RefreshCw className="animate-spin text-neutral-800 mb-4" size={40} />
        <p className="text-sm font-semibold tracking-wider">자동 매매 시스템 로드 중...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen" style={{ backgroundColor: '#f6f8fa', color: '#1a1f26', padding: '20px' }}>
        <AlertCircle className="mb-4 text-red-500" size={48} style={{ color: '#e53e3e' }} />
        <h1 className="text-lg font-bold mb-2">백엔드 서버 연결 끊김</h1>
        <p className="text-xs text-neutral-500 mb-6 text-center max-w-sm"> FastApi 서버가 작동하고 있지 않습니다.<br/>터미널에서 서버 기동 명령을 다시 확인해주세요. </p>
        <button onClick={fetchState} className="btn btn-primary">서버 다시 연결</button>
      </div>
    );
  }

  const { general_info, settings, condition_search_list, active_conditions, detected_history, trade_history, holdings, simulation_mode } = state;

  return (
    <div className="flex flex-col" style={{ padding: '15px 24px', minHeight: '100vh', maxWidth: '1800px', margin: '0 auto', gap: '16px' }}>
      
      {/* Header (메인 헤더) */}
      <header className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b border-neutral-200/60 pb-3" style={{ borderColor: '#e9ecef' }}>
        <div>
          <h1 className="text-xl font-extrabold tracking-tight flex items-center gap-2" style={{ color: '#111' }}>
            AUTOSTOCK
            <span className="text-[10px] font-bold px-2 py-0.5 border border-neutral-300 text-neutral-500 rounded-lg bg-neutral-100">DESK</span>
          </h1>
          <p className="text-[10.5px] text-neutral-500 font-medium">키움증권 API 기반 자동 거래 및 모니터링 시스템</p>
        </div>
        
        <div className="flex gap-2.5 mt-3 sm:mt-0 items-center">
          {/* Connection status */}
          <div className="flex items-center gap-1.5 border border-neutral-200 px-3 py-1.5 rounded-xl bg-white shadow-sm">
            <div className={`w-2.5 h-2.5 rounded-full ${general_info.is_connected ? 'bg-emerald-500' : 'bg-rose-500'}`} style={{ backgroundColor: general_info.is_connected ? '#10b981' : '#f43f5e' }}></div>
            <span className="text-[11px] font-bold text-neutral-600">
              {general_info.is_connected ? 'API 연결완료' : 'API 연결끊김'}
            </span>
          </div>
        </div>
      </header>

      {/* 3-Column Compact Workspace */}
      <div className="workspace-grid flex-grow">
        
        {/* ================= COLUMN 1 (Left): Info & Toggles & Settings ================= */}
        <div className="flex flex-col gap-4">
          
          {/* 1) 일반 정보 및 계좌 정보 카드 (Compact) */}
          <div className="card" style={{ padding: '14px' }}>
            <div className="card-title">
              <span>계좌 상태 요약</span>
              <span className="badge badge-connected text-[10px]" style={{ backgroundColor: '#e0f2fe', color: '#0369a1' }}>실운영</span>
            </div>
            
            <div className="flex flex-col gap-2.5 text-xs">
              <div className="flex justify-between items-center py-1 border-b border-neutral-100">
                <span className="text-neutral-500 flex items-center gap-1"><User size={13}/>계좌번호</span>
                <span className="font-bold mono text-neutral-800">{general_info.account_no}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-neutral-100">
                <span className="text-neutral-500 flex items-center gap-1"><DollarSign size={13}/>총 잔고평가액</span>
                <span className="font-extrabold text-neutral-800 text-sm">{general_info.balance.toLocaleString()} 원</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-neutral-100">
                <span className="text-neutral-500 flex items-center gap-1"><Activity size={13}/>주문 가능 현금</span>
                <span className="font-bold text-neutral-700">{general_info.available_funds.toLocaleString()} 원</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-neutral-100">
                <span className="text-neutral-500 flex items-center gap-1"><Shield size={13}/>마지막 갱신</span>
                <span className="font-medium mono text-neutral-700 text-[10.5px]">{general_info.login_date.split(' ')[1] || general_info.login_date}</span>
              </div>
              <div className="flex justify-between items-center py-1">
                <span className="text-neutral-500 flex items-center gap-1"><Layers size={13}/>영업 요일</span>
                <span className="font-bold text-neutral-700">{general_info.day_of_week}</span>
              </div>
            </div>
          </div>

          {/* 3) 조건검색 연결/해제 영역 (Compact & Sleek) */}
          <div className="card" style={{ padding: '14px' }}>
            <div className="card-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', marginBottom: '12px' }}>
              <div className="flex items-center gap-1.5">
                <span>조건 탐지 실시간 연동</span>
                <span className="badge badge-connected text-[10px] font-mono" style={{ backgroundColor: '#f1f5f9', color: '#475569' }}>
                  {active_conditions.length}개 연동
                </span>
              </div>
              <button 
                onClick={handleRefreshConditions}
                className="btn btn-secondary text-[10px] py-1 px-2 flex items-center gap-1 rounded-lg hover:bg-neutral-100"
                style={{ border: '1px solid #e2e8f0', cursor: 'pointer', height: '24px', whiteSpace: 'nowrap' }}
              >
                <RefreshCw size={10} />
                조건식 동기화
              </button>
            </div>
            
            <div className="flex flex-col gap-2.5">
              {condition_search_list.map((cond) => {
                const isActive = active_conditions.includes(cond.id);
                return (
                  <div 
                    key={cond.id}
                    className="flex justify-between items-center py-1.5 px-1 border-b border-neutral-100/50 text-xs"
                    style={{ borderBottom: '1px solid #f8fafc' }}
                  >
                    <span className="font-semibold text-neutral-700">{cond.name}</span>
                    
                    <label className="switch">
                      <input 
                        type="checkbox" 
                        checked={isActive} 
                        onChange={() => handleToggleCondition(cond.id)}
                      />
                      <span className="switch-slider"></span>
                    </label>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 7) 자동 거래 설정 영역 (Compact) */}
          <div className="card" style={{ padding: '14px' }}>
            <div className="card-title">봇 거래 매개변수 설정</div>
            <form onSubmit={handleSaveSettings} className="flex flex-col gap-3">
              
              <div className="flex justify-between items-center p-3 rounded-2xl bg-neutral-50/60 border border-neutral-200/50" style={{ marginBottom: '4px' }}>
                <div>
                  <p className="text-[11.5px] font-bold text-neutral-800 tracking-tight">자동 매수 봇 활성화</p>
                  <p className="text-[9.5px] text-neutral-500 font-medium">조건식 탐지 즉시 자동 매입 실행</p>
                </div>
                <label className="switch">
                  <input 
                    type="checkbox"
                    checked={settingsForm.auto_buy}
                    onChange={(e) => setSettingsForm({ ...settingsForm, auto_buy: e.target.checked })}
                  />
                  <span className="switch-slider"></span>
                </label>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[9.5px] font-bold text-neutral-500 uppercase tracking-tight mb-1">종목 매수금액</label>
                  <input 
                    type="number"
                    value={settingsForm.buy_budget_per_stock}
                    onChange={(e) => setSettingsForm({ ...settingsForm, buy_budget_per_stock: e.target.value })}
                    className="input font-bold mono"
                  />
                  <span className="text-[9px] text-neutral-400 block mt-0.5">{(settingsForm.buy_budget_per_stock / 10000).toLocaleString()}만 원</span>
                </div>

                <div>
                  <label className="block text-[9.5px] font-bold text-neutral-500 uppercase tracking-tight mb-1">당일 총 매수한도</label>
                  <input 
                    type="number"
                    value={settingsForm.daily_budget_limit}
                    onChange={(e) => setSettingsForm({ ...settingsForm, daily_budget_limit: e.target.value })}
                    className="input font-bold mono"
                  />
                  <span className="text-[9px] text-neutral-400 block mt-0.5">{(settingsForm.daily_budget_limit / 10000).toLocaleString()}만 원</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[9.5px] font-bold text-neutral-500 uppercase tracking-tight mb-1">매수시간 (시작/마감)</label>
                  <div className="flex gap-1">
                    <input 
                      type="text" 
                      value={settingsForm.buy_time_from} 
                      onChange={(e) => setSettingsForm({ ...settingsForm, buy_time_from: e.target.value })}
                      className="input font-bold text-center p-1"
                    />
                    <input 
                      type="text" 
                      value={settingsForm.buy_time_to} 
                      onChange={(e) => setSettingsForm({ ...settingsForm, buy_time_to: e.target.value })}
                      className="input font-bold text-center p-1"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-[9.5px] font-bold text-neutral-500 uppercase tracking-tight mb-1">청산시간 (시작/마감)</label>
                  <div className="flex gap-1">
                    <input 
                      type="text" 
                      value={settingsForm.sell_time_from} 
                      onChange={(e) => setSettingsForm({ ...settingsForm, sell_time_from: e.target.value })}
                      className="input font-bold text-center p-1"
                    />
                    <input 
                      type="text" 
                      value={settingsForm.sell_time_to} 
                      onChange={(e) => setSettingsForm({ ...settingsForm, sell_time_to: e.target.value })}
                      className="input font-bold text-center p-1"
                    />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[9.5px] font-bold text-neutral-500 uppercase tracking-tight mb-1">손절선 범위 (%)</label>
                  <input 
                    type="number"
                    step="0.1"
                    value={settingsForm.stop_loss_pct}
                    onChange={(e) => setSettingsForm({ ...settingsForm, stop_loss_pct: e.target.value })}
                    className="input font-bold mono text-center"
                  />
                </div>
                <div>
                  <label className="block text-[9.5px] font-bold text-neutral-500 uppercase tracking-tight mb-1">트레일링 익절 (%)</label>
                  <input 
                    type="number"
                    step="0.1"
                    value={settingsForm.trailing_stop_pct}
                    onChange={(e) => setSettingsForm({ ...settingsForm, trailing_stop_pct: e.target.value })}
                    className="input font-bold mono text-center"
                  />
                </div>
              </div>

              <button type="submit" className="btn btn-primary w-full py-2 rounded-xl mt-1.5 font-bold text-[11px]">
                <Settings size={13} />
                거래 설정 저장
              </button>
            </form>
          </div>

        </div>

        {/* ================= COLUMN 2 (Middle): Portfolio Holdings & Manual Order ================= */}
        <div className="flex flex-col gap-4">
          
          {/* 6) 보유 종목 정보 영역 (Table-based for extreme space efficiency) */}
          <div className="card flex flex-col" style={{ minHeight: '400px', padding: '14px' }}>
            <div className="card-title">
              <span>내 보유 주식 포트폴리오</span>
              <span className="badge badge-connected text-[10px] font-mono">보유종목: {holdings.length}개</span>
            </div>
            
            <div className="overflow-y-auto flex-grow" style={{ maxHeight: '350px' }}>
              {holdings.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-12 bg-neutral-50/50 border border-dashed border-neutral-200 rounded-2xl h-full">
                  <TrendingUp size={24} className="text-neutral-300 mb-2" />
                  <p className="text-xs text-neutral-500 font-bold">현재 보유중인 포지션이 없습니다.</p>
                  <p className="text-[10px] text-neutral-400 mt-0.5 text-center">조건식 감지 활성화 시 자동 매수되거나 아래 폼에서 수동 주문할 수 있습니다.</p>
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  {holdings.map((item) => {
                    const isProfit = item.prft_rt >= 0;
                    const profitColor = isProfit ? 'var(--color-profit)' : 'var(--color-loss)';
                    return (
                      <div 
                        key={item.stk_cd}
                        className="p-3 rounded-2xl border bg-white border-neutral-200/80 shadow-sm flex flex-col gap-2 transition-all hover:border-neutral-400"
                        style={{ borderLeft: `4px solid ${profitColor}` }}
                      >
                        <div className="flex justify-between items-center">
                          <div>
                            <span className="font-extrabold text-xs text-neutral-800">{item.stk_nm}</span>
                            <span className="text-[9.5px] font-mono text-neutral-400 ml-1.5">{item.stk_cd}</span>
                          </div>
                          
                          <div className="flex items-center gap-2">
                            <span className="text-[10.5px] font-extrabold font-mono" style={{ color: profitColor }}>
                              {isProfit ? '+' : ''}{item.prft_rt}%
                            </span>
                            <span className="text-[9px] text-neutral-400 font-mono">({item.buy_time})</span>
                          </div>
                        </div>

                        <div className="grid grid-cols-3 gap-2 py-1.5 border-t border-b border-neutral-100 text-[10.5px]">
                          <div>
                            <span className="text-[8.5px] text-neutral-400 uppercase font-bold block">보유량 / 매입가</span>
                            <span className="font-bold text-neutral-700">{item.rmnd_qty}주</span> / <span className="font-medium mono text-neutral-600">{item.pur_pric.toLocaleString()}원</span>
                          </div>
                          <div>
                            <span className="text-[8.5px] text-neutral-400 uppercase font-bold block">평가금액</span>
                            <span className="font-bold text-neutral-800">{item.evlt_amt.toLocaleString()}원</span>
                          </div>
                          <div>
                            <span className="text-[8.5px] text-neutral-400 uppercase font-bold block">최고 PEAK</span>
                            <span className="font-bold font-mono" style={{ color: item.peak_profit_rate >= 0 ? 'var(--color-profit)' : 'var(--color-loss)' }}>
                              {item.peak_profit_rate}%
                            </span>
                          </div>
                        </div>

                        <div className="flex justify-between items-center pt-0.5">
                          <span className="text-[9px] text-neutral-500">
                            현재가: <span className="font-semibold mono">{item.cur_prc.toLocaleString()}원</span>
                          </span>
                          <button 
                            onClick={() => handleInstantSell(item)}
                            className="btn btn-danger text-[9.5px] py-0.5 px-2.5 rounded-lg font-bold"
                          >
                            즉시 매도
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Manual Order card (Compact Inline Form) */}
          <div className="card" style={{ padding: '14px' }}>
            <div className="card-title">수동 즉시 주문 실행</div>
            <form onSubmit={handlePlaceOrder} className="grid grid-cols-5 gap-2 items-end">
              <div>
                <label className="block text-[9px] font-bold text-neutral-500 mb-1">구분</label>
                <select 
                  value={manualOrder.side}
                  onChange={(e) => setManualOrder({ ...manualOrder, side: e.target.value })}
                  className="input font-semibold p-1"
                >
                  <option value="buy">매수</option>
                  <option value="sell">매도</option>
                </select>
              </div>

              <div>
                <label className="block text-[9px] font-bold text-neutral-500 mb-1">종목코드</label>
                <input 
                  type="text"
                  value={manualOrder.stk_cd}
                  onChange={(e) => setManualOrder({ ...manualOrder, stk_cd: e.target.value })}
                  className="input font-bold mono text-center"
                  placeholder="005930"
                />
              </div>

              <div>
                <label className="block text-[9px] font-bold text-neutral-500 mb-1">수량</label>
                <input 
                  type="number"
                  value={manualOrder.quantity}
                  onChange={(e) => setManualOrder({ ...manualOrder, quantity: e.target.value })}
                  className="input font-bold mono text-center"
                />
              </div>

              <div>
                <label className="block text-[9px] font-bold text-neutral-500 mb-1">단가(0:시장가)</label>
                <input 
                  type="number"
                  value={manualOrder.price}
                  onChange={(e) => setManualOrder({ ...manualOrder, price: e.target.value })}
                  className="input font-bold mono text-center"
                />
              </div>

              <div>
                <button type="submit" className="btn btn-primary w-full py-1.5 rounded-xl font-bold text-[10px] uppercase">
                  주문전송
                </button>
              </div>
            </form>
          </div>

        </div>

        {/* ================= COLUMN 3 (Right): Detections & Trades Logs ================= */}
        <div className="flex flex-col gap-4">
          
          {/* 2 & 4) 실시간 조건 탐지 결과 및 이력 (Compact height limit) */}
          <div className="card flex flex-col" style={{ height: '270px', padding: '14px' }}>
            <div className="card-title">
              <span>실시간 조건 탐지 및 해제 이력</span>
              <span className="badge badge-disconnected text-[9px] font-mono">최근 감지</span>
            </div>
            
            <div className="overflow-y-auto flex-grow">
              <table className="w-full text-[11px] text-left">
                <thead>
                  <tr className="text-neutral-400 border-b border-neutral-100 font-bold">
                    <th className="py-1">시간</th>
                    <th className="py-1">조건식</th>
                    <th className="py-1">종목</th>
                    <th className="py-1 text-right">상태</th>
                  </tr>
                </thead>
                <tbody>
                  {detected_history.length === 0 ? (
                    <tr>
                      <td colSpan="4" className="text-center py-12 text-neutral-400">
                        실시간 탐지 이력이 비어있습니다.
                      </td>
                    </tr>
                  ) : (
                    detected_history.map((log, idx) => (
                      <tr key={idx} className="border-b border-neutral-50/50 hover:bg-neutral-50">
                        <td className="py-1.5 text-neutral-400 mono">{log.time}</td>
                        <td className="py-1.5 text-neutral-600 font-medium">{log.condition_name.split(' ')[0]}</td>
                        <td className="py-1.5 font-bold text-neutral-800">
                          {log.stk_nm} <span className="text-[9px] font-mono text-neutral-400 font-normal">({log.stk_cd})</span>
                        </td>
                        <td className="py-1.5 text-right font-extrabold text-[10.5px]" style={{ color: log.status === '탐지' ? 'var(--color-profit)' : 'var(--color-loss)' }}>
                          {log.status}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* 5) 매수/매도 거래 주문 이력 (Compact height limit) */}
          <div className="card flex flex-col" style={{ height: '270px', padding: '14px' }}>
            <div className="card-title">
              <span>체결 및 주문 집행 이력</span>
              <span className="badge badge-disconnected text-[9px] font-mono">최근 체결</span>
            </div>

            <div className="overflow-y-auto flex-grow">
              <table className="w-full text-[11px] text-left">
                <thead>
                  <tr className="text-neutral-400 border-b border-neutral-100 font-bold">
                    <th className="py-1">시간</th>
                    <th className="py-1">종목</th>
                    <th className="py-1">구분</th>
                    <th className="py-1">수량/단가</th>
                    <th className="py-1">수익률</th>
                    <th className="py-1 text-right">사유</th>
                  </tr>
                </thead>
                <tbody>
                  {trade_history.length === 0 ? (
                    <tr>
                      <td colSpan="6" className="text-center py-12 text-neutral-400">
                        체결된 거래 내역이 비어있습니다.
                      </td>
                    </tr>
                  ) : (
                    trade_history.map((trade, idx) => {
                      const isBuy = trade.side === '매수';
                      const hasPnl = !isBuy && trade.pnl_rate !== 0;
                      const pnlColor = trade.pnl_rate >= 0 ? 'var(--color-profit)' : 'var(--color-loss)';
                      return (
                        <tr key={idx} className="border-b border-neutral-50/50 hover:bg-neutral-50">
                          <td className="py-1.5 text-neutral-400 mono">{trade.time}</td>
                          <td className="py-1.5 font-bold text-neutral-800">
                            {trade.stk_nm}
                          </td>
                          <td className="py-1.5 font-extrabold" style={{ color: isBuy ? 'var(--color-profit)' : 'var(--color-loss)' }}>
                            {trade.side}
                          </td>
                          <td className="py-1.5 font-mono text-[10px] text-neutral-500">
                            {trade.qty}주/{trade.price.toLocaleString()}원
                          </td>
                          <td className="py-1.5 font-bold font-mono" style={{ color: pnlColor }}>
                            {isBuy ? '-' : `${trade.pnl_rate >= 0 ? '+' : ''}${trade.pnl_rate}%`}
                          </td>
                          <td className="py-1.5 text-right text-neutral-400 text-[9px] font-semibold">{trade.reason ? trade.reason.split(' ')[0] : '수동'}</td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>

        </div>

      </div>

      {/* Footer */}
      <footer className="text-center border-t border-neutral-200/60 pt-3 text-[9px] text-neutral-400 flex justify-between items-center">
        <span>© 2026 AutoStock Algorithmic Trading Desk</span>
        <span>보안 안내: 모든 비밀번호 및 앱 키 인증 정보는 소스코드 격리 상태로 로컬 물리 파일시스템에서만 관리됩니다.</span>
      </footer>

    </div>
  );
}

export default App;
