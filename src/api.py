import requests
import logging
import time
import collections
import threading
from src import config

logger = logging.getLogger("AutoStock.API")
limiter_logger = logging.getLogger("AutoStock.RateLimiter")

class KiwoomRateLimiter:
    def __init__(self):
        self.lock = threading.Lock()
        self.history = collections.deque()
        
        # Limit definitions: (duration_seconds, max_calls)
        self.limits = [
            (1.0, 5),      # 5 calls per 1 second
            (60.0, 100),   # 100 calls per 1 minute
            (3600.0, 1000) # 1000 calls per 1 hour
        ]

    def wait_if_needed(self):
        with self.lock:
            while True:
                now = time.time()
                
                # Remove timestamps older than 3600 seconds
                while self.history and self.history[0] < now - 3600.0:
                    self.history.popleft()
                
                sleep_needed = 0.0
                for duration, max_calls in self.limits:
                    # Filter history to current window duration
                    window_calls = [t for t in self.history if t >= now - duration]
                    if len(window_calls) >= max_calls:
                        # Find the oldest timestamp in the current window that must exit
                        oldest_in_window = window_calls[len(window_calls) - max_calls]
                        wait_time = (oldest_in_window + duration) - now
                        if wait_time > sleep_needed:
                            sleep_needed = wait_time
                
                if sleep_needed > 0:
                    limiter_logger.warning(
                        f"Rate limit reached. Sleeping for {sleep_needed:.3f} seconds "
                        f"to comply with Kiwoom API limits (5/s, 100/m, 1000/h)."
                    )
                    time.sleep(sleep_needed)
                    # Loop again to re-check all windows after sleep
                else:
                    self.history.append(time.time())
                    break

def parse_numeric(val):
    """Utility to parse padded numbers (e.g. '000000017598258' or '-00000032') into Python numeric types."""
    if val is None or str(val).strip() == "":
        return 0
    val_str = str(val).strip()
    try:
        # Check if float (contains dot)
        if '.' in val_str:
            return float(val_str)
        # Handles positive/negative signs and leading zeros automatically
        return int(val_str)
    except ValueError:
        return val_str

class KiwoomClient:
    def __init__(self, token_manager):
        self.token_manager = token_manager
        self.rate_limiter = KiwoomRateLimiter()

    def _get_common_headers(self, api_id, cont_yn="N", next_key=""):
        """Generates standard headers for Kiwoom REST API requests."""
        token = self.token_manager.get_token()
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "api-id": api_id,
            "authorization": f"Bearer {token}"
        }
        if cont_yn == "Y":
            headers["cont-yn"] = "Y"
            headers["next-key"] = next_key
        return headers

    def _post(self, api_id, url_path, body=None, cont_yn="N", next_key=""):
        """Internal helper for POST requests."""
        # Wait if Kiwoom rate limit is reached
        self.rate_limiter.wait_if_needed()

        url = f"{config.BASE_URL}{url_path}"
        headers = self._get_common_headers(api_id, cont_yn, next_key)
        body = body or {}

        try:
            logger.debug(f"[{api_id}] POST {url_path} | Body: {body}")
            response = requests.post(url, headers=headers, json=body, timeout=10)
            response.raise_for_status()
            res_data = response.json()
            
            # Check for API error code
            return_code = res_data.get("return_code")
            return_msg = res_data.get("return_msg", "")
            
            if return_code is not None and return_code != 0:
                logger.error(f"[{api_id}] API returned error {return_code}: {return_msg}")
            
            # Return response and headers (for pagination info)
            return res_data, response.headers
        except Exception as e:
            logger.error(f"[{api_id}] Request failed: {e}")
            raise

    # 1. 계좌번호조회 (ka00001)
    def get_account_numbers(self):
        """Retrieves list of account numbers associated with current session."""
        res_data, _ = self._post("ka00001", "/api/dostk/acnt")
        account_no = res_data.get("acctNo", "")
        # The API usually returns comma-separated or single account string
        if account_no:
            accounts = [acc.strip() for acc in account_no.split(",") if acc.strip()]
            logger.info(f"Retrieved accounts: {accounts}")
            return accounts
        return []

    # 2. 예수금상세현황요청 (kt00001)
    def get_deposit_details(self, query_type="3"):
        """
        Gets deposit details for the account.
        query_type: '3' for estimate, '2' for normal.
        """
        body = {
            "qry_tp": query_type
        }
        res_data, _ = self._post("kt00001", "/api/dostk/acnt", body)
        
        # Parse key numeric values for convenience
        parsed_data = {k: parse_numeric(v) for k, v in res_data.items() if k not in ["stk_entr_prst"]}
        parsed_data["stk_entr_prst"] = res_data.get("stk_entr_prst", [])
        return parsed_data

    # 3. 계좌평가잔고내역요청 (kt00018)
    def get_account_balance(self, query_type="1", exchange="KRX"):
        """
        Gets details of stocks in possession and evaluation balance.
        query_type: '1' for summary, '2' for detailed.
        exchange: 'KRX' (Korea Exchange) or 'NXT' (Nextrade).
        """
        body = {
            "qry_tp": query_type,
            "dmst_stex_tp": exchange
        }
        res_data, _ = self._post("kt00018", "/api/dostk/acnt", body)
        
        # Parse output data
        parsed_data = {
            "tot_pur_amt": parse_numeric(res_data.get("tot_pur_amt")),
            "tot_evlt_amt": parse_numeric(res_data.get("tot_evlt_amt")),
            "tot_evlt_pl": parse_numeric(res_data.get("tot_evlt_pl")),
            "tot_prft_rt": parse_numeric(res_data.get("tot_prft_rt")),
            "prsm_dpst_aset_amt": parse_numeric(res_data.get("prsm_dpst_aset_amt")),
            "return_code": res_data.get("return_code"),
            "return_msg": res_data.get("return_msg"),
        }
        
        raw_holdings = res_data.get("acnt_evlt_remn_indv_tot", [])
        holdings = []
        for h in raw_holdings:
            holdings.append({
                "stk_cd": h.get("stk_cd", ""),
                "stk_nm": h.get("stk_nm", ""),
                "evltv_prft": parse_numeric(h.get("evltv_prft")),
                "prft_rt": parse_numeric(h.get("prft_rt")),
                "pur_pric": parse_numeric(h.get("pur_pric")),
                "cur_prc": parse_numeric(h.get("cur_prc")),
                "rmnd_qty": parse_numeric(h.get("rmnd_qty")),
                "trde_able_qty": parse_numeric(h.get("trde_able_qty")),
                "pur_amt": parse_numeric(h.get("pur_amt")),
                "evlt_amt": parse_numeric(h.get("evlt_amt")),
                "poss_rt": parse_numeric(h.get("poss_rt")),
            })
        parsed_data["holdings"] = holdings
        return parsed_data

    # 4. 주식기본정보요청 (ka10001)
    def get_stock_info(self, stock_code):
        """Retrieves basic info for a given stock code."""
        body = {
            "stk_cd": stock_code
        }
        res_data, _ = self._post("ka10001", "/api/dostk/stkinfo", body)
        return {k: parse_numeric(v) for k, v in res_data.items()}

    # 5. 주식분봉차트조회요청 (ka10080)
    def get_minutes_chart(self, stock_code, scope="1", apply_adjustment="1", base_date=""):
        """
        Gets minutes chart data.
        scope: '1' (1m), '3' (3m), '5' (5m), '10' (10m), '15' (15m), '30' (30m), etc.
        apply_adjustment: '1' (apply split/dividend adjustments), '0' (raw).
        """
        body = {
            "stk_cd": stock_code,
            "tic_scope": scope,
            "upd_stkpc_tp": apply_adjustment
        }
        if base_date:
            body["base_dt"] = base_date
            
        res_data, _ = self._post("ka10080", "/api/dostk/chart", body)
        raw_list = res_data.get("stk_min_pole_chart_qry", [])
        
        parsed_list = []
        for c in raw_list:
            parsed_list.append({
                "cur_prc": abs(parse_numeric(c.get("cur_prc"))), # Sign might indicate change direction, we take absolute for price
                "trde_qty": parse_numeric(c.get("trde_qty")),
                "cntr_tm": c.get("cntr_tm", ""), # YYYYMMDDHHmmss
                "open_pric": abs(parse_numeric(c.get("open_pric"))),
                "high_pric": abs(parse_numeric(c.get("high_pric"))),
                "low_pric": abs(parse_numeric(c.get("low_pric"))),
                "pred_pre": parse_numeric(c.get("pred_pre")),
                "pred_pre_sig": c.get("pred_pre_sig", "")
            })
        return parsed_list

    # 6. 주식일봉차트조회요청 (ka10081)
    def get_daily_chart(self, stock_code, base_date, apply_adjustment="1"):
        """
        Gets daily chart data.
        base_date: YYYYMMDD.
        """
        body = {
            "stk_cd": stock_code,
            "base_dt": base_date,
            "upd_stkpc_tp": apply_adjustment
        }
        res_data, _ = self._post("ka10081", "/api/dostk/chart", body)
        raw_list = res_data.get("stk_dd_pole_chart_qry", [])
        
        parsed_list = []
        for c in raw_list:
            parsed_list.append({
                "cur_prc": abs(parse_numeric(c.get("cur_prc"))),
                "trde_qty": parse_numeric(c.get("trde_qty")),
                "trde_dt": c.get("trde_dt", ""), # YYYYMMDD
                "open_pric": abs(parse_numeric(c.get("open_pric"))),
                "high_pric": abs(parse_numeric(c.get("high_pric"))),
                "low_pric": abs(parse_numeric(c.get("low_pric"))),
                "pred_pre": parse_numeric(c.get("pred_pre")),
                "pred_pre_sig": c.get("pred_pre_sig", "")
            })
        return parsed_list

    # 7. 주식 매수주문 (kt10000) & 주식 매도주문 (kt10001)
    def place_order(self, stock_code, quantity, price=0, trade_type="3", side="buy", exchange="KRX"):
        """
        Places a stock buy or sell order.
        side: 'buy' or 'sell'
        trade_type: '0' for 지정가 (Limit Order), '3' for 시장가 (Market Order), '6' for 최유리지정가, etc.
        price: Required for limit order (trade_type = '0'). Leave 0/empty for market orders.
        """
        api_id = "kt10000" if side.lower() == "buy" else "kt10001"
        body = {
            "dmst_stex_tp": exchange,
            "stk_cd": stock_code,
            "ord_qty": str(quantity),
            "ord_uv": str(price) if price > 0 else "",
            "trde_tp": str(trade_type),
            "cond_uv": ""
        }
        res_data, _ = self._post(api_id, "/api/dostk/ordr", body)
        return {
            "ord_no": res_data.get("ord_no", ""),
            "dmst_stex_tp": res_data.get("dmst_stex_tp", ""),
            "return_code": res_data.get("return_code"),
            "return_msg": res_data.get("return_msg", "")
        }

    # 8. 주식 정정주문 (kt10002)
    def modify_order(self, orig_ord_no, stock_code, quantity, price, exchange="KRX"):
        """
        Modifies a pending order.
        quantity: New quantity (or 0 for entire remaining quantity).
        price: New price.
        """
        body = {
            "dmst_stex_tp": exchange,
            "orig_ord_no": orig_ord_no,
            "stk_cd": stock_code,
            "mdfy_qty": str(quantity),
            "mdfy_uv": str(price),
            "mdfy_cond_uv": ""
        }
        res_data, _ = self._post("kt10002", "/api/dostk/ordr", body)
        return {
            "ord_no": res_data.get("ord_no", ""),
            "base_orig_ord_no": res_data.get("base_orig_ord_no", ""),
            "mdfy_qty": parse_numeric(res_data.get("mdfy_qty")),
            "return_code": res_data.get("return_code"),
            "return_msg": res_data.get("return_msg", "")
        }

    # 9. 주식 취소주문 (kt10003)
    def cancel_order(self, orig_ord_no, stock_code, quantity=0, exchange="KRX"):
        """
        Cancels a pending order.
        quantity: Quantity to cancel (or 0 for entire remaining quantity).
        """
        body = {
            "dmst_stex_tp": exchange,
            "orig_ord_no": orig_ord_no,
            "stk_cd": stock_code,
            "cncl_qty": str(quantity)
        }
        res_data, _ = self._post("kt10003", "/api/dostk/ordr", body)
        return {
            "ord_no": res_data.get("ord_no", ""),
            "base_orig_ord_no": res_data.get("base_orig_ord_no", ""),
            "cncl_qty": parse_numeric(res_data.get("cncl_qty")),
            "return_code": res_data.get("return_code"),
            "return_msg": res_data.get("return_msg", "")
        }
