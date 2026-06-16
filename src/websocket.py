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

    async def connect(self):
        """Establishes WebSocket connection to Kiwoom server."""
        if self.is_connected:
            logger.info("WebSocket is already connected.")
            return

        token = self.token_manager.get_token()
        # Connection URI
        uri = f"{config.WS_URL}/api/dostk/websocket"
        
        # Handshake headers
        headers = {
            "authorization": f"Bearer {token}"
        }

        try:
            logger.info(f"Connecting to WebSocket at {uri}...")
            self.ws = await websockets.connect(uri, extra_headers=headers)
            self.is_connected = True
            logger.info("WebSocket connection established successfully.")
            
            # Start message receiving loop
            self.running_task = asyncio.create_task(self._recv_loop())
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            self.is_connected = False
            raise

    async def disconnect(self):
        """Closes the WebSocket connection."""
        self.is_connected = False
        if self.running_task:
            self.running_task.cancel()
            try:
                await self.running_task
            except asyncio.CancelledError:
                pass
        
        if self.ws:
            await self.ws.close()
            self.ws = None
            logger.info("WebSocket connection closed.")

    async def _recv_loop(self):
        """Asynchronous loop to receive and process messages from Kiwoom."""
        try:
            while self.is_connected:
                message = await self.ws.recv()
                data = json.loads(message)
                
                # Check for heartbeat or system messages
                trnm = data.get("trnm", "")
                if trnm == "REAL":
                    # Real-time market/account data
                    if self.message_callback:
                        self.message_callback(data)
                    else:
                        logger.debug(f"Received real-time message: {data}")
                elif trnm in ["REG", "REMOVE"]:
                    # Response to subscribe/unsubscribe requests
                    logger.info(f"Subscription confirmation response: {data}")
                else:
                    logger.debug(f"Received WebSocket message: {data}")
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket connection closed unexpectedly: {e}")
        except Exception as e:
            logger.error(f"Error in WebSocket receive loop: {e}")
        finally:
            self.is_connected = False

    async def subscribe(self, item, sub_type, grp_no="1"):
        """
        Subscribes to real-time events for a stock code.
        item: Stock code (e.g. '005930' for Samsung Electronics, or empty '' for account events).
        sub_type: Event type (e.g. '0B' for trades, '0D' for order book, '00' for order status, '04' for balance).
        """
        if not self.is_connected:
            raise RuntimeError("WebSocket is not connected. Call connect() first.")

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

        logger.info(f"Subscribing to item={item}, type={sub_type}...")
        await self.ws.send(json.dumps(payload))
        self.subscriptions.add((item, sub_type))

    async def unsubscribe(self, item, sub_type, grp_no="1"):
        """Unsubscribes from real-time events for a stock code."""
        if not self.is_connected:
            raise RuntimeError("WebSocket is not connected.")

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

        logger.info(f"Unsubscribing from item={item}, type={sub_type}...")
        await self.ws.send(json.dumps(payload))
        self.subscriptions.discard((item, sub_type))
