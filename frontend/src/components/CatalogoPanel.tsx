import { useState, type FormEvent } from "react";
import { Search, ChevronDown, Globe2 } from "lucide-react";
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
  const [modo,setModo]=useState<"regiao"|"arquivo">("regiao");
  const [regiao,setRegiao]=useState("Pantanal");
  const [ano,setAno]=useState("2020");
  const [avancado,setAvancado]=useState(false);
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
      let area:Record<string,unknown>={regiao};
      if(modo==="arquivo"){
        let g;
        try {g=JSON.parse(geo);} catch {throw new Error("Arquivo inválido. Importe um GeoJSON de uma área de estudo.");}
        if(g.type==="Feature")g=g.geometry;
        if(g.type==="FeatureCollection"&&g.features.length===1)g=g.features[0].geometry;
        if(!["Polygon","MultiPolygon"].includes(g?.type))throw new Error("Importe um polígono ou multipolígono GeoJSON em WGS84 (uma feição).");
        if(!origem.trim())throw new Error("Informe a fonte e versão do arquivo.");
        area={geometria:g,origem};
      }
      setResultado(await post<Resultado>("/api/catalogo",{...area,inicio:avancado?inicio:ano+"-01-01",fim:avancado?fim:ano+"-12-31",margem:avancado?Number(margem):0,atualizar}));
    }catch(e){setMsg(e instanceof Error ? e.message : String(e));}finally{setBusy(false);}
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
    <button type="button" className="jobs-head" aria-expanded={aberto} onClick={()=>setAberto(!aberto)}>
      <div className="jobs-head-icon"><Globe2 size={20}/></div>
      <span className="jobs-head-copy"><strong>Explorar incêndios</strong><small>Encontre IDs por região e ano antes de processar.</small></span>
      <ChevronDown size={19} className={aberto?"jobs-open-arrow":""}/>
    </button>
    {aberto&&<div className="jobs-body catalog-body">
      <form onSubmit={(e:FormEvent)=>{e.preventDefault();void consultar(false);}}>
        <div className="catalog-fields">
          <div className="jobs-form-field"><label htmlFor="catalog-mode">Área de pesquisa</label>
            <select id="catalog-mode" value={modo} onChange={e=>setModo(e.target.value as "regiao"|"arquivo")}><option value="regiao">Bioma brasileiro</option><option value="arquivo">Importar área personalizada</option></select></div>
          {modo==="regiao"&&<div className="jobs-form-field"><label htmlFor="catalog-region">Bioma</label>
            <select id="catalog-region" value={regiao} onChange={e=>setRegiao(e.target.value)}>{["Pantanal","Amazônia","Cerrado","Caatinga","Mata Atlântica","Pampa"].map(n=><option key={n}>{n}</option>)}</select></div>}
          <div className="jobs-form-field"><label htmlFor="catalog-year">Ano</label><select id="catalog-year" value={ano} onChange={e=>{setAno(e.target.value);setInicio(e.target.value+"-01-01");setFim(e.target.value+"-12-31");}}>{Array.from({length:20},(_,i)=>2020-i).map(n=><option key={n}>{n}</option>)}</select></div>
        </div>
        {modo==="regiao"&&<p className="catalog-note">Limites dos biomas: IBGE 2019 (1:250.000). A primeira consulta baixa e armazena o arquivo oficial.</p>}
        {modo==="arquivo"&&<div className="catalog-fields">
          <div className="jobs-form-field"><label htmlFor="catalog-file">Arquivo GeoJSON</label><input id="catalog-file" type="file" accept=".geojson,.json" onChange={async e=>{const f=e.target.files?.[0];if(f)setGeo(await f.text());}}/></div>
          <div className="jobs-form-field"><label htmlFor="catalog-source">Fonte e versão</label><input id="catalog-source" required value={origem} onChange={e=>setOrigem(e.target.value)} placeholder="Ex.: IBGE 2019"/></div>
        </div>}
        <details open={avancado} onToggle={e=>setAvancado(e.currentTarget.open)} className="catalog-advanced"><summary>Filtros avançados de data</summary>
          <div className="catalog-fields">
            <div className="jobs-form-field"><label>Início</label><input type="date" min="2001-01-01" max="2020-12-31" value={inicio} onChange={e=>setInicio(e.target.value)}/></div>
            <div className="jobs-form-field"><label>Fim</label><input type="date" min="2001-01-01" max="2020-12-31" value={fim} onChange={e=>setFim(e.target.value)}/></div>
            <div className="jobs-form-field"><label>Margem ± dias</label><input type="number" min="0" max="365" value={margem} onChange={e=>setMargem(e.target.value)}/></div>
          </div>
        </details>
        <div className="catalog-actions"><button type="submit" className="job-start" disabled={busy}><Search size={15}/> Buscar incêndios</button>
          <button type="button" className="secondary-button" disabled={busy} onClick={()=>void consultar(true)}>Atualizar consulta GEE</button></div>
      </form>
      {busy&&<p role="status">Consultando… sem estimativa de duração.</p>}
      {msg&&<p role="status">{msg}</p>}
      {resultado&&<>
        <p>Origem: {resultado.origem} | Consulta: {resultado.consultado_utc} | Janela: {resultado.inicio_efetivo} a {resultado.fim_efetivo}</p>
        <p>Os registros encontrados correspondem à região e ao período escolhidos. Consulte o total do evento separadamente.</p>
        <label>Buscar ID <input value={busca} onChange={e=>setBusca(e.target.value)}/></label>
        <label>Ordenar <select value={ordem} onChange={e=>setOrdem(e.target.value)}><option value="registros_na_aoi">Registros na AOI</option><option value="datas_distintas">Datas</option><option value="id">ID</option></select></label>
        {!linhas.length?<p>Nenhum evento encontrado.</p>:<div style={{overflowX:"auto"}}><table className="catalog-table"><thead><tr>{["ID / ano","Registros na região","Total ID/ano","Datas / lacunas","Primeira / última","Dias","Local","Ações"].map(t=><th key={t}>{t}</th>)}</tr></thead><tbody>
          {linhas.map(e=><tr key={e.ano+":"+e.id}><td>{e.id} / {e.ano}</td><td>{e.registros_na_aoi}</td><td>{e.registros_totais??"Não consultado"}</td><td>{e.datas_distintas} / {e.lacunas}</td><td>{e.primeira_data} / {e.ultima_data}</td><td>{e.dias_periodo}</td><td>{e.local.serie?"Análise disponível":e.local.p1&&e.local.p2?"P1/P2":e.local.p1?"P1":e.local.p2?"P2":"Não localizado"}</td><td><button className="secondary-button" disabled={busy} onClick={()=>void total(e)}>Ver total</button> <button className="secondary-button" disabled={busy} onClick={()=>void processar(e)}>Processar ID</button></td></tr>)}
        </tbody></table></div>}
      </>}
    </div>}
  </section>;
}
