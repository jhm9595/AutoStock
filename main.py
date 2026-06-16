import asyncio
import logging
import sys
from src.config import IS_MOCK
from src.auth import TokenManager
from src.api import KiwoomClient
from src.websocket import KiwoomWebSocket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("autostock.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("AutoStock.Main")

def on_realtime_message(data):
    """Callback function executed when a real-time message is received from WebSocket."""
    values = data.get("values", {})
    item_code = data.get("item", "")
    type_code = data.get("type", "")
    name = data.get("name", "")
    
    if type_code == "0B": # 주식체결
        time = values.get("20", "")
        price = values.get("10", "")
        change = values.get("11", "")
        rate = values.get("12", "")
        volume = values.get("15", "")
        logger.info(f"[실시간 체결 | {name}] 종목코드: {item_code} | 체결시간: {time} | 현재가: {price} | 전일대비: {change} ({rate}%) | 체결량: {volume}")
    
    elif type_code == "0D": # 주식호가잔량
        time = values.get("21", "")
        ask1 = values.get("41", "")
        ask_qty1 = values.get("61", "")
        bid1 = values.get("51", "")
        bid_qty1 = values.get("71", "")
        logger.info(f"[실시간 호가 | {name}] 종목코드: {item_code} | 시간: {time} | 매도호가1: {ask1} ({ask_qty1}) | 매수호가1: {bid1} ({bid_qty1})")
        
    elif type_code == "00": # 주문체결 통보
        status = values.get("913", "")
        ord_no = values.get("9203", "")
        side = values.get("905", "")
        qty = values.get("900", "")
        price = values.get("901", "")
        logger.info(f"[주문체결 통보] 주문번호: {ord_no} | 구분: {side} | 상태: {status} | 수량: {qty} | 단가: {price}")
        
    elif type_code == "04": # 실시간 잔고 변동
        qty = values.get("930", "")
        buy_price = values.get("931", "")
        cur_price = values.get("10", "")
        logger.info(f"[잔고 변동] 종목코드: {item_code} | 보유수량: {qty} | 매입단가: {buy_price} | 현재가: {cur_price}")
        
    else:
        logger.info(f"[실시간 수신 | {type_code}] {data}")

async def main():
    logger.info("=========================================")
    logger.info("주식 자동 매매 프로그램 (AutoStock) 시작")
    logger.info(f"운영 모드: {'모의투자' if IS_MOCK else '실거래'}")
    logger.info("=========================================")
    
    try:
        # 1. 인증 및 토큰 매니저 초기화
        token_mgr = TokenManager()
        # Verify app credentials are loaded
        token = token_mgr.get_token()
        logger.info("성공적으로 키움 REST API 인증 토큰을 획득했습니다.")

        # 2. REST API 클라이언트 초기화
        client = KiwoomClient(token_mgr)
        
        # 3. 사용자 계좌번호 확인
        accounts = client.get_account_numbers()
        if not accounts:
            logger.warning("조회된 계좌번호가 없습니다. API 인증 정보를 다시 확인해 주세요.")
            return
            
        # 첫 번째 계좌 선택
        primary_account = accounts[0]
        logger.info(f"기본 거래 계좌 설정 완료: {primary_account}")

        # 4. 계좌 예수금 및 잔고 조회 데모
        logger.info("계좌 예수금 조회 중...")
        try:
            deposit_info = client.get_deposit_details()
            logger.info(f"예수금(출금가능금액): {deposit_info.get('pymn_alow_amt', 0):,} 원")
            logger.info(f"주문가능금액: {deposit_info.get('ord_alow_amt', 0):,} 원")
        except Exception as e:
            logger.warning(f"예수금 조회 실패: {e}. 모의투자 계좌 등록여부를 확인하세요.")

        logger.info("계좌 평가잔고 내역 조회 중...")
        try:
            balance_info = client.get_account_balance()
            logger.info(f"총 매입금액: {balance_info.get('tot_pur_amt', 0):,} 원")
            logger.info(f"총 평가금액: {balance_info.get('tot_evlt_amt', 0):,} 원")
            logger.info(f"총 평가손익: {balance_info.get('tot_evlt_pl', 0):,} 원 ({balance_info.get('tot_prft_rt', 0)}%)")
            
            holdings = balance_info.get("holdings", [])
            logger.info(f"보유 종목 수: {len(holdings)}")
            for idx, item in enumerate(holdings, 1):
                logger.info(f"  [{idx}] {item['stk_nm']}({item['stk_cd']}): 보유={item['rmnd_qty']} | 매입가={item['pur_pric']:,} | 현재가={item['cur_prc']:,} | 수익률={item['prft_rt']}%")
        except Exception as e:
            logger.warning(f"잔고 내역 조회 실패: {e}")

        # 5. 실시간 WebSocket 연결 및 구독 데모
        ws_client = KiwoomWebSocket(token_mgr, message_callback=on_realtime_message)
        await ws_client.connect()
        
        # 예시로 '삼성전자(005930)'의 실시간 체결(0B) 및 호가잔량(0D) 구독 등록
        # 계좌 관련 주문체결(00) 및 잔고(04)는 종목코드 없이 공란으로 자동 등록됩니다.
        sample_stock = "005930"
        
        logger.info(f"실시간 시세 수신 시작 ({sample_stock} - 삼성전자)...")
        await ws_client.subscribe(sample_stock, "0B") # 주식체결
        await ws_client.subscribe(sample_stock, "0D") # 주식호가잔량
        await ws_client.subscribe("", "00")          # 주문체결 통보 (계좌 전체)
        await ws_client.subscribe("", "04")          # 잔고 변동 통보 (계좌 전체)
        
        # 프로그램 유지 (테스트용으로 30초 대기 후 종료)
        # 무한 대기가 필요할 경우 while True: await asyncio.sleep(1) 형태로 구성
        logger.info("실시간 데이터를 30초간 수신합니다. (Ctrl+C를 누르면 즉시 종료됩니다)")
        await asyncio.sleep(30)
        
        # 구독 해제 및 종료
        logger.info("실시간 구독을 해제합니다...")
        await ws_client.unsubscribe(sample_stock, "0B")
        await ws_client.unsubscribe(sample_stock, "0D")
        await ws_client.unsubscribe("", "00")
        await ws_client.unsubscribe("", "04")
        
        await ws_client.disconnect()
        logger.info("WebSocket 연결이 안전하게 종료되었습니다.")

    except asyncio.CancelledError:
        logger.info("비동기 작업이 취소되었습니다.")
    except KeyboardInterrupt:
        logger.info("사용자 중단 요청 감지.")
    except Exception as e:
        logger.critical(f"프로그램 실행 중 치명적인 오류 발생: {e}", exc_info=True)
    finally:
        logger.info("주식 자동 매매 프로그램 종료.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("프로그램이 사용자에 의해 종료되었습니다.")
