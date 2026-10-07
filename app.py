from flask import Flask, jsonify, request, render_template
import requests, math, statistics
from datetime import datetime, timezone

app = Flask(__name__)

BINANCE = "https://api.binance.com/api/v3/klines"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{}"

SYMBOLS = {
    "crypto": {"BTCUSDT":"BTC/USDT","ETHUSDT":"ETH/USDT","SOLUSDT":"SOL/USDT","BNBUSDT":"BNB/USDT"},
    "forex": {"EURUSD=X":"EUR/USD","GBPUSD=X":"GBP/USD","USDJPY=X":"USD/JPY","AUDUSD=X":"AUD/USD"},
    "stocks": {"AAPL":"AAPL","MSFT":"MSFT","NVDA":"NVDA","TSLA":"TSLA"}
}

def ema(values, n):
    if len(values) < n: return [None]*len(values)
    k=2/(n+1); out=[None]*(n-1)+[sum(values[:n])/n]
    for x in values[n:]: out.append(x*k+out[-1]*(1-k))
    return out

def rsi(values,n=14):
    if len(values)<=n: return [None]*len(values)
    gains=[]; losses=[]
    for i in range(1,len(values)):
        d=values[i]-values[i-1]; gains.append(max(d,0)); losses.append(max(-d,0))
    ag=sum(gains[:n])/n; al=sum(losses[:n])/n
    out=[None]*n+[100 if al==0 else 100-100/(1+ag/al)]
    for i in range(n,len(gains)):
        ag=(ag*(n-1)+gains[i])/n; al=(al*(n-1)+losses[i])/n
        out.append(100 if al==0 else 100-100/(1+ag/al))
    return out

def atr(candles,n=14):
    tr=[]
    for i,c in enumerate(candles):
        if i==0: tr.append(c["h"]-c["l"])
        else: tr.append(max(c["h"]-c["l"],abs(c["h"]-candles[i-1]["c"]),abs(c["l"]-candles[i-1]["c"])))
    e=ema(tr,n)
    return e

def fetch_crypto(symbol, interval, limit=250):
    r=requests.get(BINANCE,params={"symbol":symbol,"interval":interval,"limit":limit},timeout=12)
    r.raise_for_status()
    return [{"t":int(x[0]),"o":float(x[1]),"h":float(x[2]),"l":float(x[3]),"c":float(x[4]),"v":float(x[5])} for x in r.json()]

def fetch_yahoo(symbol, interval="15m", range_="5d"):
    # Yahoo intraday interval support varies by symbol; 15m is broadly available for recent data.
    url=YAHOO.format(symbol)
    r=requests.get(url,params={"interval":interval,"range":range_,"events":"history"},headers={"User-Agent":"Mozilla/5.0"},timeout=12)
    r.raise_for_status()
    j=r.json()["chart"]["result"][0]
    q=j["indicators"]["quote"][0]
    ts=j["timestamp"]
    out=[]
    for i,t in enumerate(ts):
        if q["close"][i] is None: continue
        out.append({"t":t*1000,"o":float(q["open"][i]),"h":float(q["high"][i]),"l":float(q["low"][i]),"c":float(q["close"][i]),"v":float(q["volume"][i] or 0)})
    return out[-250:]

def analyze(c):
    if len(c)<210: raise ValueError("Not enough candles")
    closes=[x["c"] for x in c]; vols=[x["v"] for x in c]
    e20=ema(closes,20); e50=ema(closes,50); e200=ema(closes,200); rr=rsi(closes,14); aa=atr(c,14)
    i=len(c)-1; price=closes[i]
    # Use completed candle for confirmation when possible.
    j=i-1
    price=closes[j]
    vals={"ema20":e20[j],"ema50":e50[j],"ema200":e200[j],"rsi":rr[j],"atr":aa[j]}
    avgvol=statistics.mean(vols[max(0,j-20):j]) if j>=20 else 0
    recent_high=max(x["h"] for x in c[j-20:j])
    recent_low=min(x["l"] for x in c[j-20:j])
    bull = vals["ema20"]>vals["ema50"]>vals["ema200"] and 50<=vals["rsi"]<=70 and price>vals["ema20"]
    bear = vals["ema20"]<vals["ema50"]<vals["ema200"] and 30<=vals["rsi"]<=50 and price<vals["ema20"]
    breakout_up=price>recent_high and vols[j]>avgvol*1.15
    breakout_dn=price<recent_low and vols[j]>avgvol*1.15
    long_score=sum([bull,breakout_up,price>vals["ema50"],vals["rsi"]>50])
    short_score=sum([bear,breakout_dn,price<vals["ema50"],vals["rsi"]<50])
    if long_score>=3 and long_score>short_score: side="BUY"; score=long_score
    elif short_score>=3 and short_score>long_score: side="SELL"; score=short_score
    else: side="WAIT"; score=max(long_score,short_score)
    risk=max(vals["atr"]*1.2, price*0.001)
    if side=="BUY": sl=price-risk; tp=price+risk*2
    elif side=="SELL": sl=price+risk; tp=price-risk*2
    else: sl=tp=None
    confidence={0:45,1:50,2:58,3:72,4:86}.get(score,45)
    return {"signal":side,"confidence":confidence,"entry":price,"sl":sl,"tp":tp,
            "rsi":vals["rsi"],"ema20":vals["ema20"],"ema50":vals["ema50"],"ema200":vals["ema200"],
            "atr":vals["atr"],"volume_confirmed":bool(vols[j]>avgvol*1.15),
            "candle_time":c[j]["t"]}

@app.get("/")
def home(): return render_template("index.html")

@app.get("/api/signal")
def signal():
    market=request.args.get("market","crypto"); symbol=request.args.get("symbol","BTCUSDT")
    interval=request.args.get("interval","15m")
    if market=="crypto":
        candles=fetch_crypto(symbol,interval)
    else:
        candles=fetch_yahoo(symbol,interval if interval in ("15m","30m","1h","1d") else "15m")
    result=analyze(candles)
    result.update({"market":market,"symbol":symbol,"interval":interval,"updated":datetime.now(timezone.utc).isoformat()})
    return jsonify(result)

@app.get("/api/symbols")
def symbols(): return jsonify(SYMBOLS)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=5000,debug=False)
