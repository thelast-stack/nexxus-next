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
        self.decision = None
        self.request = None
        self.result = None
        self.master_interpretation = None

    def accept_suggestion(self):
        if not self.proposal:
            raise ValueError("a MasterAI proposal is required")
        self.suggestion_accepted = True

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
                "pending_operations": 1 if event else 0,
            },
            "event": {"event_id": event.event_id, "vehicle": event.entity, "operation": event.facts["operation_id"]} if event else None,
            "messages": self.messages,
            "proposal": self.proposal.__dict__ if self.proposal else None,
            "suggestion_accepted": self.suggestion_accepted,
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
            if parsed.path == "/api/breakdown": STATE.activate_breakdown()
            elif parsed.path == "/api/accept-suggestion": STATE.accept_suggestion()
            elif parsed.path == "/api/decision": STATE.decide(parse_qs(parsed.query).get("status", [""])[0])
            elif parsed.path == "/api/execute": STATE.execute_success()
            elif parsed.path == "/api/fail": STATE.execute_failure()
            else:
                self._send(b"Not found", 404, "text/plain")
                return
            self._send(json.dumps(STATE.snapshot(), default=str))
        except ValueError as exc:
            self._send(json.dumps({"error": str(exc)}), 400)

HTML = r'''<!doctype html>
<html lang="pt">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEXXUS NEXT</title>
<style>
body{font-family:system-ui;margin:0;background:#f4f5f7;color:#17202a}header{padding:24px 32px;background:#111827;color:white}main{max-width:1100px;margin:24px auto;padding:0 20px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.card{background:white;border:1px solid #ddd;border-radius:12px;padding:18px;margin-bottom:16px}.dot{font-size:22px}button{padding:10px 14px;border:1px solid #bbb;border-radius:8px;background:white;cursor:pointer;margin:4px}button.primary{background:#111827;color:white}.msg{padding:9px;border-left:3px solid #aaa;margin:6px 0}.proposal{white-space:pre-wrap;background:#f8fafc;padding:12px;border-radius:8px}.status{font-weight:700;text-transform:uppercase}.small{color:#667085;font-size:13px}.suggestion{border:2px solid #ddd;padding:14px;border-radius:10px}.decision{border:2px solid #ddd;padding:14px;border-radius:10px;margin-top:12px}.muted{color:#667085}@media(max-width:800px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<header><strong>NEXXUS NEXT</strong><div>Director Console - prototipo demonstravel</div></header>
<main>
<div class="card"><h2>Estado da empresa</h2><div class="grid" id="company"></div></div>
<div class="card"><h2>Operacao</h2><div id="event">Nenhuma ocorrencia activa.</div><button class="primary" id="breakdown">Simular avaria do veiculo</button></div>
<div class="card"><h2>IA Mestre</h2><div id="messages"></div><div id="proposal"></div><div id="interpretation"></div></div>
<div class="card"><h2>Decisao do Director</h2><div id="decision"></div></div>
<div class="card"><h2>Execucao experimental</h2><div id="execution"></div></div>
</main>
<script>
(function () {
  "use strict";

  function el(id) { return document.getElementById(id); }
  function text(value) { return String(value == null ? "" : value); }

  async function post(path) {
    try {
      var response = await fetch(path, { method: "POST" });
      var data = await response.json();
      if (!response.ok) throw new Error(data.error || "Erro no servidor");
      render(data);
    } catch (error) {
      console.error(error);
      alert(error.message || String(error));
    }
  }

  function addButton(parent, label, primary, path) {
    var button = document.createElement("button");
    button.textContent = label;
    if (primary) button.className = "primary";
    button.addEventListener("click", function () { post(path); });
    parent.appendChild(button);
  }

  function render(data) {
    var company = data.company || {};
    el("company").innerHTML =
      "<div><b>Transportes</b><div>" + text(company.transportes) + "</div></div>" +
      "<div><b>Manutencao</b><div>" + text(company.manutencao) + "</div></div>" +
      "<div><b>Financeiro</b><div>" + text(company.financeiro) + "</div></div>" +
      "<div><b>Operacoes pendentes</b><div>" + text(company.pending_operations) + "</div></div>";

    el("event").textContent = data.event
      ? "Veiculo " + text(data.event.vehicle) + " avariado - operacao " + text(data.event.operation) + " - " + text(data.event.event_id)
      : "Nenhuma ocorrencia activa.";

    el("messages").innerHTML = (data.messages || []).map(function (message) {
      return "<div class='msg'><b>" + text(message.from) + " -> " + text(message.to) + "</b><br>" + text(message.text) + "</div>";
    }).join("");

    var proposal = el("proposal");
    proposal.innerHTML = "";
    if (data.proposal) {
      var box = document.createElement("div");
      box.className = "suggestion";
      box.innerHTML = "<h3>IA Mestre - Sugestao</h3><p>Problema: " + text(data.proposal.problem) + "</p>";
      var pre = document.createElement("pre");
      pre.className = "proposal";
      pre.textContent = "Sectores: " + (Array.isArray(data.proposal.sectors) ? data.proposal.sectors.join(", ") : text(data.proposal.sectors)) + "\nAcoes: " + JSON.stringify(data.proposal.actions || [], null, 2) + "\nAprovacao necessaria: " + text(data.proposal.approval_required) + "\nContexto: " + JSON.stringify(data.proposal.context || {}, null, 2);
      box.appendChild(pre);
      if (!data.suggestion_accepted) {
        addButton(box, "Aceitar sugestao", true, "/api/accept-suggestion");
      } else {
        var accepted = document.createElement("p");
        accepted.textContent = "Sugestao aceite. Aguardando decisao do Director.";
        box.appendChild(accepted);
      }
      proposal.appendChild(box);
    }

    var decision = el("decision");
    decision.innerHTML = "";
    if (data.suggestion_accepted && !data.decision) {
      var decisionBox = document.createElement("div");
      decisionBox.className = "decision";
      decisionBox.innerHTML = "<h3>Decisao do Director</h3><p>A resolucao proposta pela IA Mestre esta pronta para autorizacao.</p>";
      addButton(decisionBox, "Aprovar execucao", true, "/api/decision?status=approved");
      addButton(decisionBox, "Rejeitar", false, "/api/decision?status=rejected");
      decision.appendChild(decisionBox);
    } else if (data.decision) {
      decision.innerHTML = "<p>Decision <b>" + text(data.decision.decision_id) + "</b>: <span class='status'>" + text(data.decision.status) + "</span></p>";
    }

    var execution = el("execution");
    execution.innerHTML = "";
    if (data.decision && data.decision.status === "approved" && !data.result) {
      var executionBox = document.createElement("div");
      executionBox.className = "decision";
      executionBox.innerHTML = "<p>O Core autorizou a execucao experimental.</p>";
      addButton(executionBox, "Executar com sucesso", true, "/api/execute");
      addButton(executionBox, "Simular falha", false, "/api/fail");
      execution.appendChild(executionBox);
    } else if (data.result) {
      var result = document.createElement("pre");
      result.className = "proposal";
      result.textContent = "status: " + text(data.result.status) + "\nexecution_id: " + text(data.result.execution_id) + "\nresult_id: " + text(data.result.result_id) + "\ndetails: " + JSON.stringify(data.result.details || {}, null, 2);
      execution.appendChild(result);
    } else if (data.decision && data.decision.status === "rejected") {
      execution.innerHTML = "<p class='muted'>Execucao bloqueada pelo Core.</p>";
    } else {
      execution.innerHTML = "<p class='muted'>A execucao so fica disponivel apos aprovacao do Director.</p>";
    }

    el("interpretation").innerHTML = data.master_interpretation
      ? "<h3>Interpretacao da IA Mestre</h3><div class='proposal'>" + text(data.master_interpretation) + "</div>"
      : "";
  }

  el("breakdown").addEventListener("click", function () { post("/api/breakdown"); });
  fetch("/api/state").then(function (response) { return response.json(); }).then(render).catch(function (error) { console.error(error); });
}());
</script>
</body>
</html>'''

def serve(host="127.0.0.1", port=8000):
    HTTPServer((host, port), Handler).serve_forever()

if __name__ == "__main__":
    serve()
