import backtrader as bt
import pandas as pd
import yfinance as yf
from flask import Flask, jsonify, render_template
import threading
import time

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
df['Datetime'] = pd.to_datetime(df['Datetime'])
df.set_index('Datetime', inplace=True)
TICKER = TICKER.upper()
df.columns = [col.replace(f"_{TICKER}", "").rstrip("_").lower() for col in df.columns]

# Define Strategy
class TestStrategy(bt.Strategy):
    def __init__(self):
        self.rsi = bt.indicators.RSI_SMA(self.data.close, period=14)

    def next(self):
        if not self.position:
            if self.rsi < 30:
                self.buy()
        elif self.rsi > 70:
            self.sell()

# Feed data one bar at a time
class LiveFeed(bt.feeds.PandasData):
    params = (('datetime', None),)

# Feed setup
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
        if self.started and not data._done:
            cerebro._runonce = False
            cerebro._exactbars = False
            data._advance()
            self.strategy.next()
            global portfolio_value
            portfolio_value = cerebro.broker.getvalue()

live_engine = LiveEngine()

# Background updater

def update_portfolio():
    live_engine.start()
    while True:
        live_engine.step()
        time.sleep(300)  # 5 minutes

threading.Thread(target=update_portfolio, daemon=True).start()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/portfolio')
def get_portfolio():
    return jsonify({"portfolio_value": portfolio_value})

if __name__ == '__main__':
    app.run(debug=False)