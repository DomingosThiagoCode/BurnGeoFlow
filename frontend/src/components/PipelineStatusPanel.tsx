import { useState } from "react";
import { AlertTriangle, CheckCircle2, CircleHelp, ClipboardList, RefreshCw } from "lucide-react";
import { BASE_API } from "../services/api";

type EstadoArquivo = {existe:boolean;bytes:number|null;estado:string};
type Etapa = {
  nome:string;estado:string;status_manifesto:string|null;
  artefatos_ausentes:string[];assinatura_confere:boolean;mensagem:string;
};
type StatusPipeline = {
  id_incendio:number;
  metodologia_alvo:string;
  metodologia_pipeline_atual:string;
  pronto_para_reprocessamento_integral_v2:boolean;
  dados:Record<string,EstadoArquivo>;
  preprocessamento_v2:{
    versao:string;estado:string;datas_p1:number|null;
    datas_p2:number|null;primeira_data_p2:string|null;
    erro:string|null;
    progresso?:{
      estado?:string;etapa?:string;
      datas_concluidas?:number;datas_total?:number;ultima_data?:string;
    };
  };
  manifesto_existe:boolean;
  entradas_compativeis_manifesto_legado:boolean;
  etapas:Etapa[];
  alertas:string[];
};

const NOMES:Record<string,string> = {
  bruto_gee_p1:"P1 bruto (Earth Engine)",
  bruto_gee_p2:"P2 bruto (Earth Engine)",
  p1_local:"P1 local (legado)",
  p2_local:"P2 local (legado)",
  validar:"Validação estrutural",
  auditar:"Auditoria espacial",
  regularizar_diagnostico:"Regularização (diagnóstico)",
  paisagem:"Métricas de paisagem",
  linhagens:"Linhagens temporais",
  tr_igt:"Trajetórias e incrementos",
  integrar:"Integração",
  robustez:"Robustez",
};
const STATUS:Record<string,string> = {
  disponivel:"Disponível",
  ausente:"Não encontrado",
  vazio:"Arquivo vazio",
  concluido_legado:"Concluído na versão antiga",
  desatualizado:"Desatualizado",
  artefato_perdido:"Arquivo perdido",
  dependencia_desatualizada:"Depende de etapa desatualizada",
  pendente:"Pendente",
  erro:"Falhou",
  sem_proveniencia:"Sem comprovação de execução",
  preprocessado_nao_integrado:"Gerado, ainda não integrado",
  bloqueado_topologia:"Bloqueado por inconsistência geométrica",
  erro_manifesto:"Manifesto inválido",
  origem_alterada:"Fonte mudou",
  origem_ausente:"Fonte desapareceu",
  versao_incompativel:"Versão incompatível",
  codigo_v2_alterado:"Código v2 alterado",
  proveniencia_incompleta:"Hashes ausentes",
  artefato_modificado:"Arquivo alterado após processamento",
  execucao_nao_finalizada:"Execução ativa ou interrompida",
};

function Estado({ estado }: { estado:string }) {
  const bom = estado === "disponivel" || estado === "concluido_legado";
  const neutro = estado === "pendente" || estado === "ausente";
  return <span className={"pipeline-state " + (bom ? "pipeline-ok" :
    neutro ? "pipeline-neutral" : "pipeline-warning")}>
    {bom ? <CheckCircle2 size={13}/> :
      neutro ? <CircleHelp size={13}/> : <AlertTriangle size={13}/>}
    {STATUS[estado] ?? estado}
  </span>;
}

/** Verificação sob demanda para evitar refazer SHA-256 de GeoJSON grande a cada polling. */
export function PipelineStatusPanel({ incendio }: { incendio:number|null }) {
  const [dados,setDados] = useState<StatusPipeline|null>(null);
  const [idConsultado,setIdConsultado] = useState<number|null>(null);
  const [busy,setBusy] = useState(false);
  const [erro,setErro] = useState<string|null>(null);

  async function inspecionar() {
    if (incendio === null || !Number.isSafeInteger(incendio) || incendio <= 0) {
      setErro("Informe um ID GlobFire válido.");
      return;
    }
    setBusy(true); setErro(null);
    try {
      const r=await fetch(BASE_API+"/api/events/"+incendio+"/pipeline-status");
      const obj=await r.json();
      if (!r.ok) throw new Error(obj?.error?.message ?? "Falha ao consultar estado");
      setDados(obj as StatusPipeline);
      setIdConsultado(incendio);
    } catch(e) {
      setErro(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }
  const valido = dados !== null && idConsultado === incendio;
  return <div className="pipeline-inspector">
    <div className="pipeline-inspector-head">
      <div><ClipboardList size={17}/>
        <strong>Estado dos dados e do pipeline</strong></div>
      <button type="button" disabled={busy} className="secondary-button"
        onClick={()=>void inspecionar()}>
        <RefreshCw size={14} className={busy?"spin":""}/>
        {busy?"Verificando...":"Inspecionar arquivos"}
      </button>
    </div>
    <p className="catalog-note">
      Verifica arquivos, hashes, etapas e erros do ID digitado.
      Não baixa dados, não inicia processamento e não acessa o Earth Engine.
    </p>
    {erro&&<div className="job-error" role="alert">{erro}</div>}
    {valido&&dados&&<>
      <div className="pipeline-list">
        <h4>1. Insumos no computador</h4>
        {Object.entries(dados.dados).map(([chave,estado])=>
          <div className="pipeline-line" key={chave}>
            <span>{NOMES[chave]??chave}</span><Estado estado={estado.estado}/>
          </div>)}
        <h4>2. Metodologia atual</h4>
        <div className="pipeline-line">
          <span>P1 conectado + P2 retrospectivo</span>
          <Estado estado={dados.preprocessamento_v2.estado}/>
        </div>
        {dados.preprocessamento_v2.progresso?.etapa&&
          <p className="catalog-note">
            Última fase registrada: {dados.preprocessamento_v2.progresso.etapa}.
            {typeof dados.preprocessamento_v2.progresso.datas_concluidas==="number"&&
             " "+dados.preprocessamento_v2.progresso.datas_concluidas+
             " de "+dados.preprocessamento_v2.progresso.datas_total+
             " datas tratadas."}
            {" "}Esse registro não comprova que o processo continua ativo.
          </p>}
        {dados.preprocessamento_v2.erro&&
          <p className="job-error">{dados.preprocessamento_v2.erro}</p>}
        <p className="catalog-note">
          Versão-alvo: {dados.metodologia_alvo}.
          {dados.preprocessamento_v2.datas_p1 !== null &&
            " P1: "+dados.preprocessamento_v2.datas_p1+" datas."}
          {dados.preprocessamento_v2.datas_p2 !== null &&
            " P2: "+dados.preprocessamento_v2.datas_p2+" datas."}
        </p>
        <h4>3. Etapas científicas anteriores</h4>
        {dados.etapas.map(item=><div className="pipeline-line" key={item.nome}>
          <span>{NOMES[item.nome]??item.nome}</span>
          <Estado estado={item.estado}/>
        </div>)}
      </div>
      <div className="pipeline-alerts" role="status">
        <strong><AlertTriangle size={15}/> Atenção à proveniência</strong>
        <p>Resultados marcados como concluídos pertencem ao pipeline
          legado e não estão automaticamente aprovados para D-001/D-002.</p>
        {dados.alertas.map((a,i)=><p key={i}>{a}</p>)}
        {!dados.pronto_para_reprocessamento_integral_v2&&
          <p>Reprocessamento integral v2 ainda bloqueado até adaptação
            das etapas científicas dependentes. Não reaquira dados do GEE.</p>}
      </div>
    </>}
    {!valido&&dados&&<p className="catalog-note">
      O ID foi alterado. Clique em Inspecionar arquivos para atualizar o resultado.
    </p>}
  </div>;
}
