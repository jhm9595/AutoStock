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
from src.api import KiwoomClient, parse_numeric

logger = logging.getLogger("AutoStock.App")

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

# Predefined stocks for simulation
SIMULATED_STOCKS = {
    "005930": {"name": "삼성전자", "base_price": 60500},
    "000660": {"name": "SK하이닉스", "base_price": 165000},
    "035420": {"name": "NAVER", "base_price": 185000},
    "035720": {"name": "카카오", "base_price": 42000},
    "039490": {"name": "키움증권", "base_price": 128000},
    "005380": {"name": "현대차", "base_price": 240000},
    "068270": {"name": "셀트리온", "base_price": 182000},
    "000270": {"name": "기아", "base_price": 115000},
    "051910": {"name": "LG화학", "base_price": 310000},
    "006400": {"name": "삼성SDI", "base_price": 380000}
}

# Global State
state = {
    "general_info": {
        "account_no": config.ACCOUNT_NO or "5014803211",
        "day_of_week": "",
        "login_date": "",
        "balance": 10000000,
        "available_funds": 10000000,
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
    "condition_search_list": [
        {"id": "0", "name": "골든크로스 탐지"},
        {"id": "1", "name": "거래량 급증 (500% 이상)"},
        {"id": "2", "name": "RSI 과매도 돌파"},
        {"id": "3", "name": "볼린저밴드 하한선 터치"},
        {"id": "4", "name": "외국인/기관 순매수 유입"}
    ],
    "active_conditions": [],  # Connected condition IDs
    "detected_history": [],
    "trade_history": [],
    "holdings": [],
    "simulation_mode": False
}

def load_state():
    global state
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                # Merge loaded keys to preserve structure
                for key in ["general_info", "settings", "active_conditions", "detected_history", "trade_history", "holdings", "simulation_mode"]:
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

# Connect to Kiwoom API if not in simulation mode
token_mgr = TokenManager()
kiwoom_client = KiwoomClient(token_mgr)

def update_kiwoom_connection():
    if not state["simulation_mode"]:
        try:
            accounts = kiwoom_client.get_account_numbers()
            if accounts:
                state["general_info"]["account_no"] = accounts[0]
                state["general_info"]["is_connected"] = True
                
                # Fetch actual deposit (Available funds)
                try:
                    dep = kiwoom_client.get_deposit_details()
                    # Use ord_alow_amt, fall back to d2_pymn_alow_amt then pymn_alow_amt if unavailable
                    avail_funds = dep.get("ord_alow_amt")
                    if avail_funds is None or avail_funds == 0:
                        avail_funds = dep.get("d2_pymn_alow_amt", dep.get("pymn_alow_amt", 10000000))
                    state["general_info"]["available_funds"] = avail_funds
                    state["general_info"]["balance"] = dep.get("pymn_alow_amt", 10000000)
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
    else:
        state["general_info"]["is_connected"] = True

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

class ModeToggle(BaseModel):
    simulation_mode: bool

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
def toggle_condition(toggle: ConditionToggle):
    c_id = toggle.condition_id
    if c_id in state["active_conditions"]:
        state["active_conditions"].remove(c_id)
        action = "disconnected"
    else:
        state["active_conditions"].append(c_id)
        action = "connected"
    save_state()
    return {"status": "success", "active_conditions": state["active_conditions"], "action": action}

@app.post("/api/simulation/toggle")
def toggle_simulation_mode(toggle: ModeToggle):
    state["simulation_mode"] = toggle.simulation_mode
    update_kiwoom_connection()
    save_state()
    return {"status": "success", "simulation_mode": state["simulation_mode"], "is_connected": state["general_info"]["is_connected"]}

@app.post("/api/simulation/reset")
def reset_simulation():
    if not state["simulation_mode"]:
        raise HTTPException(status_code=400, detail="Reset is only available in simulation mode.")
    state["holdings"] = []
    state["trade_history"] = []
    state["detected_history"] = []
    state["general_info"]["balance"] = 10000000
    state["general_info"]["available_funds"] = 10000000
    save_state()
    return {"status": "success"}

@app.post("/api/order")
async def place_order(order: ManualOrder):
    stk_cd = order.stk_cd
    qty = order.quantity
    price = order.price
    side = order.side.lower()
    trade_type = order.trade_type
    
    # 1. Real Kiwoom Mode
    if not state["simulation_mode"]:
        if not state["general_info"]["is_connected"]:
            raise HTTPException(status_code=400, detail="Kiwoom API is disconnected.")
        try:
            res = kiwoom_client.place_order(stk_cd, qty, price, trade_type, side)
            if res.get("return_code") == 0:
                # Refresh account connection after ordering
                update_kiwoom_connection()
                return {"status": "success", "order_no": res.get("ord_no"), "message": res.get("return_msg")}
            else:
                raise HTTPException(status_code=400, detail=res.get("return_msg"))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    # 2. Simulation Mode
    else:
        if stk_cd not in SIMULATED_STOCKS:
            raise HTTPException(status_code=400, detail="Unsupported stock code for simulation.")
            
        stock_name = SIMULATED_STOCKS[stk_cd]["name"]
        
        # Calculate price if market order
        if price == 0:
            price = SIMULATED_STOCKS[stk_cd]["base_price"]
            
        total_cost = price * qty
        
        if side == "buy":
            if state["general_info"]["available_funds"] < total_cost:
                raise HTTPException(status_code=400, detail="Insufficient funds.")
                
            state["general_info"]["available_funds"] -= total_cost
            
            # Check if already holding
            existing = next((h for h in state["holdings"] if h["stk_cd"] == stk_cd), None)
            if existing:
                # Average price calculation
                total_qty = existing["rmnd_qty"] + qty
                avg_price = int((existing["pur_pric"] * existing["rmnd_qty"] + total_cost) / total_qty)
                existing["pur_pric"] = avg_price
                existing["rmnd_qty"] = total_qty
                existing["trde_able_qty"] = total_qty
                existing["pur_amt"] = total_qty * avg_price
            else:
                state["holdings"].append({
                    "stk_cd": stk_cd,
                    "stk_nm": stock_name,
                    "pur_pric": price,
                    "cur_prc": price,
                    "peak_price": price,
                    "peak_profit_rate": 0.0,
                    "rmnd_qty": qty,
                    "trde_able_qty": qty,
                    "pur_amt": total_cost,
                    "evlt_amt": total_cost,
                    "prft_rt": 0.0,
                    "tdy_buyq": qty,
                    "tdy_sellq": 0,
                    "buy_time": datetime.now().strftime("%H:%M:%S")
                })
        else:
            # Sell order
            existing = next((h for h in state["holdings"] if h["stk_cd"] == stk_cd), None)
            if not existing or existing["rmnd_qty"] < qty:
                raise HTTPException(status_code=400, detail="Insufficient stock quantity to sell.")
                
            existing["rmnd_qty"] -= qty
            existing["trde_able_qty"] -= qty
            existing["pur_amt"] = existing["rmnd_qty"] * existing["pur_pric"]
            
            revenue = price * qty
            state["general_info"]["available_funds"] += revenue
            state["general_info"]["balance"] += (price - existing["pur_pric"]) * qty
            
            # Calculate profit/loss
            profit_rate = ((price - existing["pur_pric"]) / existing["pur_pric"]) * 100
            
            # Remove holding if fully sold
            if existing["rmnd_qty"] == 0:
                state["holdings"].remove(existing)
                
        # Log to trade history
        state["trade_history"].insert(0, {
            "time": datetime.now().strftime("%H:%M:%S"),
            "stk_cd": stk_cd,
            "stk_nm": stock_name,
            "side": "매수" if side == "buy" else "매도",
            "qty": qty,
            "price": price,
            "amt": total_cost,
            "pnl_rate": round(((price - existing["pur_pric"]) / existing["pur_pric"] * 100), 2) if side == "sell" else 0.0
        })
        
        save_state()
        return {"status": "success", "message": f"Simulated {side} order completed."}

# Simulation Background Loop Task
async def simulation_loop():
    logger.info("Started simulation background loop.")
    while True:
        await asyncio.sleep(2)
        if not state["simulation_mode"]:
            continue
            
        now_time = datetime.now()
        current_time_str = now_time.strftime("%H:%M:%S")
        
        # Parse time limits
        buy_from = datetime.strptime(state["settings"]["buy_time_from"], "%H:%M")
        buy_to = datetime.strptime(state["settings"]["buy_time_to"], "%H:%M")
        sell_to = datetime.strptime(state["settings"]["sell_time_to"], "%H:%M")
        
        current_hm = datetime.strptime(now_time.strftime("%H:%M"), "%H:%M")
        is_buy_time = buy_from <= current_hm <= buy_to
        is_sell_time_past = current_hm > sell_to
        
        # 1. Update prices of holdings and evaluate exits
        holdings_to_sell = []
        
        for h in state["holdings"]:
            # Random price fluctuation: -1.5% to +1.8%
            change_pct = random.uniform(-1.5, 1.8)
            new_price = int(h["cur_prc"] * (1 + change_pct / 100))
            new_price = max(100, (new_price // 10) * 10) # Floor to nearest 10 won
            
            h["cur_prc"] = new_price
            h["evlt_amt"] = h["rmnd_qty"] * new_price
            
            # Profit / Loss calculation
            pnl_rate = ((new_price - h["pur_pric"]) / h["pur_pric"]) * 100
            h["prft_rt"] = round(pnl_rate, 2)
            
            # Peak Price update
            if new_price > h["peak_price"]:
                h["peak_price"] = new_price
                h["peak_profit_rate"] = round(pnl_rate, 2)
                
            # Exit Conditions check
            # Trailing Stop: Peak profit is > 0 and dropped by Z% from peak
            trailing_stop_pct = state["settings"]["trailing_stop_pct"]
            stop_loss_pct = state["settings"]["stop_loss_pct"]
            
            # Sell if past market hours
            if is_sell_time_past:
                holdings_to_sell.append((h, "시간 경과 강제 매도"))
            # Stop Loss
            elif pnl_rate <= -stop_loss_pct:
                holdings_to_sell.append((h, f"손절선 이탈 ({stop_loss_pct}%)"))
            # Trailing Stop: if it peaked above 1.5% and dropped by Z% from peak
            elif h["peak_profit_rate"] >= trailing_stop_pct and (h["peak_profit_rate"] - pnl_rate) >= trailing_stop_pct:
                holdings_to_sell.append((h, f"최고점 대비 하락 익절 (PEAK {h['peak_profit_rate']}% -> {h['prft_rt']}%)"))
                
        # Process automated sells
        for h, reason in holdings_to_sell:
            if h not in state["holdings"]:
                continue
            qty = h["rmnd_qty"]
            price = h["cur_prc"]
            revenue = price * qty
            
            state["general_info"]["available_funds"] += revenue
            state["general_info"]["balance"] += (price - h["pur_pric"]) * qty
            
            pnl_rate = ((price - h["pur_pric"]) / h["pur_pric"]) * 100
            
            state["trade_history"].insert(0, {
                "time": current_time_str,
                "stk_cd": h["stk_cd"],
                "stk_nm": h["stk_nm"],
                "side": "매도",
                "qty": qty,
                "price": price,
                "amt": revenue,
                "pnl_rate": round(pnl_rate, 2),
                "reason": reason
            })
            state["holdings"].remove(h)
            logger.info(f"[시뮬레이터] 자동 매도 체결: {h['stk_nm']}({h['stk_cd']}) - 사유: {reason}")
            
        # 2. Simulate Random Stock Detection by Active Conditions
        if state["active_conditions"] and is_buy_time:
            # ~15% chance to detect a stock each tick (2 seconds)
            if random.random() < 0.15:
                detected_cd = random.choice(list(SIMULATED_STOCKS.keys()))
                detected_name = SIMULATED_STOCKS[detected_cd]["name"]
                
                # Pick a random connected condition
                cond_id = random.choice(state["active_conditions"])
                cond_name = next(c["name"] for c in state["condition_search_list"] if c["id"] == cond_id)
                
                # Check if already logged detection recently
                duplicate = any(d for d in state["detected_history"][:5] if d["stk_cd"] == detected_cd and d["condition_name"] == cond_name)
                
                if not duplicate:
                    price = SIMULATED_STOCKS[detected_cd]["base_price"]
                    # Randomize detection price slightly
                    price = int(price * random.uniform(0.98, 1.02))
                    price = (price // 10) * 10
                    
                    state["detected_history"].insert(0, {
                        "time": current_time_str,
                        "stk_cd": detected_cd,
                        "stk_nm": detected_name,
                        "condition_name": cond_name,
                        "price": price,
                        "status": "탐지"
                    })
                    
                    logger.info(f"[시뮬레이터] 조건 탐지: {cond_name} -> {detected_name}({detected_cd}) @ {price:,}원")
                    
                    # 3. Auto Buy logic
                    if state["settings"]["auto_buy"]:
                        # Check if already holding
                        holding_exist = any(h for h in state["holdings"] if h["stk_cd"] == detected_cd)
                        if not holding_exist:
                            budget = state["settings"]["buy_budget_per_stock"]
                            if state["general_info"]["available_funds"] >= budget:
                                qty = budget // price
                                if qty > 0:
                                    cost = qty * price
                                    state["general_info"]["available_funds"] -= cost
                                    
                                    state["holdings"].append({
                                        "stk_cd": detected_cd,
                                        "stk_nm": detected_name,
                                        "pur_pric": price,
                                        "cur_prc": price,
                                        "peak_price": price,
                                        "peak_profit_rate": 0.0,
                                        "rmnd_qty": qty,
                                        "trde_able_qty": qty,
                                        "pur_amt": cost,
                                        "evlt_amt": cost,
                                        "prft_rt": 0.0,
                                        "tdy_buyq": qty,
                                        "tdy_sellq": 0,
                                        "buy_time": current_time_str
                                    })
                                    
                                    state["trade_history"].insert(0, {
                                        "time": current_time_str,
                                        "stk_cd": detected_cd,
                                        "stk_nm": detected_name,
                                        "side": "매수",
                                        "qty": qty,
                                        "price": price,
                                        "amt": cost,
                                        "pnl_rate": 0.0,
                                        "reason": f"조건 자동 매수 ({cond_name})"
                                    })
                                    logger.info(f"[시뮬레이터] 자동 매수 체결: {detected_name}({detected_cd}) {qty}주")
                                    
        # Recalculate total balance
        if state["holdings"]:
            total_holdings_value = sum(h["evlt_amt"] for h in state["holdings"])
            state["general_info"]["balance"] = state["general_info"]["available_funds"] + total_holdings_value
        else:
            state["general_info"]["balance"] = state["general_info"]["available_funds"]
            
        save_state()

# Start background simulation task when FastAPI starts
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(simulation_loop())
