export interface Book {bids:[string,string][];asks:[string,string][];source_at:string|null;received_at:string;cache_age:number|null;version:string;state:string}
export interface Market {id:string;slug:string;horizon:'15m'|'1h';start:string;end:string;threshold:string|null;tick:string;minimum_qty:string;status:string;book:Book|null;book_fresh:boolean;source_age_seconds:number|null;imbalance:string|null}
export type Row=Record<string,unknown>;
export interface Account {id:string;cash:string;reserved:string;equity:string;day_start_equity:string;positions:Row[];pending:Row[];halts:string[];consecutive_losses:number;cooldown_until:string|null}
export interface State {mode:string;server_time:string;collection:boolean;engine_state:string;reference_validated:boolean;manual_trading_ready:boolean;reference:{value:string|null;source_at:string|null;source:string};spot:{value:string;source_at:string;source:string}|null;markets:Market[];accounts:Account[];http_latency_ms:number|null;last_update:string|null;stream_status:string;gap_count:number;errors:Record<string,string>;recorder:{used_bytes:number;quota_bytes:number;free_bytes:number;halted:boolean;warning:boolean};decisions:Row[];orders:Row[];fills:Row[];datasets:Row[];equity_history:Row[];performance:Record<string,{fill_count:number;net_realized_pnl:string}>;research:{status:string;message:string}}
export interface Preview {allowed:boolean;reasons:string[];maximum_cost:string|null;order_id?:string;book_version?:string;source_at?:string;status?:string;estimate:{qty:string;cost:string;fees:string;vwap:string|null;label:string}|null}
export class ApiError extends Error {constructor(message:string,public status:number){super(message);}}
export async function api<T>(path:string,options:RequestInit={},csrf?:string):Promise<T>{
 const response=await fetch(`/api${path}`,{...options,cache:'no-store',headers:{'Content-Type':'application/json',...(csrf?{'x-csrf-token':csrf}:{}),...options.headers}});
 const body=await response.json();
 if(!response.ok)throw new ApiError(typeof body.detail==='string'?body.detail:`Request failed (${response.status})`,response.status);
 return body as T;
}
export const money=(v:unknown,digits=2)=>v===null||v===undefined?'—':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',minimumFractionDigits:digits,maximumFractionDigits:digits}).format(Number(v));
export const number=(v:unknown,digits=2)=>v===null||v===undefined?'—':Number(v).toLocaleString('en-US',{maximumFractionDigits:digits});
export const time=(v:unknown)=>typeof v==='string'?new Date(v).toLocaleTimeString('en-US',{hour12:false,timeZone:'UTC'})+' UTC':'—';
