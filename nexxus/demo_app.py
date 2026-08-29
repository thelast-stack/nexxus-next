from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from urllib.parse import parse_qs, urlparse

from .core import Core, ExecutionRequest, HumanDecision, InvestigationRequest, ResolutionProposal, SectorEvent, utc_now
from .executor import simulate_failure, simulate_success
from .master_ai import MasterAI, SectorPerspective


@dataclass
class DemoState:
    event: SectorEvent | None = None
    investigation: InvestigationRequest | None = None
    proposal: ResolutionProposal | None = None
    suggestion_accepted: bool = False
    suggestion_rejected: bool = False
    decision: HumanDecision | None = None
    request: ExecutionRequest | None = None
    result: object | None = None
    master_interpretation: str | None = None
    messages: list[dict[str, object]] = field(default_factory=list)

    def activate_breakdown(self):
        self.event = SectorEvent("evt-demo-1", "transportes", "vehicle_breakdown", "TX-04", {"operation_id": "OP-123", "urgent": True}, utc_now())
        self.investigation = InvestigationRequest("inv-demo-1", self.event.event_id, ("manutencao", "financeiro"), ("diagnosticar avaria", "avaliar alternativa e impacto"))
        perspectives = (
            SectorPerspective("transportes", {"vehicle_id": "TX-04", "operation_id": "OP-123", "urgent": True, "message": "Veiculo indisponivel durante operacao importante."}),
            SectorPerspective("manutencao", {"diagnosis": "falha do motor", "repair_estimate_hours": 6}),
            SectorPerspective("financeiro", {"alternative_cost": 1800, "currency": "EUR"}),
        )
        self.messages = [
            {"from": "Transportes", "to": "IA Mestre", "text": "TX-04 sofreu uma avaria durante OP-123."},
            {"from": "IA Mestre", "to": "Manutencao", "text": "Necessitamos avaliacao da avaria."},
            {"from": "Manutencao", "to": "IA Mestre", "text": "Falha do motor; reparacao estimada em 6h."},
            {"from": "IA Mestre", "to": "Financeiro", "text": "Qual o impacto estimado da alternativa?"},
            {"from": "Financeiro", "to": "IA Mestre", "text": "Alternativa estimada em 1800 EUR."},
        ]
        self.proposal = MasterAI().coordinate(self.event.event_id, perspectives)
        self.suggestion_accepted = False
        self.suggestion_rejected = False
        self.decision = None
        self.request = None
        self.result = None
        self.master_interpretation = None

    def accept_suggestion(self):
        if not self.proposal:
            raise ValueError("a MasterAI proposal is required")
        if self.suggestion_rejected:
            raise ValueError("the suggestion was rejected")
        self.suggestion_accepted = True

    def reject_suggestion(self):
        if not self.proposal:
            raise ValueError("a MasterAI proposal is required")
        self.suggestion_rejected = True
        self.suggestion_accepted = False
        self.decision = None
        self.request = None
        self.result = None
        self.master_interpretation = None

    def decide(self, status):
        if status not in {"approved", "rejected"} or not self.proposal or not self.suggestion_accepted:
            raise ValueError("the suggestion must be accepted before human decision")
        self.decision = HumanDecision("dec-demo-1", self.proposal.proposal_id, status, "director-demo")
        self.request = ExecutionRequest("exec-demo-1", self.proposal.proposal_id, self.decision.decision_id, "core-gateway")
        self.result = Core().execute(self.request, self.proposal, self.decision)
        self.master_interpretation = MasterAI().interpret_execution_result(self.result)

    def execute_success(self):
        if not self.request or not self.decision or self.decision.status != "approved":
            raise ValueError("an approved decision is required")
        self.result = simulate_success(self.result)
        self.master_interpretation = MasterAI().interpret_execution_result(self.result)

    def execute_failure(self):
        if not self.request or not self.decision or self.decision.status != "approved":
            raise ValueError("an approved decision is required")
        self.result = simulate_failure(self.result)
        self.master_interpretation = MasterAI().interpret_execution_result(self.result)

    def snapshot(self):
        event = self.event
        return {
            "company": {
                "transportes": "ocorrencia activa" if event else "operacional",
                "manutencao": "a analisar avaria" if event else "operacional",
                "financeiro": "impacto pendente" if event else "operacional",
                "master": "situacao em analise" if event and not self.result else ("resultado recebido" if self.result else "em espera"),
                "pending_operations": 1 if event and not self.result else 0,
            },
            "event": {"event_id": event.event_id, "vehicle": event.entity, "operation": event.facts["operation_id"]} if event else None,
            "messages": self.messages,
            "proposal": self.proposal.__dict__ if self.proposal else None,
            "suggestion_accepted": self.suggestion_accepted,
            "suggestion_rejected": self.suggestion_rejected,
            "decision": self.decision.__dict__ if self.decision else None,
            "request": self.request.__dict__ if self.request else None,
            "result": self.result.__dict__ if self.result else None,
            "master_interpretation": self.master_interpretation,
        }


STATE = DemoState()


class Handler(BaseHTTPRequestHandler):
    def _send(self, payload, status=200, content_type="application/json"):
        body = payload if isinstance(payload, bytes) else payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/state":
            self._send(json.dumps(STATE.snapshot(), default=str))
            return
        if path != "/":
            self._send(b"Not found", 404, "text/plain")
            return
        self._send(HTML, content_type="text/html; charset=utf-8")

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/breakdown":
                STATE.activate_breakdown()
            elif parsed.path == "/api/accept-suggestion":
                STATE.accept_suggestion()
            elif parsed.path == "/api/reject-suggestion":
                STATE.reject_suggestion()
            elif parsed.path == "/api/decision":
                STATE.decide(parse_qs(parsed.query).get("status", [""])[0])
            elif parsed.path == "/api/execute":
                STATE.execute_success()
            elif parsed.path == "/api/fail":
                STATE.execute_failure()
            else:
                self._send(b"Not found", 404, "text/plain")
                return
            self._send(json.dumps(STATE.snapshot(), default=str))
        except ValueError as exc:
            self._send(json.dumps({"error": str(exc)}), 400)


HTML = r'''<!doctype html>
<html lang="pt">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEXXUS NEXT</title>
<style>
:root{font-family:system-ui,-apple-system,sans-serif;color:#17202a;background:#f4f6f8}*{box-sizing:border-box}body{margin:0}header{background:#111827;color:#fff;padding:24px 32px}main{max-width:1100px;margin:24px auto;padding:0 20px}.card{background:#fff;border:1px solid #d9dee7;border-radius:14px;padding:20px;margin-bottom:16px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.metric{padding:14px;background:#f8fafc;border-radius:10px}.metric b{display:block;margin-bottom:5px}.step{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px}.step span{padding:7px 10px;border-radius:999px;background:#eef2f6;color:#667085;font-size:13px}.step .active{background:#111827;color:#fff}.msg{padding:10px 12px;border-left:3px solid #9aa4b2;margin:7px 0;background:#fafafa}.box{border:2px solid #d9dee7;border-radius:12px;padding:16px;margin-top:12px}.suggestion{border-color:#111827}.decision{border-color:#667085}button{padding:10px 14px;border:1px solid #b8c0cc;border-radius:8px;background:#fff;cursor:pointer;margin:4px 4px 0 0}button.primary{background:#111827;color:#fff;border-color:#111827}pre{white-space:pre-wrap;background:#f8fafc;padding:12px;border-radius:8px}.status{text-transform:uppercase;font-weight:700}.muted{color:#667085}@media(max-width:800px){.grid{grid-template-columns:1fr 1fr}}@media(max-width:520px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<header><strong>NEXXUS NEXT</strong><div>Director Console — prototipo demonstravel</div></header>
<main>
<div class="card"><h2>Estado da empresa</h2><div class="grid" id="company"></div></div>
<div class="card"><div class="step" id="steps"></div><h2>Operacao</h2><div id="event">Nenhuma ocorrencia activa.</div><button class="primary" id="breakdown">Simular avaria do veiculo</button></div>
<div class="card"><h2>IA Mestre</h2><div id="messages"></div><div id="proposal"></div><div id="interpretation"></div></div>
<div class="card"><h2>Decisao do Director</h2><div id="decision"></div></div>
<div class="card"><h2>Execucao experimental</h2><div id="execution"></div></div>
</main>
<script>
(function(){"use strict";
function el(id){return document.getElementById(id)}
function t(v){return String(v==null?"":v)}
async function post(path){try{var r=await fetch(path,{method:"POST"}),d=await r.json();if(!r.ok)throw new Error(d.error||"Erro no servidor");render(d)}catch(e){console.error(e);alert(e.message||String(e))}}
function button(parent,label,primary,path){var b=document.createElement("button");b.textContent=label;if(primary)b.className="primary";b.addEventListener("click",function(){post(path)});parent.appendChild(b)}
function render(d){
 var c=d.company||{};
 el("company").innerHTML="<div class='metric'><b>Transportes</b>"+t(c.transportes)+"</div><div class='metric'><b>Manutencao</b>"+t(c.manutencao)+"</div><div class='metric'><b>Financeiro</b>"+t(c.financeiro)+"</div><div class='metric'><b>IA Mestre</b>"+t(c.master)+"</div>";
 var stages=["Estado","Deteccao","Analise Mestre","Sugestao","Decisao Director","Core / Execucao","Resultado"];var active=d.result?6:d.decision?5:d.suggestion_accepted?4:d.proposal?3:d.event?2:0;el("steps").innerHTML=stages.map(function(s,i){return "<span class='"+(i===active?"active":"")+"'>"+(i+1)+". "+s+"</span>"}).join("");
 el("event").textContent=d.event?"Veiculo "+t(d.event.vehicle)+" avariado — operacao "+t(d.event.operation)+" — "+t(d.event.event_id):"Nenhuma ocorrencia activa.";
 el("messages").innerHTML=(d.messages||[]).map(function(m){return "<div class='msg'><b>"+t(m.from)+" → "+t(m.to)+"</b><br>"+t(m.text)+"</div>"}).join("");
 var p=el("proposal");p.innerHTML="";if(d.proposal){var box=document.createElement("div");box.className="box suggestion";box.innerHTML="<h3>IA Mestre — RECOMENDACAO</h3><p>"+t(d.proposal.problem)+"</p>";var pre=document.createElement("pre");pre.textContent="Sectores envolvidos: "+(Array.isArray(d.proposal.sectors)?d.proposal.sectors.join(", "):t(d.proposal.sectors))+"\nAcoes: "+JSON.stringify(d.proposal.actions||[],null,2)+"\nAprovacao necessaria: "+t(d.proposal.approval_required);box.appendChild(pre);if(!d.suggestion_accepted&&!d.suggestion_rejected){button(box,"Aceitar sugestao",true,"/api/accept-suggestion");button(box,"Rejeitar sugestao",false,"/api/reject-suggestion")}else{var q=document.createElement("p");q.innerHTML=d.suggestion_rejected?"<b>Sugestao rejeitada pelo Director.</b> O fluxo nao avancara para aprovacao.":"<b>Sugestao aceite pelo Director.</b> Aguardando autorizacao da execucao.";box.appendChild(q)}p.appendChild(box)}
 var dec=el("decision");dec.innerHTML="";if(d.suggestion_accepted&&!d.decision){var b=document.createElement("div");b.className="box decision";b.innerHTML="<h3>DECISAO NECESSARIA</h3><p>A proposta foi aceite como recomendacao. A autorizacao da execucao continua a ser uma decisao humana separada.</p>";button(b,"APROVAR EXECUCAO",true,"/api/decision?status=approved");button(b,"REJEITAR EXECUCAO",false,"/api/decision?status=rejected");dec.appendChild(b)}else if(d.decision){dec.innerHTML="<p>Decision <b>"+t(d.decision.decision_id)+"</b>: <span class='status'>"+t(d.decision.status)+"</span></p>"}else if(d.suggestion_rejected){dec.innerHTML="<p class='muted'>O Director rejeitou a recomendacao. Nao existe autorizacao para execucao.</p>"}
 var ex=el("execution");ex.innerHTML="";if(d.decision&&d.decision.status==="approved"&&!d.result){var x=document.createElement("div");x.className="box";x.innerHTML="<p><b>Core:</b> aprovacao valida. Execucao experimental disponivel.</p>";button(x,"Executar com sucesso",true,"/api/execute");button(x,"Simular falha",false,"/api/fail");ex.appendChild(x)}else if(d.result){var r=document.createElement("pre");r.textContent="status: "+t(d.result.status)+"\nexecution_id: "+t(d.result.execution_id)+"\nresult_id: "+t(d.result.result_id)+"\ndetails: "+JSON.stringify(d.result.details||{},null,2);ex.appendChild(r)}else{ex.innerHTML="<p class='muted'>A execucao so fica disponivel apos aprovacao humana valida.</p>"}
 el("interpretation").innerHTML=d.master_interpretation?"<h3>IA Mestre — resultado recebido</h3><div class='box'>"+t(d.master_interpretation)+"</div>":"";
}
el("breakdown").addEventListener("click",function(){post("/api/breakdown")});fetch("/api/state").then(function(r){return r.json()}).then(render).catch(console.error);
}());
</script>
</body></html>'''


def serve(host="127.0.0.1", port=8000):
    HTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    serve()
