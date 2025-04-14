import backtrader as bt
import pandas as pd

class RSIMomentumStrategy(bt.Strategy):
    params = dict(
        rsi_window=14,
        momentum_shift=10,
        volume_window=50,
        peak_valley_order=5
    )

    def __init__(self):
        self.rsi = bt.indicators.RSI(self.data.close, period=self.p.rsi_window)
        self.momentum = self.data.close - self.data.close(-self.p.momentum_shift)
        self.avg_vol = bt.indicators.SimpleMovingAverage(self.data.volume, period=self.p.volume_window)

        self.momentum_prev = self.momentum(-1)
        self.rsi_prev = self.rsi(-1)

        self.order = None

    def next(self):
        if len(self.data) < self.p.volume_window + self.p.momentum_shift:
            return

        # Dynamic threshold estimation from past 3 days
        df = pd.DataFrame({
            'momentum': self.momentum.get(size=400),
            'rsi': self.rsi.get(size=400)
        })
        df.dropna(inplace=True)

        def get_extremes(series, order):
            from scipy.signal import argrelextrema
            max_idx = argrelextrema(series.values, np.greater_equal, order=order)[0]
            min_idx = argrelextrema(series.values, np.less_equal, order=order)[0]
            return series.iloc[max_idx], series.iloc[min_idx]

        momentum_peaks, momentum_valleys = get_extremes(df['momentum'], self.p.peak_valley_order)
        rsi_peaks, rsi_valleys = get_extremes(df['rsi'], self.p.peak_valley_order)

        if len(momentum_peaks) == 0 or len(momentum_valleys) == 0 or len(rsi_peaks) == 0 or len(rsi_valleys) == 0:
            return

        momentum_buy_threshold = momentum_valleys.mean() * 0.8
        momentum_sell_threshold = momentum_peaks.mean() * 0.6
        rsi_buy_threshold = rsi_valleys.mean() * 0.8
        rsi_sell_threshold = rsi_peaks.mean() * 0.6

        # Entry logic
        if not self.position:
            if (
                self.momentum_prev[0] < momentum_buy_threshold and
                self.momentum[0] > self.momentum_prev[0] and
                self.rsi_prev[0] < rsi_buy_threshold and
                self.rsi[0] > self.rsi_prev[0] and
                self.data.volume[0] < self.avg_vol[0]
            ):
                self.buy()
        else:
            if (
                self.momentum_prev[0] > momentum_sell_threshold and
                self.momentum[0] < self.momentum_prev[0] and
                self.rsi_prev[0] > rsi_sell_threshold and
                self.rsi[0] < self.rsi_prev[0] and
                self.data.volume[0] < self.avg_vol[0] * 1.2
            ):
                self.sell()


# === Usage Example ===
if __name__ == '__main__':
    import yfinance as yf
    import numpy as np

    ticker = 'PICCADIL.BO'
    df = yf.download(ticker, period='7d', interval='5m')
    df.dropna(inplace=True)
    df.index.name = 'datetime'
    df.columns = [c.lower() for c in df.columns]

    data = bt.feeds.PandasData(dataname=df)

    cerebro = bt.Cerebro()
    cerebro.adddata(data)
    cerebro.addstrategy(RSIMomentumStrategy)
    cerebro.broker.setcash(100000.0)
    cerebro.run()
    cerebro.plot(style='candlestick')