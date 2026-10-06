from alpaca.trading.client import TradingClient
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("ALPACA_API_KEY")
secret_key = os.getenv("ALPACA_SECRET_KEY")
print(f"Key: {api_key}")
print(f"Secret: {secret_key}")
client = TradingClient(api_key, secret_key, paper=True)
print(client.get_account().status)
