import os
import json
import random
import asyncio
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src import config
from src.auth import TokenManager
from src.api import KiwoomClient, parse_numeric, KiwoomAPIError
from src.websocket import KiwoomWebSocket

logger = logging.getLogger("AutoStock.App")

kiwoom_ws = None

app = FastAPI(title="AutoStock Trading System Backend")

# Enable CORS for React frontend (default Vite port: 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATE_FILE = os.path.join(config.CONFIG_DIR, "state.json")

# Global State
state = {
    "general_info": {
        "account_no": config.ACCOUNT_NO or "5014803211",
        "day_of_week": "",
        "login_date": "",
        "balance": 0,
        "available_funds": 0,
        "is_connected": False
    },
    "settings": {
        "auto_buy": False,
        "buy_budget_per_stock": 1000000,
        "daily_budget_limit": 5000000,
        "buy_time_from": "09:00",
        "buy_time_to": "15:20",
        "sell_time_from": "09:00",
        "sell_time_to": "15:30",
        "trailing_stop_pct": 1.5,
        "stop_loss_pct": 2.0
    },
    "condition_search_list": [],
    "active_conditions": [],  # Connected condition IDs
    "detected_history": [],
    "trade_history": [],
    "holdings": [],
    "daily_bought_stocks": [],  # 하루 1번 매수 제한을 위한 당일 매수 종목 리스트
    "last_trading_date": ""
}

def load_state():
    global state
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                # Merge loaded keys to preserve structure
                for key in ["general_info", "settings", "active_conditions", "detected_history", "trade_history", "holdings", "daily_bought_stocks", "last_trading_date"]:
                    if key in loaded:
                        if isinstance(state[key], dict):
                            state[key].update(loaded[key])
                        else:
                            state[key] = loaded[key]
            logger.info("Loaded state from state.json")
        except Exception as e:
            logger.error(f"Failed to load state: {e}")

def save_state():
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")

# Load state at startup
load_state()

# Update time and day of week
state["general_info"]["login_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
days_kr = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
state["general_info"]["day_of_week"] = days_kr[datetime.now().weekday()]

# Connect to Kiwoom API
token_mgr = TokenManager()
kiwoom_client = KiwoomClient(token_mgr)

def ws_message_handler(data):
    try:
        trnm = data.get("trnm", "")
        if trnm == "REAL":
            for entry in data.get("data", []):
                if entry.get("name") == "조건검색" or entry.get("type") == "02":
                    vals = entry.get("values", {})
                    seq = str(vals.get("841", ""))
                    stk_cd = str(vals.get("9001", ""))
                    action_type = vals.get("843", "")  # 'I' (Insert) or 'D' (Delete)
                    time_str = vals.get("20", datetime.now().strftime("%H:%M:%S"))
                    
                    if len(time_str) == 6:
                        time_str = f"{time_str[0:2]}:{time_str[2:4]}:{time_str[4:6]}"
                        
                    cond_name = f"조건식 {seq}"
                    for c in state["condition_search_list"]:
                        if str(c["id"]) == seq:
                            cond_name = c["name"]
                            break
                            
                    status_str = "탐지" if action_type == "I" else "해제"
                    
                    stk_nm = f"종목 {stk_cd}"
                        
                    duplicate = any(d for d in state["detected_history"][:5] 
                                    if d["stk_cd"] == stk_cd and d["condition_name"] == cond_name and d["status"] == status_str)
                    
                    if not duplicate:
                        state["detected_history"].insert(0, {
                            "time": time_str,
                            "stk_cd": stk_cd,
                            "stk_nm": stk_nm,
                            "condition_name": cond_name,
                            "status": status_str
                        })
                        state["detected_history"] = state["detected_history"][:100]
                        logger.info(f"[실시간 조건] {status_str}: {cond_name} -> {stk_nm}({stk_cd}) @ {time_str}")
                        
                        if action_type == "I" and state["settings"]["auto_buy"]:
                            # FID 10 = 현재가 (REAL 패킷에 이미 포함됨 - REST 조회 불필요)
                            realtime_price = abs(parse_numeric(vals.get("10", 0)))
                            asyncio.create_task(execute_auto_buy(stk_cd, cond_name, realtime_price))
                            
                        save_state()
                        
    except Exception as e:
        logger.error(f"Error handling WS message: {e}")

async def execute_auto_buy(stk_cd, cond_name, realtime_price=0):
    try:
        logger.info(f"[자동 매수] 조건 탐지 자동 매수 개시: {stk_cd} ({cond_name})")
        
        # 1. 당일 이미 매수한 종목인지 확인
        if stk_cd in state.get("daily_bought_stocks", []):
            logger.info(f"[자동 매수] {stk_cd} 종목은 금일 이미 매수 이력이 있어 자동 매수를 건너뜁니다.")
            return
            
        # 2. 현재 보유 중인지 확인
        holding_exist = any(h for h in state["holdings"] if h["stk_cd"] == stk_cd)
        if holding_exist:
            logger.info(f"[자동 매수] {stk_cd} 종목은 이미 보유 중이므로 자동 매수를 건너뜁니다.")
            return

        loop = asyncio.get_running_loop()

        if realtime_price > 0:
            # 빠르게 매수: REAL 패킷의 현재가 직접 활용 (REST 호출 없음)
            price = realtime_price
            logger.info(f"[자동 매수] 실시간 패킷 현재가 사용: {price:,}원 (REST 조회 생략)")
        else:
            # Fallback: REST API로 현재가 조회
            logger.info(f"[자동 매수] REAL 패킷에 현재가 없음 - REST 호출로 fallback")
            stk_info = await loop.run_in_executor(None, kiwoom_client.get_stock_info, stk_cd)
            price = abs(parse_numeric(stk_info.get("cur_prc", 0)))
        
        if price == 0:
            logger.error(f"[자동 매수] {stk_cd} 현재가를 가져오지 못했습니다. 자동 매수 취소.")
            return

        budget = state["settings"]["buy_budget_per_stock"]
        if state["general_info"]["available_funds"] < budget:
            logger.warning(f"[자동 매수] 예수금 부족 (필요: {budget:,}원 / 잔액: {state['general_info']['available_funds']:,}원)")
            return

        qty = budget // price
        if qty <= 0:
            logger.warning(f"[자동 매수] 매수금액 한도가 1주 가격보다 적어 매수할 수 없습니다.")
            return

        logger.info(f"[자동 매수] 주문 전송: {stk_cd} {qty}주 @ 시장가")
        res = await loop.run_in_executor(None, kiwoom_client.place_order, stk_cd, qty, 0, "3", "buy")
        
        if res.get("return_code") == 0:
            ord_no = res.get('ord_no', '-')
            logger.info(f"[자동 매수] 주문 성공! 주문번호: {ord_no} | {res.get('return_msg')}")
            state["trade_history"].insert(0, {
                "time": datetime.now().strftime("%H:%M:%S"),
                "stk_cd": stk_cd,
                "stk_nm": stk_cd,
                "side": "매수",
                "qty": qty,
                "price": price,
                "amt": price * qty,
                "pnl_rate": 0.0,
                "reason": f"자동 매수 ({cond_name})"
            })
            
            # 당일 매수 리스트에 추가
            if "daily_bought_stocks" not in state:
                state["daily_bought_stocks"] = []
            state["daily_bought_stocks"].append(stk_cd)
            
            save_state()
            # 주문 접수 후 키움 서버 처리 대기 후 잔액 갱신
            await asyncio.sleep(1.5)
            await loop.run_in_executor(None, update_kiwoom_connection)
            logger.info(f"[자동 매수] 잔액 갱신 완료 - 가용금액: {state['general_info']['available_funds']:,}원")
        else:
            logger.error(f"[자동 매수] 주문 실패: {res.get('return_msg')}")
            
    except Exception as e:
        logger.error(f"[자동 매수] 자동 매수 처리 중 예외 발생: {e}")

def update_kiwoom_connection():
    try:
        account_no = state["general_info"]["account_no"]
        if not account_no:
            accounts = kiwoom_client.get_account_numbers()
            if accounts:
                account_no = accounts[0]
                state["general_info"]["account_no"] = account_no
            else:
                state["general_info"]["is_connected"] = False
                return

        if account_no:
            state["general_info"]["is_connected"] = True
            
            # Fetch actual deposit (Available funds)
            try:
                dep = kiwoom_client.get_deposit_details()
                # Use ord_alow_amt, fall back to d2_pymn_alow_amt then pymn_alow_amt if unavailable
                avail_funds = dep.get("ord_alow_amt")
                if avail_funds is None or avail_funds == 0:
                    avail_funds = dep.get("d2_pymn_alow_amt", dep.get("pymn_alow_amt", 0))
                state["general_info"]["available_funds"] = avail_funds
                state["general_info"]["balance"] = dep.get("pymn_alow_amt", 0)
            except Exception as e:
                logger.warning(f"Failed to fetch live deposit: {e}")
                
            # Fetch holdings and Real Balance (Estimate Deposit Assets)
            try:
                bal = kiwoom_client.get_account_balance()
                # Update real balance from Account Balance (prsm_dpst_aset_amt)
                real_balance = bal.get("prsm_dpst_aset_amt")
                if real_balance is not None and real_balance > 0:
                    state["general_info"]["balance"] = real_balance
                
                # Map live holdings to local structure
                holdings = []
                for h in bal.get("holdings", []):
                    holdings.append({
                        "stk_cd": h["stk_cd"].replace("A", ""), # Remove prefix
                        "stk_nm": h["stk_nm"],
                        "pur_pric": h["pur_pric"],
                        "cur_prc": h["cur_prc"],
                        "peak_price": h["cur_prc"],
                        "peak_profit_rate": h["prft_rt"],
                        "rmnd_qty": h["rmnd_qty"],
                        "trde_able_qty": h["trde_able_qty"],
                        "pur_amt": h["pur_amt"],
                        "evlt_amt": h["evlt_amt"],
                        "prft_rt": h["prft_rt"],
                        "tdy_buyq": h["rmnd_qty"],
                        "tdy_sellq": 0,
                        "buy_time": datetime.now().strftime("%H:%M:%S")
                    })
                state["holdings"] = holdings
            except Exception as e:
                logger.warning(f"Failed to fetch live balance: {e}")


        else:
            state["general_info"]["is_connected"] = False
    except Exception as e:
        logger.error(f"Live Kiwoom connection failed: {e}")
        state["general_info"]["is_connected"] = False

# Initial check
update_kiwoom_connection()

# Request Models
class SettingsUpdate(BaseModel):
    auto_buy: bool
    buy_budget_per_stock: int
    daily_budget_limit: int
    buy_time_from: str
    buy_time_to: str
    sell_time_from: str
    sell_time_to: str
    trailing_stop_pct: float
    stop_loss_pct: float

class ConditionToggle(BaseModel):
    condition_id: str

class ManualOrder(BaseModel):
    stk_cd: str
    quantity: int
    price: int # 0 for Market order
    trade_type: str # "3" for Market, "0" for Limit
    side: str # "buy" or "sell"

@app.get("/api/state")
def get_state():
    # Update current time
    state["general_info"]["login_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state["general_info"]["day_of_week"] = days_kr[datetime.now().weekday()]
    return state

@app.post("/api/settings")
def update_settings(updates: SettingsUpdate):
    state["settings"] = updates.model_dump()
    save_state()
    return {"status": "success", "settings": state["settings"]}

@app.post("/api/conditions/toggle")
async def toggle_condition(toggle: ConditionToggle):
    c_id = toggle.condition_id
    if not kiwoom_ws or not kiwoom_ws.is_connected:
        raise HTTPException(status_code=400, detail="실시간 시세 서버(WebSocket)가 연결되어 있지 않습니다. 잠시 후 다시 시도해 주세요.")
        
    # 조건식 이름 조회 (로그 가독성)  
    cond_name = next((c["name"] for c in state.get("condition_search_list", []) if c["id"] == c_id), c_id)

    if c_id in state["active_conditions"]:
        try:
            await kiwoom_ws.cancel_condition_realtime(c_id)
            state["active_conditions"].remove(c_id)
            action = "disconnected"
            logger.info(f"조건검색 실시간 해제: [{c_id}] {cond_name}")
        except Exception as e:
            logger.error(f"Failed to unregister condition {c_id} on Kiwoom: {e}")
            raise HTTPException(status_code=400, detail=f"조건 연동 해제 실패: {str(e)}")
    else:
        try:
            await kiwoom_ws.request_condition_realtime(c_id)
            state["active_conditions"].append(c_id)
            action = "connected"
            logger.info(f"조건검색 실시간 등록: [{c_id}] {cond_name}")
        except Exception as e:
            logger.error(f"Failed to register condition {c_id} on Kiwoom: {e}")
            raise HTTPException(status_code=400, detail=f"조건 연동 실패: {str(e)}")
    save_state()
    return {"status": "success", "active_conditions": state["active_conditions"], "action": action}


@app.post("/api/conditions/refresh")
async def refresh_conditions():
    if not state["general_info"]["is_connected"]:
        raise HTTPException(status_code=400, detail="키움 API가 연결되어 있지 않습니다.")
    if not kiwoom_ws or not kiwoom_ws.is_connected:
        raise HTTPException(status_code=400, detail="실시간 시세 서버(WebSocket)가 연결되어 있지 않습니다. 잠시 후 다시 시도해 주세요.")
    try:
        conds = await kiwoom_ws.get_condition_list()
        state["condition_search_list"] = conds
        save_state()
        logger.info(f"Manually refreshed condition list: {conds}")
        return {"status": "success", "conditions": conds}
    except Exception as e:
        logger.error(f"Failed to refresh condition list: {e}")
        raise HTTPException(status_code=400, detail=f"조건식 동기화 실패: {str(e)}")


@app.post("/api/order")
async def place_order(order: ManualOrder):
    stk_cd = order.stk_cd
    qty = order.quantity
    price = order.price
    side = order.side.lower()
    trade_type = order.trade_type
    
    if not state["general_info"]["is_connected"]:
        raise HTTPException(status_code=400, detail="키움 API가 연결되어 있지 않습니다.")
    try:
        stk_nm = f"종목 {stk_cd}"
        existing = next((h for h in state["holdings"] if h["stk_cd"] == stk_cd), None)
        if existing:
            stk_nm = existing["stk_nm"]

        res = kiwoom_client.place_order(stk_cd, qty, price, trade_type, side)
        state["trade_history"].insert(0, {
            "time": datetime.now().strftime("%H:%M:%S"),
            "stk_cd": stk_cd,
            "stk_nm": stk_nm,
            "side": "매수" if side == "buy" else "매도",
            "qty": qty,
            "price": price if price > 0 else 0,
            "amt": price * qty if price > 0 else 0,
            "pnl_rate": 0.0,
            "reason": "수동 주문"
        })
        update_kiwoom_connection()
        save_state()
        return {"status": "success", "order_no": res.get("ord_no"), "message": res.get("return_msg")}
    except KiwoomAPIError as e:
        logger.error(f"Kiwoom order API error: {e.return_msg}")
        raise HTTPException(status_code=400, detail=f"주문 실패: {e.return_msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def websocket_loop():
    global kiwoom_ws
    logger.info("Starting WebSocket background connection monitor.")
    while True:
        # 웹소켓은 로그인/인증이 되어 있을 때 항상 연결을 시도하고 유지합니다.
        if not state["general_info"]["is_connected"]:
            await asyncio.sleep(3)
            continue

        if kiwoom_ws is None:
            kiwoom_ws = KiwoomWebSocket(token_mgr, ws_message_handler)
        
        if not kiwoom_ws.is_connected:
            try:
                logger.info("Attempting to connect Kiwoom WebSocket...")
                await kiwoom_ws.connect()
                
                # 첫 연결 성공 시 조건식 목록 자동 동기화
                try:
                    conds = await kiwoom_ws.get_condition_list()
                    state["condition_search_list"] = conds
                    logger.info(f"WebSocket connected. Auto-synced conditions: {conds}")
                    save_state()
                except Exception as ex:
                    logger.warning(f"Failed to auto-sync conditions on WS connection: {ex}")

                # 기존 연동된 조건식들 재등록
                for cond_id in state["active_conditions"]:
                    logger.info(f"Re-subscribing condition {cond_id} on reconnect...")
                    try:
                        await kiwoom_ws.request_condition_realtime(cond_id)
                    except Exception as ex:
                        logger.error(f"Failed to re-subscribe condition {cond_id}: {ex}")
            except Exception as e:
                logger.error(f"WebSocket reconnection failed: {e}")
                
        await asyncio.sleep(5)


async def real_trading_loop():
    logger.info("Started real trading background monitor 실거래 감시 루프 시작.")
    while True:
        # 보유 주식이 있으면 3초마다 타이트하게 감시(빠른 손절/익절), 없으면 10초 대기(서버 부하 최소화)
        sleep_time = 3 if len(state.get("holdings", [])) > 0 else 10
        await asyncio.sleep(sleep_time)
        
        if not state["general_info"]["is_connected"]:
            continue
            
        now_time = datetime.now()
        current_time_str = now_time.strftime("%H:%M:%S")
        current_hm = datetime.strptime(now_time.strftime("%H:%M"), "%H:%M")
        current_date_str = now_time.strftime("%Y-%m-%d")
        
        # 날짜가 바뀌었으면 당일 매수 리스트 초기화
        if state.get("last_trading_date") != current_date_str:
            state["daily_bought_stocks"] = []
            state["last_trading_date"] = current_date_str
            save_state()
            logger.info(f"[실거래 감시] 날짜가 변경되어 당일 매수 기록을 초기화했습니다: {current_date_str}")
        
        # Parse time limits
        try:
            sell_to = datetime.strptime(state["settings"]["sell_time_to"], "%H:%M")
            is_sell_time_past = current_hm > sell_to
        except Exception as e:
            logger.error(f"Failed to parse sell time limit: {e}")
            is_sell_time_past = False
            
        # 1. Periodically refresh holdings to get actual cur_prc and prft_rt
        # 보유 종목이 있을 때만 계좌 잔고를 조회하도록 최적화 (불필요한 REST API 호출 방지)
        try:
            if len(state["holdings"]) > 0:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, update_kiwoom_connection)
        except Exception as e:
            logger.warning(f"[실거래 감시] 계좌 정보 갱신 실패: {e}")
            continue
            
        # 2. Check each holding for exit conditions
        holdings_to_sell = []
        
        for h in state["holdings"]:
            stk_cd = h["stk_cd"]
            pnl_rate = h.get("prft_rt", 0.0)
            cur_prc = h.get("cur_prc", 0)
            
            # peak_price and peak_profit_rate tracking
            if "peak_price" not in h or h["peak_price"] is None or h["peak_price"] == 0:
                h["peak_price"] = cur_prc
            if "peak_profit_rate" not in h or h["peak_profit_rate"] is None:
                h["peak_profit_rate"] = pnl_rate
                
            if cur_prc > h["peak_price"]:
                h["peak_price"] = cur_prc
                h["peak_profit_rate"] = pnl_rate
                
            trailing_stop_pct = state["settings"]["trailing_stop_pct"]
            stop_loss_pct = state["settings"]["stop_loss_pct"]
            
            # Sell if past market hours
            if is_sell_time_past:
                holdings_to_sell.append((h, "시간 경과 강제 매도"))
            # Stop Loss
            elif pnl_rate <= -stop_loss_pct:
                holdings_to_sell.append((h, f"손절선 이탈 ({stop_loss_pct}%)"))
            # Trailing Stop
            elif h["peak_profit_rate"] >= trailing_stop_pct and (h["peak_profit_rate"] - pnl_rate) >= trailing_stop_pct:
                holdings_to_sell.append((h, f"최고점 대비 하락 익절 (PEAK {h['peak_profit_rate']}% -> {h['prft_rt']}%)"))
                
        # 3. Process automated real sells
        for h, reason in holdings_to_sell:
            stk_cd = h["stk_cd"]
            stk_nm = h["stk_nm"]
            qty = h.get("trde_able_qty", h.get("rmnd_qty", 0))
            cur_prc = h.get("cur_prc", 0)
            pnl_rate = h.get("prft_rt", 0.0)
            
            if qty <= 0:
                logger.warning(f"[실거래 감시] {stk_nm}({stk_cd}) 매도 대상이나 매매가능수량(trde_able_qty)이 0입니다.")
                continue
                
            logger.info(f"[실거래 감시] 자동 매도 조건 감지: {stk_nm}({stk_cd}) - 사유: {reason}. 주문 집행합니다.")
            
            try:
                loop = asyncio.get_running_loop()
                res = await loop.run_in_executor(None, kiwoom_client.place_order, stk_cd, qty, 0, "3", "sell")
                
                if res.get("return_code") == 0:
                    ord_no = res.get('ord_no', '-')
                    logger.info(f"[실거래 감시] 자동 매도 주문 성공: {stk_nm}({stk_cd}) 주문번호: {ord_no} - {res.get('return_msg')}")
                    state["trade_history"].insert(0, {
                        "time": current_time_str,
                        "stk_cd": stk_cd,
                        "stk_nm": stk_nm,
                        "side": "매도",
                        "qty": qty,
                        "price": cur_prc,
                        "amt": cur_prc * qty,
                        "pnl_rate": pnl_rate,
                        "reason": f"자동 매도 ({reason})"
                    })
                    # 주문 접수 후 키움 서버 처리 대기 후 잔액 갱신
                    await asyncio.sleep(1.5)
                    await loop.run_in_executor(None, update_kiwoom_connection)
                    logger.info(f"[실거래 감시] 잔액 갱신 완료 - 가용금액: {state['general_info']['available_funds']:,}원")
                else:
                    logger.error(f"[실거래 감시] 자동 매도 주문 실패: {res.get('return_msg')}")
            except Exception as e:
                logger.error(f"[실거래 감시] 자동 매도 처리 중 오류 발생: {e}")
                
        save_state()

# Start background monitoring tasks when FastAPI starts
@app.on_event("startup")
async def startup_event():
    # 백그라운드 태스크 시작 (조건식 목록 동기화는 websocket_loop가 첫 연결 성공 시 수행함)
    asyncio.create_task(websocket_loop())
    asyncio.create_task(real_trading_loop())

