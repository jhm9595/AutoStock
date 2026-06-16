import os
import glob
import logging

# Set up logging format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("AutoStock.Config")

# Base Directory Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE_DIR, 'config')

APP_KEY = ""
SECRET_KEY = ""
ACCOUNT_NO = ""

# Auto-detect keys from files matching <account>_appkey.txt and <account>_secretkey.txt
appkey_files = glob.glob(os.path.join(CONFIG_DIR, '*_appkey.txt'))
secretkey_files = glob.glob(os.path.join(CONFIG_DIR, '*_secretkey.txt'))

if appkey_files:
    appkey_path = appkey_files[0]
    filename = os.path.basename(appkey_path)
    ACCOUNT_NO = filename.split('_')[0]
    try:
        with open(appkey_path, 'r', encoding='utf-8') as f:
            APP_KEY = f.read().strip()
        logger.info(f"Loaded APP_KEY from {filename} for account {ACCOUNT_NO}")
    except Exception as e:
        logger.error(f"Failed to read appkey file: {e}")

if secretkey_files:
    secretkey_path = secretkey_files[0]
    try:
        with open(secretkey_path, 'r', encoding='utf-8') as f:
            SECRET_KEY = f.read().strip()
        logger.info(f"Loaded SECRET_KEY from {os.path.basename(secretkey_path)}")
    except Exception as e:
        logger.error(f"Failed to read secretkey file: {e}")

# Domains
MOCK_DOMAIN = "https://mockapi.kiwoom.com"
PROD_DOMAIN = "https://api.kiwoom.com"

MOCK_WS_DOMAIN = "wss://mockapi.kiwoom.com:10000"
PROD_WS_DOMAIN = "wss://api.kiwoom.com:10000"

# DEFAULT SETTING: Mock Trading (Safe for development)
# Change to False for Real Trading
IS_MOCK = True

BASE_URL = MOCK_DOMAIN if IS_MOCK else PROD_DOMAIN
WS_URL = MOCK_WS_DOMAIN if IS_MOCK else PROD_WS_DOMAIN

logger.info(f"Configuration initialized. Mode: {'Mock Trading' if IS_MOCK else 'Real Trading'}")
logger.info(f"REST URL: {BASE_URL} / WS URL: {WS_URL}")
