# AutoStock - 키움 REST API 기반 주식 자동 매매 프로그램

이 프로젝트는 키움증권의 새로운 REST API 및 WebSocket 명세를 기반으로 작성된 국내주식 자동 매매 프로그램의 템플릿 프로젝트입니다.

---

## 📂 프로젝트 구조

```text
AutoStock/
│
├── config/
│   ├── kiwoom_rest_api_doc.xlsx     # 키움 REST API 상세 엑셀 명세서
│   ├── <account_id>_appkey.txt     # [Git 제외] 키움 Open API 앱키
│   ├── <account_id>_secretkey.txt  # [Git 제외] 키움 Open API 시크릿키
│   └── credentials.json            # [Git 제외] 로컬 토큰 캐시 파일
│
├── src/
│   ├── __init__.py
│   ├── config.py                   # 설정 모듈 (앱키 로드 및 서버 도메인 분기)
│   ├── auth.py                     # 인증 모듈 (Access Token 발급 및 자동 갱신)
│   ├── api.py                      # REST API 클라이언트 (계좌/주문/시세 조회 및 주문 전송)
│   └── websocket.py                # WebSocket 클라이언트 (실시간 시세/체결 및 잔고 수신)
│
├── venv/                           # Python 가상 환경 (Git 제외)
├── main.py                         # 프로그램 메인 진입점 및 흐름 제어 데모
├── requirements.txt                # 필요한 의존 라이브러리 목록
└── README.md                       # 프로젝트 설명 문서
```

---

## ⚙️ 개발 및 실행 환경 설정

### 1. 가상 환경 활성화 (Windows PowerShell 기준)
```powershell
.\venv\Scripts\Activate.ps1
```

### 2. 패키지 설치 확인
(이미 가상환경이 설정되고 패키지가 설치되어 있으므로, 추가 패키지가 필요할 때만 실행합니다.)
```powershell
pip install -r requirements.txt
```

### 3. 인증키 설정
`config/` 디렉토리 안에 다음 파일이 존재해야 합니다. (이 파일들은 `.gitignore`를 통해 Git 추적에서 자동 제외됩니다.)
* `<계좌번호>_appkey.txt`: 키움증권 Open API 콘솔에서 발급받은 App Key 입력
* `<계좌번호>_secretkey.txt`: 발급받은 Secret Key 입력
* *예시 파일명: `50148032_appkey.txt`, `50148032_secretkey.txt`*

### 4. 실운영 / 모의투자 설정
기본적으로 안전을 위해 **모의투자(Mock Trading)** 도메인으로 설정되어 있습니다. 
실거래를 원하시면 `src/config.py` 파일 내의 `IS_MOCK = True` 설정을 `IS_MOCK = False`로 변경하십시오.

---

## 🚀 실행 방법

```powershell
python main.py
```

### 실행 결과 데모
1. `config/` 디렉토리에 있는 앱키/시크릿키를 읽어와 `/oauth2/token` API로 토큰을 획득합니다.
2. 획득한 토큰을 `config/credentials.json`에 저장하여 유효기간(약 24시간) 동안 재사용합니다.
3. `/api/dostk/acnt` API를 통해 계좌 리스트를 조회하고 기본 계좌를 설정합니다.
4. 해당 계좌의 예수금 정보(`kt00001`) 및 보유 주식 잔고(`kt00018`)를 조회하여 화면에 출력합니다.
5. 웹소켓(`wss://...`) 연결을 시도하고, 삼성전자(`005930`)의 실시간 체결(`0B`) 및 호가잔량(`0D`)을 구독하여 30초간 화면에 출력한 뒤 안전하게 종료합니다.
