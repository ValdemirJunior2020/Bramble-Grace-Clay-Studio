const localDev=window.location.port==='5173'||window.location.port==='4173';
export const API=(import.meta.env.VITE_API_URL||(localDev?'http://127.0.0.1:8765':window.location.origin)).replace(/\/$/,'');
export async function api<T=any>(path:string,init?:RequestInit):Promise<T>{
 const r=await fetch(API+path,init); if(!r.ok){let m=`HTTP ${r.status}`;try{const j=await r.json();m=j.detail||m}catch{}throw new Error(m)}
 const ct=r.headers.get('content-type')||'';return (ct.includes('application/json')?await r.json():await r.blob()) as T;
}
export const media=(path?:string|null)=>path?`${API}${path}`:'';
