import os
import json
import logging
import requests
from datetime import datetime
from src import config

logger = logging.getLogger("AutoStock.Auth")

TOKEN_FILE = os.path.join(config.CONFIG_DIR, "credentials.json")

class TokenManager:
    def __init__(self):
        self.token = ""
        self.expires_dt = None
        self._load_token_from_cache()

    def _load_token_from_cache(self):
        """Loads cached token from disk if it exists."""
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.token = data.get("token", "")
                    expires_str = data.get("expires_dt", "")
                    if expires_str:
                        # Format is YYYYMMDDHHmmss
                        self.expires_dt = datetime.strptime(expires_str, "%Y%m%d%H%M%S")
                        logger.info(f"Loaded cached token. Expires at: {self.expires_dt}")
            except Exception as e:
                logger.warning(f"Failed to load token cache: {e}")

    def _save_token_to_cache(self, token, expires_str):
        """Saves token and expiration to credentials.json (git ignored)."""
        try:
            data = {
                "token": token,
                "expires_dt": expires_str
            }
            with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            logger.info("Saved new token to credentials.json cache.")
        except Exception as e:
            logger.error(f"Failed to cache token: {e}")

    def is_token_valid(self):
        """Checks if current token is loaded and not expired."""
        if not self.token or not self.expires_dt:
            return False
        # Add 1 minute buffer for safety
        now = datetime.now()
        return self.expires_dt > now

    def get_token(self):
        """Returns valid token, fetching a new one if necessary."""
        if self.is_token_valid():
            return self.token
        
        logger.info("Token expired or not found. Fetching new token from Kiwoom...")
        return self.refresh_token()

    def refresh_token(self):
        """Requests a new access token from the Kiwoom REST API."""
        if not config.APP_KEY or not config.SECRET_KEY:
            raise ValueError("APP_KEY or SECRET_KEY is missing. Check config files.")

        url = f"{config.BASE_URL}/oauth2/token"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "api-id": "au10001"
        }
        body = {
            "grant_type": "client_credentials",
            "appkey": config.APP_KEY,
            "secretkey": config.SECRET_KEY
        }

        try:
            response = requests.post(url, headers=headers, json=body, timeout=10)
            response.raise_for_status()
            res_data = response.json()
            
            return_code = res_data.get("return_code")
            return_msg = res_data.get("return_msg", "")
            
            if return_code != 0:
                raise RuntimeError(f"Kiwoom Token Error [{return_code}]: {return_msg}")

            token = res_data.get("token")
            expires_str = res_data.get("expires_dt")
            
            self.token = token
            self.expires_dt = datetime.strptime(expires_str, "%Y%m%d%H%M%S")
            self._save_token_to_cache(token, expires_str)
            
            logger.info("Successfully fetched and cached new token.")
            return self.token
            
        except Exception as e:
            logger.error(f"Failed to request Kiwoom access token: {e}")
            raise

    def revoke_token(self):
        """Revokes the current access token (optional clean-up)."""
        if not self.token:
            logger.info("No token to revoke.")
            return

        url = f"{config.BASE_URL}/oauth2/revoke"
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "api-id": "au10002"
        }
        body = {
            "appkey": config.APP_KEY,
            "secretkey": config.SECRET_KEY,
            "token": self.token
        }

        try:
            response = requests.post(url, headers=headers, json=body, timeout=10)
            response.raise_for_status()
            res_data = response.json()
            if res_data.get("return_code") == 0:
                logger.info("Token successfully revoked.")
                self.token = ""
                self.expires_dt = None
                if os.path.exists(TOKEN_FILE):
                    os.remove(TOKEN_FILE)
            else:
                logger.warning(f"Failed to revoke token: {res_data.get('return_msg')}")
        except Exception as e:
            logger.error(f"Failed to revoke token: {e}")
