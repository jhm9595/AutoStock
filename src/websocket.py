import json
import asyncio
import logging
import websockets
from src import config

logger = logging.getLogger("AutoStock.WS")

class KiwoomWebSocket:
    def __init__(self, token_manager, message_callback=None):
        self.token_manager = token_manager
        self.message_callback = message_callback
        self.ws = None
        self.is_connected = False
        self.running_task = None
        self.subscriptions = set() # Keeps track of active subscriptions: (item, type)
        self._pending_responses = {} # key -> asyncio.Future

    async def connect(self):
        """Kiwoom 서버에 WebSocket 연결을 수립합니다."""
        if self.is_connected:
            logger.info("WebSocket이 이미 연결되어 있습니다.")
            return

        token = self.token_manager.get_token()
        uri = f"{config.WS_URL}/api/dostk/websocket"

        try:
            logger.info(f"WebSocket 연결 시도 중: {uri}")
            # extra_headers 없이 연결 (asyncio 라이브러리 충돌 방지)
            self.ws = await websockets.connect(uri)
            self.is_connected = True
            logger.info("WebSocket TCP 연결 완료. LOGIN 패킷 전송 중...")
            
            # 메시지 수신 루프 시작
            self.running_task = asyncio.create_task(self._recv_loop())
            
            # LOGIN 패킷 즉시 전송 후 응답 대기
            login_payload = {
                "trnm": "LOGIN",
                "token": token
            }
            login_res = await self._send_request_and_wait("LOGIN", login_payload, key="LOGIN", timeout=5.0)
            
            if login_res.get("return_code") != 0:
                err_msg = login_res.get("return_msg", "알 수 없는 로그인 오류")
                logger.error(f"WebSocket LOGIN 핸드셰이크 실패: {err_msg}")
                self.is_connected = False
                await self.ws.close()
                self.ws = None
                raise RuntimeError(f"WebSocket 로그인 핸드셰이크 실패: {err_msg}")
                
            logger.info("WebSocket 연결 및 LOGIN 핸드셰이크 성공적으로 완료.")
            
            # 재연결 시 기존 구독 항목 복구
            if self.subscriptions:
                logger.info(f"기존 구독 {len(self.subscriptions)}건 재등록 중...")
                for item, sub_type in list(self.subscriptions):
                    await self._send_subscribe_packet(item, sub_type)
                    
        except Exception as e:
            logger.error(f"WebSocket 연결 또는 로그인 실패: {e}")
            self.is_connected = False
            if self.running_task:
                self.running_task.cancel()
                self.running_task = None
            if self.ws:
                await self.ws.close()
                self.ws = None
            raise

    async def disconnect(self):
        """WebSocket 연결을 종료합니다."""
        self.is_connected = False
        if self.running_task:
            self.running_task.cancel()
            try:
                await self.running_task
            except asyncio.CancelledError:
                pass
            self.running_task = None
        
        if self.ws:
            await self.ws.close()
            self.ws = None
            logger.info("WebSocket 연결이 종료되었습니다.")

    async def _send_request_and_wait(self, trnm, payload, key, timeout=5.0):
        """WebSocket으로 요청 패킷을 전송하고 지정된 응답 키를 기다립니다."""
        if not self.is_connected or not self.ws:
            raise RuntimeError("WebSocket이 연결되어 있지 않습니다.")
            
        fut = asyncio.get_running_loop().create_future()
        self._pending_responses[key] = fut
        
        try:
            await self.ws.send(json.dumps(payload))
            logger.debug(f"WS 요청 전송 [{trnm}] 키:[{key}]: {payload}")
            response = await asyncio.wait_for(fut, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.error(f"WS 응답 대기 시간 초과 - 키: [{key}]")
            raise TimeoutError(f"WebSocket response timeout for key [{key}]")
        finally:
            self._pending_responses.pop(key, None)

    async def _recv_loop(self):
        """키움 서버로부터 메시지를 수신하고 처리하는 비동기 루프."""
        try:
            while self.is_connected:
                message = await self.ws.recv()
                data = json.loads(message)
                
                trnm = data.get("trnm", "")
                if trnm == "REAL":
                    # 실시간 시세/계좌/조건검색 데이터
                    if self.message_callback:
                        self.message_callback(data)
                    else:
                        logger.debug(f"실시간 메시지 수신: {data}")
                elif trnm == "LOGIN":
                    logger.info("WS LOGIN 응답 수신.")
                    fut = self._pending_responses.get("LOGIN")
                    if fut and not fut.done():
                        fut.set_result(data)
                elif trnm == "CNSRLST":
                    logger.info("WS CNSRLST(조건식 목록) 응답 수신.")
                    fut = self._pending_responses.get("CNSRLST")
                    if fut and not fut.done():
                        fut.set_result(data)
                elif trnm == "CNSRREQ":
                    seq = str(data.get("seq", ""))
                    logger.info(f"WS CNSRREQ(조건검색 등록) 응답 수신 - seq: {seq}")
                    fut = self._pending_responses.get(f"CNSRREQ:{seq}")
                    if fut and not fut.done():
                        fut.set_result(data)
                elif trnm == "CNSRCLR":
                    seq = str(data.get("seq", ""))
                    logger.info(f"WS CNSRCLR(조건검색 해제) 응답 수신 - seq: {seq}")
                    fut = self._pending_responses.get(f"CNSRCLR:{seq}")
                    if fut and not fut.done():
                        fut.set_result(data)
                elif trnm == "PING":
                    # PING에 수신 데이터 그대로 응답
                    logger.debug("WS PING 수신. PONG 전송 중...")
                    await self.ws.send(json.dumps(data))
                elif trnm in ["REG", "REMOVE"]:
                    logger.info(f"구독 처리 결과 수신: {data}")
                else:
                    logger.debug(f"WS 메시지 수신: {data}")
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket 연결이 예기치 않게 종료되었습니다: {e}")
        except Exception as e:
            logger.error(f"WebSocket 수신 루프 오류: {e}")
        finally:
            self.is_connected = False
            # 대기 중인 모든 Future를 예외로 처리하여 호출 측이 무한 대기하지 않도록 함
            for fut in self._pending_responses.values():
                if not fut.done():
                    fut.set_exception(RuntimeError("요청 처리 중 WebSocket 연결이 끊겼습니다."))
            self._pending_responses.clear()

    # 1. Condition Search Methods (ka10171, ka10173, ka10174 equivalents)
    async def get_condition_list(self):
        """Retrieves user's registered condition search list from Kiwoom via WebSocket."""
        payload = {
            "trnm": "CNSRLST"
        }
        res = await self._send_request_and_wait("CNSRLST", payload, key="CNSRLST", timeout=5.0)
        if res.get("return_code") != 0:
            raise RuntimeError(res.get("return_msg", "Failed to retrieve condition list"))
            
        raw_list = res.get("data", [])
        conditions = []
        for item in raw_list:
            if isinstance(item, list) and len(item) >= 2:
                conditions.append({
                    "id": str(item[0]),
                    "name": str(item[1])
                })
            elif isinstance(item, dict):
                conditions.append({
                    "id": str(item.get("seq", "")),
                    "name": str(item.get("name", ""))
                })
        return conditions

    async def request_condition_realtime(self, seq):
        """Requests real-time tracking for a specific condition formula via WebSocket."""
        payload = {
            "trnm": "CNSRREQ",
            "seq": str(seq),
            "search_type": "1",
            "stex_tp": "K"
        }
        res = await self._send_request_and_wait("CNSRREQ", payload, key=f"CNSRREQ:{seq}", timeout=5.0)
        if res.get("return_code") != 0:
            raise RuntimeError(res.get("return_msg", "Failed to register realtime condition"))
        return res

    async def cancel_condition_realtime(self, seq):
        """Cancels real-time tracking for a specific condition formula via WebSocket."""
        payload = {
            "trnm": "CNSRCLR",
            "seq": str(seq)
        }
        res = await self._send_request_and_wait("CNSRCLR", payload, key=f"CNSRCLR:{seq}", timeout=5.0)
        if res.get("return_code") != 0:
            raise RuntimeError(res.get("return_msg", "Failed to cancel realtime condition"))
        return res

    async def query_condition_once(self, seq):
        """[ka10172] 조건검색 요청 일반 - 실시간 등록 없이 현재 시점의 조건 충족 종목을 일회성 조회.

        실시간 등록(request_condition_realtime)과 달리 단순 조회만 하고 끝납니다.
        Response data 예시: [{"stk_cd": "005930", "stk_nm": "삼성전자"}, ...]

        Args:
            seq: 조건검색식 일련번호 (get_condition_list()의 'id' 값)

        Returns:
            dict with keys: return_code, return_msg, trnm, data (list of stocks)
        """
        payload = {
            "trnm": "CNSRREQ",
            "seq": str(seq),
            "search_type": "0"  # 0: 일반(일회성), 1: 실시간 등록
        }
        res = await self._send_request_and_wait("CNSRREQ", payload, key=f"CNSRREQ:{seq}", timeout=10.0)
        if res.get("return_code") != 0:
            raise RuntimeError(res.get("return_msg", "Failed to query condition"))
        return res

    # 2. General Real-time Data Subscription Methods (REG, REMOVE)
    async def _send_subscribe_packet(self, item, sub_type, grp_no="1"):
        payload = {
            "trnm": "REG",
            "grp_no": grp_no,
            "refresh": "1",
            "data": [
                {
                    "item": [item],
                    "type": [sub_type]
                }
            ]
        }
        await self.ws.send(json.dumps(payload))

    async def subscribe(self, item, sub_type, grp_no="1"):
        """종목코드에 대한 실시간 이벤트를 구독합니다."""
        if not self.is_connected:
            raise RuntimeError("WebSocket이 연결되어 있지 않습니다.")
        await self._send_subscribe_packet(item, sub_type, grp_no)
        self.subscriptions.add((item, sub_type))

    async def unsubscribe(self, item, sub_type, grp_no="1"):
        """종목코드에 대한 실시간 이벤트 구독을 해제합니다."""
        if not self.is_connected:
            raise RuntimeError("WebSocket이 연결되어 있지 않습니다.")
        payload = {
            "trnm": "REMOVE",
            "grp_no": grp_no,
            "refresh": "1",
            "data": [
                {
                    "item": [item],
                    "type": [sub_type]
                }
            ]
        }
        await self.ws.send(json.dumps(payload))
        self.subscriptions.discard((item, sub_type))
