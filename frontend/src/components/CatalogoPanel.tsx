import { lazy, Suspense, useEffect, useState, type FormEvent } from "react";
import type { PoligonoAOI } from "./AoiDrawMap";

const AoiDrawMap = lazy(() => import("./AoiDrawMap"));
import { Search, ChevronDown, Globe2, ChevronLeft, ChevronRight } from "lucide-react";
import { BASE_API } from "../services/api";
import { criarJob } from "../services/jobs";

type Evento = {id:number; ano:number; registros_na_aoi:number; registros_totais:number|null; datas_distintas:number; primeira_data:string; ultima_data:string; dias_periodo:number; lacunas:number; local:{p1:boolean;p2:boolean;serie:boolean}};
type Resultado = {origem:string; consultado_utc:string; inicio_efetivo:string; fim_efetivo:string; eventos:Evento[]};
type RegioesDisponiveis = {
  biomas: string[]; pais: string; ufs: {codigo: string; nome: string}[];
};

async function post<T>(path:string, body?:unknown):Promise<T> {
  const res=await fetch(BASE_API+path,{method:"POST",headers:{"Content-Type":"application/json"},...(body===undefined?{}:{body:JSON.stringify(body)})});
  const data=await res.json();
  if(!res.ok) throw new Error(typeof data.detail==="string"?data.detail:data.error?.message??"Falha na consulta");
  return data as T;
}
export function CatalogoPanel() {
  const [aberto,setAberto]=useState(false);
  const [modo,setModo]=useState<"regiao"|"uf"|"pais"|"arquivo"|"desenho">("regiao");
  const [regioes,setRegioes]=useState<RegioesDisponiveis|null>(null);
  const [uf,setUf]=useState("MS");
  const [mapaAberto,setMapaAberto]=useState(false);
  const [desenho,setDesenho]=useState<PoligonoAOI|null>(null);
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
  const [pagina,setPagina]=useState(1);
  const [ordem,setOrdem]=useState("registros_na_aoi");
  useEffect(() => {
    if (!aberto || regioes) return;
    const ctrl = new AbortController();
    fetch(BASE_API + "/api/catalogo/regioes", { signal: ctrl.signal })
      .then(async r => {
        if (!r.ok) throw new Error("Falha lendo regiões do catálogo.");
        return r.json() as Promise<RegioesDisponiveis>;
      })
      .then(r => { if (!ctrl.signal.aborted) setRegioes(r); })
      .catch(err => {
        if (!ctrl.signal.aborted) setMsg(
          err instanceof Error ? err.message : "Falha consultando regiões"
        );
      });
    return () => ctrl.abort();
  }, [aberto, regioes]);

  async function consultar(atualizar:boolean) {
    setBusy(true);setMsg("");
    try {
      let area:Record<string,unknown>={regiao};
      if (modo === "uf") {
        if (!uf) throw new Error("Selecione um estado.");
        area = { regiao: "UF:" + uf };
      } else if (modo === "pais") {
        area = { regiao: "Brasil" };
      } else if (modo === "desenho") {
        if (!desenho) throw new Error("Desenhe pelo menos três vértices no mapa antes de consultar.");
        area = {
          geometria: desenho,
          origem: "Desenho manual do usuário no BurnGeoFlow / WGS84 / v1",
        };
      } else if(modo==="arquivo"){
        let g;
        try {g=JSON.parse(geo);} catch {throw new Error("Arquivo inválido. Importe um GeoJSON de uma área de estudo.");}
        if(g.type==="Feature")g=g.geometry;
        if(g.type==="FeatureCollection"){
          if(g.features?.length!==1)throw new Error("GeoJSON deve ter exatamente uma feição.");
          g=g.features[0].geometry;
        }
        if(!["Polygon","MultiPolygon"].includes(g?.type))throw new Error("Importe um polígono ou multipolígono GeoJSON em WGS84 (uma feição).");
        if(!origem.trim())throw new Error("Informe a fonte e versão do arquivo.");
        area={geometria:g,origem};
      }
      setResultado(await post<Resultado>("/api/catalogo",{...area,inicio:avancado?inicio:ano+"-01-01",fim:avancado?fim:ano+"-12-31",margem:avancado?Number(margem):0,atualizar}));
      setPagina(1); setBusca("");
    }catch(e){setMsg(
      (e instanceof Error ? e.message : String(e)) +
      (resultado ? " Os resultados da consulta anterior foram mantidos." : "")
    );}finally{setBusy(false);}
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
  const tamanhoPagina = 5;
  const totalPaginas = Math.max(1, Math.ceil(linhas.length / tamanhoPagina));
  const paginaAtual = Math.min(pagina, totalPaginas);
  const inicioPagina = (paginaAtual - 1) * tamanhoPagina;
  const visiveis = linhas.slice(inicioPagina, inicioPagina + tamanhoPagina);
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
            <select id="catalog-mode" value={modo}
              onChange={e=>setModo(e.target.value as "regiao"|"uf"|"pais"|"arquivo"|"desenho")}>
              <option value="regiao">Bioma brasileiro</option>
              <option value="uf">Estado brasileiro (UF)</option>
              <option value="pais">Brasil (país)</option>
              <option value="desenho">Desenhar área no mapa</option>
              <option value="arquivo">Importar área personalizada</option>
            </select></div>
          {modo==="regiao"&&<div className="jobs-form-field"><label htmlFor="catalog-region">Bioma</label>
            <select id="catalog-region" value={regiao} onChange={e=>setRegiao(e.target.value)}>
              {(regioes?.biomas??["Pantanal","Amazônia","Cerrado","Caatinga","Mata Atlântica","Pampa"])
                .map(n=><option key={n}>{n}</option>)}
            </select></div>}
          {modo==="uf"&&<div className="jobs-form-field"><label htmlFor="catalog-uf">Estado</label>
            <select id="catalog-uf" value={uf} onChange={e=>setUf(e.target.value)}>
              {(regioes?.ufs??[{codigo:"MS",nome:"Mato Grosso do Sul"}])
                .map(e=><option value={e.codigo} key={e.codigo}>{e.nome} ({e.codigo})</option>)}
            </select></div>}
          <div className="jobs-form-field"><label htmlFor="catalog-year">Ano</label><select id="catalog-year" value={ano} onChange={e=>{setAno(e.target.value);setInicio(e.target.value+"-01-01");setFim(e.target.value+"-12-31");}}>{Array.from({length:20},(_,i)=>2020-i).map(n=><option key={n}>{n}</option>)}</select></div>
        </div>
        {modo==="regiao"&&<p className="catalog-note">Limites oficiais dos biomas: IBGE 2019 (1:250.000). A primeira consulta baixa e armazena o arquivo oficial.</p>}
        {(modo==="uf"||modo==="pais")&&<p className="catalog-note">
          Delimitação IBGE, malhas territoriais 2024. A primeira consulta
          baixa o arquivo oficial da malha de UFs e guarda uma cópia local.
          Consultar o Brasil inteiro pode ser mais pesado que consultar um estado.
        </p>}
        {modo==="desenho"&&<div>
          {!mapaAberto&&<button type="button" className="secondary-button"
            onClick={()=>setMapaAberto(true)}>Abrir mapa para desenhar</button>}
          {mapaAberto&&<Suspense fallback={<p role="status">Carregando mapa de desenho…</p>}>
            <AoiDrawMap onChange={setDesenho}/>
          </Suspense>}
        </div>}
        {modo==="arquivo"&&<div className="catalog-fields">
          <div className="jobs-form-field"><label htmlFor="catalog-file">Arquivo GeoJSON</label><input id="catalog-file" type="file" accept=".geojson,.json" onChange={async e=>{
              const f=e.target.files?.[0];
              if (!f) return;
              if (f.size>5_000_000){setMsg("GeoJSON excede 5 MB. Simplifique a AOI apenas para descoberta de IDs.");return;}
              setGeo(await f.text());setMsg("");
            }}/></div>
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
          <button type="button" className="secondary-button" disabled={busy}
            onClick={()=>void consultar(true)}>Atualizar consulta GEE</button></div>
      </form>
      {busy&&<p role="status">Consultando… sem estimativa de duração.</p>}
      {msg&&<p role="status">{msg}</p>}
      {resultado&&<>
        <p>Origem: {resultado.origem} | Consulta: {resultado.consultado_utc} | Janela: {resultado.inicio_efetivo} a {resultado.fim_efetivo}</p>
        <p>Os registros encontrados correspondem à região e ao período escolhidos. Consulte o total do evento separadamente.</p>
        <div className="catalog-fields">
          <div className="jobs-form-field">
            <label htmlFor="catalog-filter-id">Buscar ID</label>
            <input id="catalog-filter-id" value={busca}
              onChange={e=>{setBusca(e.target.value);setPagina(1);}}
              placeholder="Filtrar resultados"/>
          </div>
          <div className="jobs-form-field">
            <label htmlFor="catalog-sort">Ordenar</label>
            <select id="catalog-sort" value={ordem}
              onChange={e=>{setOrdem(e.target.value);setPagina(1);}}>
              <option value="registros_na_aoi">Mais registros na área</option>
              <option value="datas_distintas">Mais datas observadas</option>
              <option value="id">ID crescente</option>
            </select>
          </div>
        </div>
        <p className="catalog-note" role="status">
          {linhas.length.toLocaleString("pt-BR")} de {resultado.eventos.length.toLocaleString("pt-BR")} eventos ·
          {" "}{linhas.length?inicioPagina+1:0}–{Math.min(inicioPagina+tamanhoPagina,linhas.length)} exibidos
        </p>
        {!linhas.length?<p>Nenhum evento encontrado.</p>:<div style={{overflowX:"auto"}}><table className="catalog-table"><thead><tr>{["ID / ano","Registros na região","Total ID/ano","Datas / lacunas","Primeira / última","Dias","Local","Ações"].map(t=><th key={t}>{t}</th>)}</tr></thead><tbody>
          {visiveis.map(e=><tr key={e.ano+":"+e.id}><td>{e.id} / {e.ano}</td><td>{e.registros_na_aoi}</td><td>{e.registros_totais??"Não consultado"}</td><td>{e.datas_distintas} / {e.lacunas}</td><td>{e.primeira_data} / {e.ultima_data}</td><td>{e.dias_periodo}</td><td>{e.local.serie?"Análise disponível":e.local.p1&&e.local.p2?"P1/P2":e.local.p1?"P1":e.local.p2?"P2":"Não localizado"}</td><td><button className="secondary-button" disabled={busy} onClick={()=>void total(e)}>Ver total</button> <button className="secondary-button" disabled={busy} onClick={()=>void processar(e)}>Processar ID</button></td></tr>)}
        </tbody></table></div>}
        {linhas.length>0&&<nav className="catalog-pagination" aria-label="Paginação dos incêndios">
          <button type="button" className="secondary-button"
            disabled={paginaAtual===1} onClick={()=>setPagina(1)}>Primeira</button>
          <button type="button" className="secondary-button" aria-label="Página anterior"
            disabled={paginaAtual===1} onClick={()=>setPagina(paginaAtual-1)}>
            <ChevronLeft size={16}/>
          </button>
          <span aria-live="polite">Página {paginaAtual} de {totalPaginas}</span>
          <button type="button" className="secondary-button" aria-label="Próxima página"
            disabled={paginaAtual===totalPaginas} onClick={()=>setPagina(paginaAtual+1)}>
            <ChevronRight size={16}/>
          </button>
          <button type="button" className="secondary-button"
            disabled={paginaAtual===totalPaginas} onClick={()=>setPagina(totalPaginas)}>Última</button>
        </nav>}
      </>}
    </div>}
  </section>;
}
