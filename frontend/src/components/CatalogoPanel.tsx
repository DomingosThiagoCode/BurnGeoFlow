import { useState, type FormEvent } from "react";
import { BASE_API } from "../services/api";
import { criarJob } from "../services/jobs";

type Evento = {id:number; ano:number; registros_na_aoi:number; registros_totais:number|null; datas_distintas:number; primeira_data:string; ultima_data:string; dias_periodo:number; lacunas:number; local:{p1:boolean;p2:boolean;serie:boolean}};
type Resultado = {origem:string; consultado_utc:string; inicio_efetivo:string; fim_efetivo:string; eventos:Evento[]};

async function post<T>(path:string, body?:unknown):Promise<T> {
  const res=await fetch(BASE_API+path,{method:"POST",headers:{"Content-Type":"application/json"},...(body===undefined?{}:{body:JSON.stringify(body)})});
  const data=await res.json();
  if(!res.ok) throw new Error(typeof data.detail==="string"?data.detail:data.error?.message??"Falha na consulta");
  return data as T;
}
export function CatalogoPanel() {
  const [aberto,setAberto]=useState(false);
  const [geo,setGeo]=useState("");
  const [origem,setOrigem]=useState("");
  const [inicio,setInicio]=useState("2020-01-01");
  const [fim,setFim]=useState("2020-12-31");
  const [margem,setMargem]=useState("15");
  const [resultado,setResultado]=useState<Resultado|null>(null);
  const [busy,setBusy]=useState(false);
  const [msg,setMsg]=useState("");
  const [busca,setBusca]=useState("");
  const [ordem,setOrdem]=useState("registros_na_aoi");
  async function consultar(atualizar:boolean) {
    setBusy(true);setMsg("");setResultado(null);
    try {
      let g=JSON.parse(geo);
      if(g.type==="Feature")g=g.geometry;
      if(g.type==="FeatureCollection"&&g.features.length===1)g=g.features[0].geometry;
      if(!["Polygon","MultiPolygon"].includes(g.type))throw new Error("Importe um polígono ou multipolígono GeoJSON em WGS84 (uma feição).");
      setResultado(await post<Resultado>("/api/catalogo",{geometria:g,origem,inicio,fim,margem:Number(margem),atualizar}));
    }catch(e){setMsg(String(e));}finally{setBusy(false);}
  }
  async function total(e:Evento){
    setBusy(true);setMsg("");
    try{const t=await post<{registros_totais:number}>("/api/catalogo/total/"+e.ano+"/"+e.id);
      setResultado(r=>r?{...r,eventos:r.eventos.map(v=>v.id===e.id&&v.ano===e.ano?{...v,registros_totais:t.registros_totais}:v)}:r);
    }catch(err){setMsg(String(err));}finally{setBusy(false);}
  }
  async function processar(e:Evento){
    if(!window.confirm("Processar ID "+e.id+" ("+e.ano+")? Eventos grandes podem exigir processamento pesado."))return;
    setBusy(true);setMsg("");
    try{await criarJob({id_incendio:e.id,ano:e.ano,origem:"auto"});setMsg("Execução criada. Acompanhe no painel de processamento.");}
    catch(err){setMsg(String(err));}finally{setBusy(false);}
  }
  const linhas=(resultado?.eventos??[]).filter(e=>String(e.id).includes(busca)).sort((a,b)=>ordem==="id"?a.id-b.id:ordem==="datas_distintas"?b.datas_distintas-a.datas_distintas:b.registros_na_aoi-a.registros_na_aoi);
  return <section className="jobs-panel">
    <button type="button" className="jobs-head" aria-expanded={aberto} onClick={()=>setAberto(!aberto)}>Explorar incêndios / Catálogo GlobFire</button>
    {aberto&&<div className="jobs-body">
      <p>Descubra eventos por AOI e período sem exportar geometrias ou calcular P1/P2.</p>
      <form onSubmit={(e:FormEvent)=>{e.preventDefault();void consultar(false);}}>
        <label>Importar AOI GeoJSON <input type="file" accept=".geojson,.json" onChange={async e=>{const f=e.target.files?.[0];if(f)setGeo(await f.text());}}/></label>
        <label>GeoJSON (WGS84)<textarea required value={geo} onChange={e=>setGeo(e.target.value)} rows={4}/></label>
        <label>Fonte e versão da AOI<input required value={origem} onChange={e=>setOrigem(e.target.value)} placeholder="Ex.: IBGE, biomas 2019"/></label>
        <div className="jobs-form">
          <label>Início<input type="date" required min="2001-01-01" max="2020-12-31" value={inicio} onChange={e=>setInicio(e.target.value)}/></label>
          <label>Fim<input type="date" required min="2001-01-01" max="2020-12-31" value={fim} onChange={e=>setFim(e.target.value)}/></label>
          <label>Margem ± dias<input type="number" min="0" max="365" required value={margem} onChange={e=>setMargem(e.target.value)}/></label>
          <button type="submit" disabled={busy}>Consultar catálogo</button>
          <button type="button" disabled={busy||!geo||!origem} onClick={()=>void consultar(true)}>Atualizar catálogo (GEE)</button>
        </div>
      </form>
      {busy&&<p role="status">Consultando… sem estimativa de duração.</p>}
      {msg&&<p role="status">{msg}</p>}
      {resultado&&<>
        <p>Origem: {resultado.origem} | Consulta: {resultado.consultado_utc} | Janela: {resultado.inicio_efetivo} a {resultado.fim_efetivo}</p>
        <p>Contagens e datas da tabela referem-se à interseção AOI/período; total por ID/ano é consultado separadamente.</p>
        <label>Buscar ID <input value={busca} onChange={e=>setBusca(e.target.value)}/></label>
        <label>Ordenar <select value={ordem} onChange={e=>setOrdem(e.target.value)}><option value="registros_na_aoi">Registros na AOI</option><option value="datas_distintas">Datas</option><option value="id">ID</option></select></label>
        {!linhas.length?<p>Nenhum evento encontrado.</p>:<div style={{overflowX:"auto"}}><table><thead><tr>{["ID / ano","Registros AOI","Total ID/ano","Datas / lacunas","Primeira / última","Dias","Local","Ações"].map(t=><th key={t}>{t}</th>)}</tr></thead><tbody>
          {linhas.map(e=><tr key={e.ano+":"+e.id}><td>{e.id} / {e.ano}</td><td>{e.registros_na_aoi}</td><td>{e.registros_totais??"Não consultado"}</td><td>{e.datas_distintas} / {e.lacunas}</td><td>{e.primeira_data} / {e.ultima_data}</td><td>{e.dias_periodo}</td><td>{e.local.serie?"Análise disponível":e.local.p1&&e.local.p2?"P1/P2":e.local.p1?"P1":e.local.p2?"P2":"Não localizado"}</td><td><button disabled={busy} onClick={()=>void total(e)}>Total</button> <button disabled={busy} onClick={()=>void processar(e)}>Processar este ID</button></td></tr>)}
        </tbody></table></div>}
      </>}
    </div>}
  </section>;
}
