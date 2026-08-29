from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from urllib.parse import parse_qs, urlparse

from .core import Core, ExecutionRequest, HumanDecision, InvestigationRequest, ResolutionProposal, SectorEvent, utc_now
from .executor import simulate_failure, simulate_success
from .master_ai import MasterAI, SectorPerspective
from .transport import TransportSalesState


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
    transport: TransportSalesState = field(default_factory=TransportSalesState)

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
        if not self.proposal or self.suggestion_rejected:
            raise ValueError("a valid MasterAI suggestion is required")
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
            "transport": self.transport.snapshot(),
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

    def _json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

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
            elif parsed.path == "/api/transport/client":
                STATE.transport.create_client(**self._json_body())
            elif parsed.path == "/api/transport/client/select":
                STATE.transport.select_client(self._json_body().get("client_id", ""))
            elif parsed.path == "/api/transport/request":
                STATE.transport.create_request(**self._json_body())
            elif parsed.path == "/api/transport/proforma":
                STATE.transport.create_proforma(self._json_body().get("request_id"))
            elif parsed.path == "/api/transport/payment":
                STATE.transport.confirm_payment(self._json_body().get("proforma_id", ""))
            else:
                self._send(b"Not found", 404, "text/plain")
                return
            self._send(json.dumps(STATE.snapshot(), default=str))
        except (ValueError, TypeError, KeyError) as exc:
            self._send(json.dumps({"error": str(exc)}), 400)


HTML = r'''<!doctype html>
<html lang="pt"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NEXXUS NEXT — Transportes</title>
<style>:root{font-family:system-ui,-apple-system,sans-serif;color:#17202a;background:#f4f6f8}*{box-sizing:border-box}body{margin:0}header{background:#111827;color:#fff;padding:24px 32px}main{max-width:1180px;margin:24px auto;padding:0 20px}.card{background:#fff;border:1px solid #d9dee7;border-radius:14px;padding:20px;margin-bottom:16px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.metric{padding:14px;background:#f8fafc;border-radius:10px}.metric b{display:block;margin-bottom:5px}.step{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px}.step span{padding:7px 10px;border-radius:999px;background:#eef2f6;color:#667085;font-size:13px}.step .active{background:#111827;color:#fff}.msg{padding:10px 12px;border-left:3px solid #9aa4b2;margin:7px 0;background:#fafafa}.box{border:2px solid #d9dee7;border-radius:12px;padding:16px;margin-top:12px}.suggestion{border-color:#111827}.decision{border-color:#667085}.commercial{border-color:#315c8c}button{padding:10px 14px;border:1px solid #b8c0cc;border-radius:8px;background:#fff;cursor:pointer;margin:4px 4px 0 0}button.primary{background:#111827;color:#fff;border-color:#111827}input,select{padding:9px;border:1px solid #c7ced8;border-radius:7px;margin:4px;width:calc(100% - 8px)}form{display:grid;grid-template-columns:1fr 1fr;gap:4px}.full{grid-column:1/-1}pre{white-space:pre-wrap;background:#f8fafc;padding:12px;border-radius:8px}.status{text-transform:uppercase;font-weight:700}.muted{color:#667085}.ok{font-weight:700}@media(max-width:800px){.grid{grid-template-columns:1fr 1fr}form{grid-template-columns:1fr}}@media(max-width:520px){.grid{grid-template-columns:1fr}}</style></head>
<body><header><strong>NEXXUS NEXT</strong><div>Director Console — Transportes</div></header><main>
<div class="card"><h2>Estado da empresa</h2><div class="grid" id="company"></div></div>
<div class="card commercial"><h2>Transportes — Comercial</h2><div id="commercial"></div></div>
<div class="card"><div class="step" id="steps"></div><h2>Ocorrência / Operação</h2><div id="event">Nenhuma ocorrência activa.</div><button class="primary" id="breakdown">Simular avaria do veículo</button></div>
<div class="card"><h2>IA Mestre</h2><div id="messages"></div><div id="proposal"></div><div id="interpretation"></div></div>
<div class="card"><h2>Decisão do Director</h2><div id="decision"></div></div><div class="card"><h2>Execução experimental</h2><div id="execution"></div></div>
</main><script>(function(){"use strict";function el(id){return document.getElementById(id)}function t(v){return String(v==null?"":v)}async function post(path,body){try{var o={method:"POST"};if(body!==undefined){o.headers={"Content-Type":"application/json"};o.body=JSON.stringify(body)}var r=await fetch(path,o),d=await r.json();if(!r.ok)throw new Error(d.error||"Erro no servidor");render(d)}catch(e){console.error(e);alert(e.message||String(e))}}function button(parent,label,primary,path,body){var b=document.createElement("button");b.textContent=label;if(primary)b.className="primary";b.addEventListener("click",function(){post(path,body)});parent.appendChild(b)}function render(d){var c=d.company||{};el("company").innerHTML="<div class='metric'><b>Transportes</b>"+t(c.transportes)+"</div><div class='metric'><b>Manutenção</b>"+t(c.manutencao)+"</div><div class='metric'><b>Financeiro</b>"+t(c.financeiro)+"</div><div class='metric'><b>IA Mestre</b>"+t(c.master)+"</div>";var tr=d.transport||{},p=el("commercial");p.innerHTML="";if(tr.selected_client){var cp=document.createElement("p");cp.innerHTML="<b>Cliente seleccionado:</b> "+t(tr.selected_client.name)+" — "+t(tr.selected_client.identification);p.appendChild(cp)}var cf=document.createElement("form");cf.innerHTML="<input name='name' placeholder='Cliente — nome' required><input name='contact' placeholder='Contacto' required><input class='full' name='identification' placeholder='NIF / identificação' required>";var cb=document.createElement("button");cb.className="primary full";cb.textContent="Criar / seleccionar cliente";cf.appendChild(cb);cf.addEventListener("submit",function(e){e.preventDefault();post("/api/transport/client",Object.fromEntries(new FormData(cf)))});p.appendChild(cf);if((tr.clients||[]).length){var s=document.createElement("select");s.innerHTML="<option value=''>Seleccionar cliente existente</option>"+(tr.clients||[]).map(function(x){return "<option value='"+t(x.client_id)+"'>"+t(x.name)+" — "+t(x.identification)+"</option>"}).join("");s.addEventListener("change",function(){if(this.value)post("/api/transport/client/select",{client_id:this.value})});p.appendChild(s)}var rf=document.createElement("form");rf.innerHTML="<input name='cargo_description' placeholder='Descrição da carga' required><input name='quantity' type='number' min='1' placeholder='Quantidade' required><input name='weight_kg' type='number' min='0' step='0.1' placeholder='Peso (kg)' required><input name='volume_m3' type='number' min='0' step='0.1' placeholder='Volume (m³)' required><input name='cargo_type' placeholder='Tipo de carga' required><input name='origin' placeholder='Origem / recolha' required><input name='destination' placeholder='Destino / entrega' required><input name='distance_km' type='number' min='0' step='1' placeholder='Distância km (mock opcional)'><input name='priority' placeholder='Prioridade' value='normal'><input class='full' name='observations' placeholder='Observações'>";var rb=document.createElement("button");rb.className="primary full";rb.textContent="Criar pedido de transporte";rf.appendChild(rb);rf.addEventListener("submit",function(e){e.preventDefault();post("/api/transport/request",Object.fromEntries(new FormData(rf)))});p.appendChild(rf);if(tr.request){var rq=document.createElement("div");rq.className="box";rq.innerHTML="<h3>Pedido "+t(tr.request.request_id)+"</h3><p>"+t(tr.request.origin)+" → "+t(tr.request.destination)+" · "+t(tr.request.cargo_description)+" · "+t(tr.request.weight_kg)+" kg</p>";button(rq,"Criar Proforma",true,"/api/transport/proforma",{request_id:tr.request.request_id});p.appendChild(rq)}if(tr.proforma){var pp=document.createElement("div");pp.className="box";pp.innerHTML="<h3>Proforma "+t(tr.proforma.proforma_id)+" — "+t(tr.proforma.status)+"</h3><p>Valor preliminar: <b>"+t(tr.proforma.total)+" EUR</b></p><p>Pedido: "+t(tr.proforma.request_id)+" · Cliente: "+t(tr.proforma.client_name)+"</p>";if(tr.proforma.status==="payment_pending")button(pp,"Simular confirmação de pagamento",true,"/api/transport/payment",{proforma_id:tr.proforma.proforma_id});pp.innerHTML+=tr.operation_eligible?"<p class='ok'>✓ Pedido elegível para futura Operação.</p>":"<p class='muted'>Operação bloqueada até confirmação do pagamento.</p>";p.appendChild(pp)}var stages=["Estado","Detecção","Análise Mestre","Sugestão","Decisão Director","Core / Execução","Resultado"],active=d.result?6:d.decision?5:d.suggestion_accepted?4:d.proposal?3:d.event?2:0;el("steps").innerHTML=stages.map(function(s,i){return "<span class='"+(i===active?"active":"")+"'>"+(i+1)+". "+s+"</span>"}).join("");el("event").textContent=d.event?"Veículo "+t(d.event.vehicle)+" avariado — operação "+t(d.event.operation)+" — "+t(d.event.event_id):"Nenhuma ocorrência activa.";el("messages").innerHTML=(d.messages||[]).map(function(m){return "<div class='msg'><b>"+t(m.from)+" → "+t(m.to)+"</b><br>"+t(m.text)+"</div>"}).join("");var pr=el("proposal");pr.innerHTML="";if(d.proposal){var b=document.createElement("div");b.className="box suggestion";b.innerHTML="<h3>IA Mestre — RECOMENDAÇÃO</h3><p>"+t(d.proposal.problem)+"</p>";var pre=document.createElement("pre");pre.textContent="Sectores: "+(Array.isArray(d.proposal.sectors)?d.proposal.sectors.join(", "):t(d.proposal.sectors))+"\nAcções: "+JSON.stringify(d.proposal.actions||[],null,2)+"\nAprovação necessária: "+t(d.proposal.approval_required);b.appendChild(pre);if(!d.suggestion_accepted&&!d.suggestion_rejected){button(b,"Aceitar sugestão",true,"/api/accept-suggestion");button(b,"Rejeitar sugestão",false,"/api/reject-suggestion")}else{var q=document.createElement("p");q.innerHTML=d.suggestion_rejected?"<b>Sugestão rejeitada pelo Director.</b> O fluxo não avança.":"<b>Sugestão aceite pelo Director.</b> Aguardando autorização da execução.";b.appendChild(q)}pr.appendChild(b)}var dec=el("decision");dec.innerHTML="";if(d.suggestion_accepted&&!d.decision){var db=document.createElement("div");db.className="box decision";db.innerHTML="<h3>DECISÃO NECESSÁRIA</h3><p>A aceitação da recomendação não autoriza execução. O Director deve decidir separadamente.</p>";button(db,"APROVAR EXECUÇÃO",true,"/api/decision?status=approved");button(db,"REJEITAR EXECUÇÃO",false,"/api/decision?status=rejected");dec.appendChild(db)}else if(d.decision){dec.innerHTML="<p>Decision <b>"+t(d.decision.decision_id)+"</b>: <span class='status'>"+t(d.decision.status)+"</span></p>"}else if(d.suggestion_rejected)dec.innerHTML="<p class='muted'>Recomendação rejeitada. Não existe autorização.</p>";var ex=el("execution");ex.innerHTML="";if(d.decision&&d.decision.status==="approved"&&!d.result){var xb=document.createElement("div");xb.className="box";xb.innerHTML="<p><b>Core:</b> aprovação válida. Execução experimental disponível.</p>";button(xb,"Executar com sucesso",true,"/api/execute");button(xb,"Simular falha",false,"/api/fail");ex.appendChild(xb)}else if(d.result){var xr=document.createElement("pre");xr.textContent="status: "+t(d.result.status)+"\nexecution_id: "+t(d.result.execution_id)+"\nresult_id: "+t(d.result.result_id)+"\ndetails: "+JSON.stringify(d.result.details||{},null,2);ex.appendChild(xr)}else ex.innerHTML="<p class='muted'>Execução disponível apenas após aprovação humana válida.</p>";el("interpretation").innerHTML=d.master_interpretation?"<h3>IA Mestre — resultado recebido</h3><div class='box'>"+t(d.master_interpretation)+"</div>":""}
el("breakdown").addEventListener("click",function(){post("/api/breakdown")});fetch("/api/state").then(function(r){return r.json()}).then(render).catch(console.error)})();</script></body></html>'''


def serve(host="127.0.0.1", port=8000):
    HTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    serve()
