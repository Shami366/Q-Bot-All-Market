# Q-Bot All Markets v2
Mobile-friendly trading signal dashboard for Crypto + Forex + Stocks.

## Included
- Crypto live candles from Binance public API
- Stocks/Forex via Yahoo Finance chart API
- EMA 20/50/200, RSI(14), ATR(14)
- Breakout + volume confirmation
- BUY / SELL / WAIT
- Entry, Stop Loss, Take Profit (1:2 RR)
- Confidence score
- Signal history in browser
- Signal-only: no automatic trading

## Run
Python 3.10+
```bash
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

No API key is required for the included public-data endpoints.
