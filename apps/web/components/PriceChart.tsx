'use client';
import {useEffect,useRef,useState} from 'react';
import {createChart,CandlestickSeries,ColorType,type UTCTimestamp} from 'lightweight-charts';
import {api} from '../lib/api';
type Candle={time:number;open:number;high:number;low:number;close:number;volume:number};
export default function PriceChart({theme}:{theme:string}){
 const host=useRef<HTMLDivElement>(null);const [interval,setInterval]=useState('1m');const [message,setMessage]=useState('Loading real spot candles…');
 useEffect(()=>{
  if(!host.current)return;
  let active=true;const root=getComputedStyle(document.documentElement);
  const chart=createChart(host.current,{height:300,layout:{background:{type:ColorType.Solid,color:root.getPropertyValue('--panel').trim()},textColor:root.getPropertyValue('--muted').trim(),fontFamily:'monospace',fontSize:11},grid:{vertLines:{color:root.getPropertyValue('--line').trim()},horzLines:{color:root.getPropertyValue('--line').trim()}},rightPriceScale:{borderVisible:false},timeScale:{timeVisible:true,secondsVisible:false,borderVisible:false},handleScroll:true,handleScale:true});
  const series=chart.addSeries(CandlestickSeries,{upColor:'#25c7a2',downColor:'#e7757e',wickUpColor:'#25c7a2',wickDownColor:'#e7757e',borderVisible:false});
  const resize=new ResizeObserver(()=>{if(host.current)chart.applyOptions({width:host.current.clientWidth});});resize.observe(host.current);
  async function load(){try{const result=await api<{status:string;candles:Candle[]}>('/candles?timeframe='+interval);if(!active)return;if(result.status!=='REAL_DATA'||!result.candles.length){setMessage('Spot candles unavailable. No synthetic data is shown.');return;}series.setData(result.candles.map(c=>({...c,time:c.time as UTCTimestamp})));setMessage('');}catch{if(active)setMessage('Spot candles unavailable. No synthetic data is shown.');}}
  load();const refresh=window.setInterval(load,30000);
  return()=>{active=false;clearInterval(refresh);resize.disconnect();chart.remove();};
 },[interval,theme]);
 return <><div className="chart-tools"><div className="segmented">{['1m','5m','15m','1h'].map(v=><button key={v} className={interval===v?'selected':''} onClick={()=>setInterval(v)}>{v}</button>)}</div><span className="muted">Coinbase BTC-USD · UTC · spot context only</span></div><div className="chart-wrap"><div ref={host}/>{message&&<div className="chart-message">{message}</div>}</div><div className="chart-caption">Spot candles do not determine contract settlement. Chart by <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">TradingView</a>.</div></>;
}
