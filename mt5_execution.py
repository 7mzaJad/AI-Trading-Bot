import logging
import MetaTrader5 as mt5
from config import Config

logger = logging.getLogger(__name__)

class MT5ExecutionManager:
    def __init__(self):
        Config.validate()
        
        login = int(Config.MT5_LOGIN) if Config.MT5_LOGIN else 0
        password = Config.MT5_PASSWORD
        server = Config.MT5_SERVER

        # Try to initialize MT5 explicitly targeting the default path
        mt5_path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
        init_success = mt5.initialize(path=mt5_path)
        
        if not init_success:
            logger.warning(f"Initial MT5 bind returned {mt5.last_error()}, attempting explicit login anyway...")

        if login and password and server:
            authorized = mt5.login(login, password=password, server=server)
            if not authorized:
                raise ValueError(f"MT5 login failed, error code: {mt5.last_error()}")
        
        logger.info("Successfully connected to MetaTrader 5.")

    def get_account_status(self):
        account_info = mt5.account_info()
        if account_info is None:
            raise ValueError(f"Failed to get MT5 account info, error code: {mt5.last_error()}")
        
        return {
            "equity": account_info.equity,
            "balance": account_info.balance,
            "margin_free": account_info.margin_free
        }

    def calculate_lot_size(self, symbol: str, sl_price: float, current_price: float, equity: float) -> float:
        """
        Calculates exact lot size to risk exactly MAX_RISK_PERCENT of account equity.
        """
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logger.error(f"{symbol} not found in MT5.")
            return 0.0

        risk_amount = equity * Config.MAX_RISK_PERCENT
        
        # Price distance
        price_diff = abs(current_price - sl_price)
        if price_diff <= 0:
            return 0.0
            
        # Standard calculation: Risk = Lots * ContractSize * PriceDiff
        # Lots = Risk / (ContractSize * PriceDiff)
        contract_size = symbol_info.trade_contract_size
        
        if contract_size == 0:
            contract_size = 100 # Standard fallback for Gold

        lots = risk_amount / (price_diff * contract_size)
        
        # Floor to minimum volume step (e.g., 0.01)
        min_vol = symbol_info.volume_min
        step_vol = symbol_info.volume_step
        
        lots = max(min_vol, round(lots / step_vol) * step_vol)
        lots = min(lots, symbol_info.volume_max)
        
        return float(lots)

    def execute_trade(self, symbol: str, evaluation: dict, current_price: float):
        decision = evaluation.get("decision", "HOLD")
        if decision == "HOLD":
            return False

        account = self.get_account_status()
        
        # Check if we already have an open position on this symbol
        positions = mt5.positions_get(symbol=symbol)
        if positions is None:
            logger.error(f"Error checking positions for {symbol}, error code: {mt5.last_error()}")
            return False
            
        if len(positions) > 0:
            logger.info(f"Already hold open position(s) for {symbol}. Skipping new entry.")
            return False

        sl_price = float(evaluation.get("stop_loss_price", 0.0))
        tp_price = float(evaluation.get("take_profit_price", 0.0))
        
        lots = self.calculate_lot_size(symbol, sl_price, current_price, account['equity'])
        
        if lots <= 0:
            logger.warning(f"Calculated lot size for {symbol} is 0 or invalid. Aborting.")
            return False

        order_type = mt5.ORDER_TYPE_BUY if decision == "BUY" else mt5.ORDER_TYPE_SELL
        action_type = mt5.TRADE_ACTION_DEAL
        
        symbol_info = mt5.symbol_info(symbol)
        price = symbol_info.ask if order_type == mt5.ORDER_TYPE_BUY else symbol_info.bid

        request = {
            "action": action_type,
            "symbol": symbol,
            "volume": lots,
            "type": order_type,
            "price": price,
            "sl": sl_price,
            "tp": tp_price,
            "deviation": 20,
            "magic": 234000,
            "comment": "AI Bot XAUUSD",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        logger.info(f"Sending {decision} order for {lots} lots of {symbol}. SL: {sl_price}, TP: {tp_price}")
        
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order failed, retcode={result.retcode}")
            return False
            
        logger.info(f"Successfully opened {decision} position for {symbol}. Ticket: {result.order}")
        
        # Send Email Alert
        self.send_email_alert(
            subject=f"MT5 AI Bot: {decision} {symbol}",
            body=f"Order executed: {decision} {lots} lots of {symbol} at {price}.\nStop Loss: {sl_price}\nTake Profit: {tp_price}\nTicket: {result.order}"
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
        mt5.shutdown()
