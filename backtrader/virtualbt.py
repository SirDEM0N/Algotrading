import backtrader as bt
import yfinance as yf
import pandas as pd
import numpy as np
import ta
from datetime import datetime
from scipy.signal import argrelextrema
# === Fetch and clean data ===
print("\n" + "=" * 30)
print(f"Running virtual session at {datetime.now()}")
print("=" * 30)

ticker = 'PICCADIL.BO'
df = yf.download(ticker, period='7d', interval='5m', auto_adjust=False)

df.dropna(inplace=True)
df.columns = ['_'.join(col).strip() if isinstance(col, tuple) else col for col in df.columns]
df = df.drop(columns=[col for col in df.columns if 'Ticker' in col])

# Ensure 'Datetime' is the index and convert it to datetime
df.reset_index(inplace=True)

# Convert 'Datetime' to datetime and set it as the index
df['Datetime'] = pd.to_datetime(df['Datetime'], unit='ms')
df.set_index('Datetime', inplace=True)

# Update columns for consistency
ticker = ticker.upper()
df.columns = [col.replace(f"_{ticker}", "").rstrip("_").lower() for col in df.columns]

# === Add indicators ===
df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
df['momentum'] = df['close'] - df['close'].shift(10)
df['avg_vol'] = df['volume'].rolling(50).mean()
df['rsi_prev'] = df['rsi'].shift(1)
df['momentum_prev'] = df['momentum'].shift(1)
df.dropna(inplace=True)

# === Dynamic Thresholds ===
def get_peaks_and_valleys(series, order=5):
    max_idx = argrelextrema(series.values, np.greater_equal, order=order)[0]
    min_idx = argrelextrema(series.values, np.less_equal, order=order)[0]
    return series.iloc[max_idx], series.iloc[min_idx]

last_3_days = df.tail(3 * 78 * 24)  # approx 3 days of 5min data

momentum_peaks, momentum_valleys = get_peaks_and_valleys(last_3_days['momentum'], order=5)
rsi_peaks, rsi_valleys = get_peaks_and_valleys(last_3_days['rsi'], order=5)

momentum_buy_threshold = momentum_valleys.mean() * 0.8
momentum_sell_threshold = momentum_peaks.mean() * 0.6
rsi_buy_threshold = rsi_valleys.mean() * 0.8
rsi_sell_threshold = rsi_peaks.mean() * 0.6

print("\n=== Dynamic Thresholds ===")
print(f"Momentum Buy Threshold: {momentum_buy_threshold:.2f}")
print(f"Momentum Sell Threshold: {momentum_sell_threshold:.2f}")
print(f"RSI Buy Threshold: {rsi_buy_threshold:.2f}")
print(f"RSI Sell Threshold: {rsi_sell_threshold:.2f}")

# === Define Backtrader Strategy ===
class RSIMomentumStrategy(bt.Strategy):
    def __init__(self):
        self.buy_signal = self.datas[0].close * 0
        self.sell_signal = self.datas[0].close * 0

    def next(self):
        i = len(self) - 1
        data = self.datas[0]

        mom = data.lines.momentum[0]
        mom_prev = data.lines.momentum_prev[0]
        rsi = data.lines.rsi[0]
        rsi_prev = data.lines.rsi_prev[0]
        vol = data.lines.volume[0]
        avg_vol = data.lines.avg_vol[0]

        # Buy signal
        if (
            mom_prev < momentum_buy_threshold and mom > mom_prev and
            rsi_prev < rsi_buy_threshold and rsi > rsi_prev and
            vol < avg_vol
        ):
            if not self.position:
                self.buy()

        # Sell signal
        elif (
            mom_prev > momentum_sell_threshold and mom < mom_prev and
            rsi_prev > rsi_sell_threshold and rsi < rsi_prev and
            vol < avg_vol * 1.2
        ):
            if self.position:
                self.sell()

# === Extend data feed to support custom columns ===
class CustomPandas(bt.feeds.PandasData):
    lines = ('momentum', 'momentum_prev', 'rsi', 'rsi_prev', 'avg_vol')
    params = (
        ('momentum', -1),
        ('momentum_prev', -1),
        ('rsi', -1),
        ('rsi_prev', -1),
        ('avg_vol', -1),
    )

# === Set up Backtrader engine ===
cerebro = bt.Cerebro()
data = CustomPandas(dataname=df, timeframe=bt.TimeFrame.Minutes, compression=5)
cerebro.adddata(data)
cerebro.addstrategy(RSIMomentumStrategy)
cerebro.broker.set_cash(100000)
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

# === Run Backtest ===
results = cerebro.run()
strat = results[0]

# === Print Metrics ===
print("\n===== Strategy Performance Metrics =====")
print(f"Final Portfolio Value: {cerebro.broker.getvalue():.2f}")
print(f"Sharpe Ratio: {strat.analyzers.sharpe.get_analysis().get('sharperatio')}")
print(f"Max Drawdown: {strat.analyzers.drawdown.get_analysis()['max']['drawdown']:.2f}%")
trades = strat.analyzers.trades.get_analysis()
print(f"Total Trades: {trades.total.closed}")
print(f"Winning Trades: {trades.won.total}")
print(f"Win Rate: {(trades.won.total / trades.total.closed) * 100:.2f}%" if trades.total.closed else "No trades")

# === Plot (optional) ===
# cerebro.plot()
