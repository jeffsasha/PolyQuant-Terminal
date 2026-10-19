'use client';
import {useEffect,useRef,useState} from 'react';
import {createChart,CandlestickSeries,ColorType,type UTCTimestamp,type IChartApi,type ISeriesApi} from 'lightweight-charts';
import {api} from '../lib/api';
type Candle={time:number;open:number;high:number;low:number;close:number;volume:number};
export default function PriceChart({theme}:{theme:string}){
 const host=useRef<HTMLDivElement>(null);const chartRef=useRef<IChartApi|null>(null);const seriesRef=useRef<ISeriesApi<'Candlestick'>|null>(null);const [interval,setInterval]=useState('1m');const [message,setMessage]=useState('Loading real spot candles…');const [lastCandle,setLastCandle]=useState<number|null>(null);
 useEffect(()=>{
  if(!host.current)return;
  setMessage('Loading real spot candles…');setLastCandle(null);
  let active=true;const root=getComputedStyle(document.documentElement);
  const chart=createChart(host.current,{width:host.current.clientWidth,height:320,layout:{background:{type:ColorType.Solid,color:'rgba(0,0,0,0)'},textColor:root.getPropertyValue('--muted').trim(),fontFamily:root.getPropertyValue('--font-mono').trim()||'monospace',fontSize:11,attributionLogo:true},grid:{vertLines:{color:root.getPropertyValue('--chart-grid').trim()},horzLines:{color:root.getPropertyValue('--chart-grid').trim()}},crosshair:{vertLine:{color:root.getPropertyValue('--accent').trim(),labelBackgroundColor:root.getPropertyValue('--accent').trim()},horzLine:{color:root.getPropertyValue('--accent').trim(),labelBackgroundColor:root.getPropertyValue('--accent').trim()}},rightPriceScale:{borderVisible:false},timeScale:{timeVisible:true,secondsVisible:false,borderVisible:false},handleScroll:true,handleScale:true});
  chartRef.current=chart;
  const up=root.getPropertyValue('--green').trim()||'#4cc38a',down=root.getPropertyValue('--red').trim()||'#eb5757';
  const series=chart.addSeries(CandlestickSeries,{upColor:up,downColor:down,wickUpColor:up,wickDownColor:down,borderVisible:false});seriesRef.current=series;
  const resize=new ResizeObserver(()=>{if(host.current)chart.applyOptions({width:host.current.clientWidth});});resize.observe(host.current);
  async function load(){try{const result=await api<{status:string;candles:Candle[]}>('/candles?timeframe='+interval);if(!active)return;if(result.status!=='REAL_DATA'||!result.candles.length){setMessage('Spot candles unavailable. No synthetic data is shown.');return;}series.setData(result.candles.map(c=>({...c,time:c.time as UTCTimestamp})));setLastCandle(result.candles[result.candles.length-1].time);setMessage('');}catch{if(active)setMessage('Spot candles unavailable. No synthetic data is shown.');}}
  load();const refresh=window.setInterval(load,30000);
  return()=>{active=false;clearInterval(refresh);resize.disconnect();chartRef.current=null;seriesRef.current=null;chart.remove();};
 },[interval]);
 useEffect(()=>{
  const root=getComputedStyle(document.documentElement);
  chartRef.current?.applyOptions({layout:{textColor:root.getPropertyValue('--muted').trim()},grid:{vertLines:{color:root.getPropertyValue('--chart-grid').trim()},horzLines:{color:root.getPropertyValue('--chart-grid').trim()}}});
  const up=root.getPropertyValue('--green').trim(),down=root.getPropertyValue('--red').trim();seriesRef.current?.applyOptions({upColor:up,downColor:down,wickUpColor:up,wickDownColor:down});
 },[theme]);
 return <><div className="chart-tools"><div className="segmented">{['1m','5m','15m','1h'].map(v=><button key={v} className={interval===v?'selected':''} onClick={()=>setInterval(v)}>{v}</button>)}</div><span className="muted">Coinbase BTC-USD · UTC · spot context only</span></div><div className="chart-wrap"><div ref={host}/>{message&&<div className="chart-message">{message}</div>}</div><div className="chart-caption">Latest candle: {lastCandle?new Date(lastCandle*1000).toISOString().slice(11,16)+' UTC':'unavailable'}. Spot candles do not determine settlement. Chart by <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">TradingView</a>.</div></>;
}
