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
    decision: HumanDecision | None = None
    request: ExecutionRequest | None = None
    result: object | None = None
    master_interpretation: str | None = None
    messages: list[dict[str, object]] = field(default_factory=list)

    def activate_breakdown(self) -> None:
        self.event = SectorEvent("evt-demo-1", "transportes", "vehicle_breakdown", "TX-04", {"operation_id": "OP-123", "urgent": True}, utc_now())
        self.investigation = InvestigationRequest("inv-demo-1", self.event.event_id, ("manutencao", "financeiro"), ("diagnosticar avaria", "avaliar alternativa e impacto"))
        perspectives = (
            SectorPerspective("transportes", {"vehicle_id": "TX-04", "operation_id": "OP-123", "urgent": True, "message": "Veículo indisponível durante operação importante."}),
            SectorPerspective("manutencao", {"diagnosis": "falha do motor", "repair_estimate_hours": 6}),
            SectorPerspective("financeiro", {"alternative_cost": 1800, "currency": "EUR"}),
        )
        self.messages = [
            {"from": "Transportes", "to": "IA Mestre", "text": f"{perspectives[0].facts['vehicle_id']} sofreu uma avaria durante {perspectives[0].facts['operation_id']}."},
            {"from": "IA Mestre", "to": "Manutenção", "text": "Necessitamos avaliação da avaria."},
            {"from": "Manutenção", "to": "IA Mestre", "text": f"{perspectives[1].facts['diagnosis']}; reparação estimada em {perspectives[1].facts['repair_estimate_hours']}h."},
            {"from": "IA Mestre", "to": "Financeiro", "text": "Qual o impacto estimado da alternativa?"},
            {"from": "Financeiro", "to": "IA Mestre", "text": f"Alternativa estimada em {perspectives[2].facts['alternative_cost']} {perspectives[2].facts['currency']}."},
        ]
        self.proposal = MasterAI().coordinate(self.event.event_id, perspectives)
        self.suggestion_accepted = False
        self.decision = None
        self.request = None
        self.result = None
        self.master_interpretation = None

    def accept_suggestion(self) -> None:
        if not self.proposal:
            raise ValueError("a MasterAI proposal is required")
        self.suggestion_accepted = True

    def decide(self, status: str) -> None:
        if status not in {"approved", "rejected"} or not self.proposal or not self.suggestion_accepted:
            raise ValueError("the suggestion must be accepted before human decision")
        self.decision = HumanDecision("dec-demo-1", self.proposal.proposal_id, status, "director-demo")
        self.request = ExecutionRequest("exec-demo-1", self.proposal.proposal_id, self.decision.decision_id, "core-gateway")
        self.result = Core().execute(self.request, self.proposal, self.decision)
        self.master_interpretation = MasterAI().interpret_execution_result(self.result)

    def execute_success(self) -> None:
        if not self.request or not self.decision or self.decision.status != "approved":
            raise ValueError("an approved decision is required")
        self.result = simulate_success(self.result)
        self.master_interpretation = MasterAI().interpret_execution_result(self.result)

    def execute_failure(self) -> None:
        if not self.request or not self.decision or self.decision.status != "approved":
            raise ValueError("an approved decision is required")
        self.result = simulate_failure(self.result)
        self.master_interpretation = MasterAI().interpret_execution_result(self.result)

    def snapshot(self) -> dict[str, object]:
        event = self.event
        return {"company": {"transportes": "ocorrência activa" if event else "operacional", "manutencao": "a analisar avaria" if event else "operacional", "financeiro": "impacto pendente" if event else "operacional", "pending_operations": 1 if event else 0}, "event": {"event_id": event.event_id, "vehicle": event.entity, "operation": event.facts["operation_id"]} if event else None, "messages": self.messages, "proposal": self.proposal.__dict__ if self.proposal else None, "suggestion_accepted": self.suggestion_accepted, "decision": self.decision.__dict__ if self.decision else None, "request": self.request.__dict__ if self.request else None, "result": self.result.__dict__ if self.result else None, "master_interpretation": self.master_interpretation}


STATE = DemoState()


class Handler(BaseHTTPRequestHandler):
    def _send(self, payload, status=200, content_type="application/json"):
        body = payload if isinstance(payload, bytes) else payload.encode("utf-8")
        self.send_response(status); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/state": self._send(json.dumps(STATE.snapshot(), default=str)); return
        if path != "/": self._send(b"Not found", 404, "text/plain"); return
        self._send(HTML, content_type="text/html; charset=utf-8")

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/breakdown": STATE.activate_breakdown()
            elif path == "/api/accept-suggestion": STATE.accept_suggestion()
            elif path == "/api/decision": STATE.decide(parse_qs(urlparse(self.path).query).get("status", [""])[0])
            elif path == "/api/execute": STATE.execute_success()
            elif path == "/api/fail": STATE.execute_failure()
            else: self._send(b"Not found", 404, "text/plain"); return
            self._send(json.dumps(STATE.snapshot(), default=str))
        except ValueError as exc: self._send(json.dumps({"error": str(exc)}), 400)


HTML = '''<!doctype html><html lang="pt"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NEXXUS NEXT</title><style>body{font-family:system-ui;margin:0;background:#f4f5f7;color:#17202a}header{padding:24px 32px;background:#111827;color:white}main{max-width:1100px;margin:24px auto;padding:0 20px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.card{background:white;border:1px solid #ddd;border-radius:12px;padding:18px;margin-bottom:16px}.dot{font-size:22px}button{padding:10px 14px;border:1px solid #bbb;border-radius:8px;background:white;cursor:pointer;margin:4px}button.primary{background:#111827;color:white}.msg{padding:9px;border-left:3px solid #aaa;margin:6px 0}.proposal{white-space:pre-wrap;background:#f8fafc;padding:12px;border-radius:8px}.status{font-weight:700;text-transform:uppercase}.small{color:#667085;font-size:13px}.suggestion{border:2px solid #ddd;padding:14px;border-radius:10px}.decision{border:2px solid #ddd;padding:14px;border-radius:10px;margin-top:12px}.muted{color:#667085}@media(max-width:800px){.grid{grid-template-columns:1fr}}</style></head><body><header><strong>NEXXUS NEXT</strong><div>Director Console · protótipo demonstrável</div></header><main><div class="card"><h2>Estado da empresa</h2><div class="grid" id="company"></div></div><div class="card"><h2>Operação</h2><div id="event">Nenhuma ocorrência activa.</div><button class="primary" onclick="post('/api/breakdown')">Simular avaria do veículo</button></div><div class="card"><h2>IA Mestre</h2><div id="messages"></div><div id="proposal"></div><div id="interpretation"></div></div><div class="card"><h2>Decisão do Director</h2><div id="decision"></div></div><div class="card"><h2>Execução experimental</h2><div id="execution"></div></div></main><script>async function post(u){try{const r=await fetch(u,{method:'POST'});const d=await r.json();if(!r.ok){alert(d.error||'Erro');return}render(d)}catch(e){alert('Não foi possível contactar o servidor NEXXUS. Confirme que o servidor está a correr.')}}async function load(){try{const r=await fetch('/api/state');render(await r.json())}catch(e){console.error(e)}}function render(d){document.getElementById('company').innerHTML=Object.entries(d.company).map(([k,v])=>`<div><span class="dot">●</span><b>${k}</b><div>${v}</div></div>`).join('');document.getElementById('event').innerHTML=d.event?`<b>${d.event.vehicle}</b> · operação <b>${d.event.operation}</b> · event_id <span class="small">${d.event.event_id}</span>`:'Nenhuma ocorrência activa.';document.getElementById('messages').innerHTML=d.messages.map(m=>`<div class="msg"><b>${m.from} → ${m.to}</b><br>${m.text}</div>`).join('');document.getElementById('proposal').innerHTML=d.proposal?`<div class="suggestion"><h3>IA Mestre — Sugestão</h3><p>Problema: ${d.proposal.problem}</p><div class="proposal">Sectores: ${d.proposal.sectors.join(', ')}\nAções: ${JSON.stringify(d.proposal.actions,null,2)}\nAprovação necessária: ${d.proposal.approval_required}\nContexto: ${JSON.stringify(d.proposal.context,null,2)}</div>${!d.suggestion_accepted?'<button class="primary" onclick="post(\'/api/accept-suggestion\')">Aceitar sugestão</button>':'<p><b>Sugestão aceite.</b> Aguardando decisão do Director.</p>'}</div>`:'';document.getElementById('decision').innerHTML=d.suggestion_accepted&&!d.decision?`<div class="decision"><h3>Decisão do Director</h3><p>A resolução proposta pela IA Mestre está pronta para autorização.</p><button class="primary" onclick="post('/api/decision?status=approved')">Aprovar execução</button><button onclick="post('/api/decision?status=rejected')">Rejeitar</button></div>`:d.decision?`<p>Decision <b>${d.decision.decision_id}</b>: <span class="status">${d.decision.status}</span></p>`:'';document.getElementById('execution').innerHTML=d.decision&&d.decision.status==='approved'&&!d.result?`<div class="decision"><p>O Core autorizou a execução experimental.</p><button class="primary" onclick="post('/api/execute')">Executar com sucesso</button><button onclick="post('/api/fail')">Simular falha</button></div>`:d.result?`<div class="proposal">status: <b>${d.result.status}</b>\nexecution_id: ${d.result.execution_id}\nresult_id: ${d.result.result_id}\ndetails: ${JSON.stringify(d.result.details,null,2)}</div>`:d.decision&&d.decision.status==='rejected'?'<p class="muted">Execução bloqueada pelo Core.</p>':'<p class="muted">A execução só fica disponível após aprovação do Director.</p>';document.getElementById('interpretation').innerHTML=d.master_interpretation?`<h3>Interpretação da IA Mestre</h3><div class="proposal">${d.master_interpretation}</div>`:''}load();</script></body></html>'''


def serve(host="127.0.0.1", port=8000): HTTPServer((host, port), Handler).serve_forever()

if __name__ == "__main__": serve()
