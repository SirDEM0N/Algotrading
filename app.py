import backtrader as bt
import pandas as pd
import yfinance as yf
from flask import Flask, jsonify, render_template
import threading
import time
import os

app = Flask(__name__)

# Global state
portfolio_value = 1000000
cerebro = bt.Cerebro()
cerebro.broker.setcash(portfolio_value)
cerebro.broker.setcommission(commission=0.001)

# Load data
TICKER = 'PICCADIL.BO'
df = yf.download(TICKER, period='7d', interval='5m', auto_adjust=False)
df.dropna(inplace=True)
df.columns = ['_'.join(col).strip() if isinstance(col, tuple) else col for col in df.columns]
df = df.drop(columns=[col for col in df.columns if 'Ticker' in col])
df.reset_index(inplace=True)
df['datetime'] = pd.to_datetime(df['Datetime'])
df.set_index('datetime', inplace=True)
TICKER = TICKER.upper()
df.columns = [col.replace(f"_{TICKER}", "").rstrip("_").lower() for col in df.columns]

# Define Strategy
class TestStrategy(bt.Strategy):
    def __init__(self):
        self.rsi = bt.indicators.RSI_SMA(self.data.close, period=14)

    def next(self):
        if not self.position:
            if self.rsi[0] < 30:
                self.buy()
        elif self.rsi[0] > 70:
            self.sell()

# Custom data feed class
class LiveFeed(bt.feeds.PandasData):
    params = (('datetime', None),)

# Add data to Cerebro
data = LiveFeed(dataname=df)
cerebro.adddata(data)
cerebro.addstrategy(TestStrategy)

# Run one bar at a time
class LiveEngine:
    def __init__(self):
        self.data = data
        self.strategy = None
        self.started = False

    def start(self):
        self.strategy = cerebro.run(runonce=False, stdstats=False)[0]
        self.started = True

    def step(self):
        try:
            if not self.data._state == self.data._OVER:
                self.data._advance()
                self.strategy.next()
                global portfolio_value
                portfolio_value = cerebro.broker.getvalue()
        except Exception as e:
            print("Step error:", e)

live_engine = LiveEngine()

# Background updater thread
def update_portfolio():
    live_engine.start()
    while True:
        live_engine.step()
        time.sleep(300)  # Update every 5 minutes

threading.Thread(target=update_portfolio, daemon=True).start()

# Flask routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/portfolio')
def get_portfolio():
    return jsonify({"portfolio_value": portfolio_value})

# For Render deployment
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
