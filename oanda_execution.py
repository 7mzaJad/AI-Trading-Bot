import logging
import requests
from config import Config

logger = logging.getLogger(__name__)

class OandaExecutionManager:
    def __init__(self):
        Config.validate()
        self.api_key = Config.OANDA_API_KEY
        self.account_id = Config.OANDA_ACCOUNT_ID
        env = Config.OANDA_ENVIRONMENT.lower()
        self.base_url = "https://api-fxtrade.oanda.com/v3" if env == "live" else "https://api-fxpractice.oanda.com/v3"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Test connection
        if self.api_key and self.account_id:
            account = self.get_account_status()
            if account:
                logger.info("Successfully connected to OANDA API.")

    def get_account_status(self):
        url = f"{self.base_url}/accounts/{self.account_id}/summary"
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            logger.error(f"Failed to get OANDA account info: {response.text}")
            return None
            
        data = response.json().get('account', {})
        return {
            "equity": float(data.get('NAV', 0)),
            "balance": float(data.get('balance', 0)),
            "margin_free": float(data.get('marginAvailable', 0))
        }

    def get_positions(self, symbol: str):
        url = f"{self.base_url}/accounts/{self.account_id}/positions/{symbol}"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            pos = response.json().get('position', {})
            long_units = abs(float(pos.get('long', {}).get('units', 0)))
            short_units = abs(float(pos.get('short', {}).get('units', 0)))
            return long_units > 0 or short_units > 0
        return False

    def calculate_units(self, symbol: str, sl_price: float, current_price: float, equity: float) -> int:
        """
        Calculates OANDA units to risk exactly MAX_RISK_PERCENT of account equity.
        For XAU_USD, 1 unit = 1 ounce.
        """
        risk_amount = equity * Config.MAX_RISK_PERCENT
        price_diff = abs(current_price - sl_price)
        
        if price_diff <= 0:
            return 0
            
        units = int(risk_amount / price_diff)
        return units

    def execute_trade(self, symbol: str, evaluation: dict, current_price: float):
        decision = evaluation.get("decision", "HOLD")
        if decision == "HOLD":
            return False

        account = self.get_account_status()
        if not account:
            return False
            
        if self.get_positions(symbol):
            logger.info(f"Already hold open position(s) for {symbol}. Skipping new entry.")
            return False

        sl_price = float(evaluation.get("stop_loss_price", 0.0))
        tp_price = float(evaluation.get("take_profit_price", 0.0))
        
        units = self.calculate_units(symbol, sl_price, current_price, account['equity'])
        
        if units <= 0:
            logger.warning(f"Calculated units for {symbol} is 0. Aborting.")
            return False

        # OANDA requires negative units for short
        if decision == "SELL":
            units = -units

        order_payload = {
            "order": {
                "units": str(units),
                "instrument": symbol,
                "timeInForce": "FOK",
                "type": "MARKET",
                "positionFill": "DEFAULT",
                "stopLossOnFill": {
                    "price": f"{sl_price:.3f}"
                },
                "takeProfitOnFill": {
                    "price": f"{tp_price:.3f}"
                }
            }
        }

        logger.info(f"Sending OANDA {decision} order for {abs(units)} units of {symbol}. SL: {sl_price}, TP: {tp_price}")
        
        url = f"{self.base_url}/accounts/{self.account_id}/orders"
        response = requests.post(url, headers=self.headers, json=order_payload)
        
        if response.status_code not in [200, 201]:
            logger.error(f"OANDA Order failed: {response.text}")
            return False
            
        res_data = response.json()
        order_id = res_data.get('orderCreateTransaction', {}).get('id', 'Unknown')
        
        logger.info(f"Successfully opened {decision} position for {symbol}. Order ID: {order_id}")
        
        # Send Email Alert
        self.send_email_alert(
            subject=f"OANDA AI Bot: {decision} {symbol}",
            body=f"Order executed: {decision} {abs(units)} units of {symbol} at ~{current_price}.\nStop Loss: {sl_price}\nTake Profit: {tp_price}\nOrder ID: {order_id}"
        )
        return True

    def send_email_alert(self, subject: str, body: str):
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        sender = Config.EMAIL_SENDER
        password = Config.EMAIL_PASSWORD
        receiver = Config.EMAIL_RECEIVER
        
        if not sender or not password or not receiver:
            return
            
        try:
            msg = MIMEMultipart()
            msg['From'] = sender
            msg['To'] = receiver
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
            server.quit()
            logger.info(f"Successfully sent email alert: {subject}")
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")

    def shutdown(self):
        pass
