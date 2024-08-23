import numpy as np
import pandas as pd
import pandas_ta as ta
from datetime import datetime
from collections import deque
import asyncio
import websockets
import json
from flask import Flask, render_template_string
from threading import Thread
import subprocess

# Customizable variables
Timeframe = '5m'
ema_period_5 = 5
ema_period_15 = 15
rsi_period = 3
rsi_overbought = 70
rsi_oversold = 30

# Add the Pair variable
Pairs = ["BNBUSDT"]

app = Flask(__name__)

def calculate_indicators(prices):
    df = pd.DataFrame(prices, columns=['close'])
    df['ema_5'] = ta.ema(df['close'], length=ema_period_5)
    df['ema_15'] = ta.ema(df['close'], length=ema_period_15)
    df['rsi'] = ta.rsi(df['close'], length=rsi_period)
    return df.iloc[-1]

class TradingStrategy:
    def __init__(self, pairs):
        self.pairs = pairs
        self.close_prices = {pair: deque(maxlen=ema_period_15) for pair in pairs}
        self.bot_status = "Bot is running..."

    def run_bnb_long(self):
        try:
            subprocess.Popen(["python", "bnb_long.py"])
            print("Running bnb_long.py")
        except Exception as e:
            print(f"Error running bnb_long.py: {e}")

    def run_bnb_short(self):
        try:
            subprocess.Popen(["python", "bnb_short.py"])
            print("Running bnb_short.py")
        except Exception as e:
            print(f"Error running bnb_short.py: {e}")

    def process_price(self, pair, timestamp, open_price, high_price, low_price, close_price, volume, is_closed):
        if is_closed:
            self.close_prices[pair].append(close_price)

        if len(self.close_prices[pair]) == ema_period_15:
            indicators = calculate_indicators(list(self.close_prices[pair]))
            ema_5 = indicators['ema_5']
            ema_15 = indicators['ema_15']
            rsi = indicators['rsi']

            if is_closed:
                if self.check_long_entry(ema_5, ema_15, rsi):
                    self.run_bnb_long()
                elif self.check_short_entry(ema_5, ema_15, rsi):
                    self.run_bnb_short()

    def check_long_entry(self, ema_5, ema_15, rsi):
        if ema_5 < ema_15 and rsi > rsi_overbought:
            return True
        return False

    def check_short_entry(self, ema_5, ema_15, rsi):
        if ema_5 > ema_15 and rsi < rsi_oversold:
            return True
        return False

strategy = TradingStrategy(Pairs)

@app.route('/')
def index():
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Trading Bot Status</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding-top: 50px; }
            .status { font-size: 24px; font-weight: bold; }
        </style>
        <script>
            function refreshPage() {
                location.reload();
            }
            setInterval(refreshPage, 5000);
        </script>
    </head>
    <body>
        <div class="status">{{ bot_status }}</div>
    </body>
    </html>
    '''
    return render_template_string(template, bot_status=strategy.bot_status)

async def connect_to_binance_futures():
    uri = f"wss://fstream.binance.com/stream?streams={'/'.join([pair.lower() + '@kline_' + Timeframe for pair in Pairs])}"

    async with websockets.connect(uri) as websocket:
        print("Connected to Binance Futures WebSocket")

        while True:
            message = await websocket.recv()
            process_message(json.loads(message))

def process_message(message):
    stream = message['stream']
    pair = stream.split('@')[0].upper()
    data = message['data']
    candle = data['k']

    open_time = datetime.fromtimestamp(candle['t'] / 1000)
    open_price = float(candle['o'])
    high_price = float(candle['h'])
    low_price = float(candle['l'])
    close_price = float(candle['c'])
    volume = float(candle['v'])
    is_closed = candle['x']

    strategy.process_price(pair, open_time, open_price, high_price, low_price, close_price, volume, is_closed)

def run_flask():
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    asyncio.get_event_loop().run_until_complete(connect_to_binance_futures())
