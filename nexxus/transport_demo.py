from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from urllib.parse import parse_qs, urlparse

from .transport import TransportSalesState


STATE = TransportSalesState()


class TransportHandler(BaseHTTPRequestHandler):
    def _send(self, payload, status=200, content_type="application/json"):
        body = payload if isinstance(payload, bytes) else payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/transport/state":
            self._send(json.dumps(STATE.snapshot()))
        elif path == "/":
            self._send(HTML, content_type="text/html; charset=utf-8")
        else:
            self._send(b"Not found", 404, "text/plain")

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            body = self._body()
            if parsed.path == "/api/transport/client":
                STATE.create_client(body.get("name", ""), body.get("contact", ""), body.get("identification", ""))
            elif parsed.path == "/api/transport/client/select":
                STATE.select_client(body.get("client_id", ""))
            elif parsed.path == "/api/transport/request":
                STATE.create_request(**body)
            elif parsed.path == "/api/transport/proforma":
                STATE.create_proforma(body.get("request_id"))
            elif parsed.path == "/api/transport/payment":
                STATE.confirm_payment(body.get("proforma_id", ""))
            elif parsed.path == "/api/transport/operation":
                STATE.create_operation(body.get("request_id"))
            elif parsed.path == "/api/transport/operation/vehicle":
                STATE.assign_vehicle(body.get("operation_id", ""), body.get("vehicle_id", ""))
            elif parsed.path == "/api/transport/operation/driver":
                STATE.assign_driver(body.get("operation_id", ""), body.get("driver_id", ""))
            else:
                self._send(b"Not found", 404, "text/plain")
                return
            self._send(json.dumps(STATE.snapshot()))
        except (ValueError, TypeError, KeyError) as exc:
            self._send(json.dumps({"error": str(exc)}), 400)


HTML = r'''<!doctype html>
<html lang="pt"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEXXUS — Transportes</title>
<style>
:root{font-family:Inter,system-ui,-apple-system,sans-serif;color:#18212f;background:#f3f5f8;--ink:#172033;--line:#dfe4ec;--soft:#f8fafc;--accent:#244b74}
*{box-sizing:border-box}body{margin:0}header{background:var(--ink);color:#fff;padding:22px 34px}header strong{font-size:19px;letter-spacing:.04em}header span{margin-left:12px;color:#aeb8c7;font-size:13px}main{max-width:1180px;margin:auto;padding:24px 20px 60px}.hero{margin-bottom:18px}.hero h1{margin:0 0 6px;font-size:26px}.muted{color:#667085}.tabs{display:flex;gap:6px;border-bottom:1px solid var(--line);margin:12px 0 18px}.tab{border:0;background:transparent;padding:12px 18px;margin:0;border-radius:10px 10px 0 0;color:#667085;cursor:pointer;font-size:14px}.tab.active{background:#fff;color:var(--ink);font-weight:700;border:1px solid var(--line);border-bottom-color:#fff}.panel{display:none}.panel.active{display:block}.card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:20px;margin-bottom:16px;box-shadow:0 2px 8px rgba(16,24,40,.04)}h2{font-size:16px;margin:0 0 14px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.metric{background:var(--soft);border:1px solid #edf0f4;border-radius:10px;padding:13px}.metric b{display:block;text-transform:uppercase;color:#667085;font-size:11px;margin-bottom:6px}.metric strong{font-size:14px}.flow{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}.flow span{padding:7px 10px;border-radius:999px;background:#eef2f6;font-size:12px;color:#667085}.flow .current{background:var(--accent);color:#fff}form{display:grid;grid-template-columns:1fr 1fr;gap:8px}input,select{width:100%;padding:10px;border:1px solid #cbd3df;border-radius:8px;font:inherit}.full{grid-column:1/-1}button.action{padding:10px 14px;border:1px solid #cbd3df;border-radius:8px;background:#fff;cursor:pointer;font:inherit}.primary{background:var(--ink)!important;color:#fff;border-color:var(--ink)!important}.danger{border-color:#b54747!important;color:#9b2c2c}.row{display:flex;gap:10px;flex-wrap:wrap}.kv{display:grid;grid-template-columns:170px 1fr;gap:7px;padding:8px 0;border-bottom:1px solid #edf0f4}.status{font-weight:700;text-transform:uppercase}.success{color:#177245}.warning{color:#9a6700}.blocked{color:#9b2c2c}.notice{padding:12px;border-radius:9px;background:#f7f9fc;margin:10px 0}.empty{color:#98a2b3;padding:8px 0}@media(max-width:800px){.grid{grid-template-columns:1fr 1fr}form{grid-template-columns:1fr}.full{grid-column:auto}.kv{grid-template-columns:1fr}}@media(max-width:520px){.grid{grid-template-columns:1fr}}
</style></head><body>
<header><strong>NEXXUS</strong><span>Transportes · Director Console · Protótipo</span></header><main>
<section class="hero"><h1>Transportes</h1><div class="muted">Primeiro fluxo comercial-operacional: pedido → proforma → pagamento → operação.</div></section>
<section class="card"><h2>Estado</h2><div id="state" class="grid"></div><div id="flow" class="flow"></div></section>
<div class="tabs"><button class="tab active" data-panel="pedido">Pedido</button><button class="tab" data-panel="proforma">Proforma</button><button class="tab" data-panel="operacao">Operação</button></div>
<section id="pedido" class="panel active"><div class="card"><h2>1. Cliente</h2><div id="client-current"></div><form id="client-form"><input name="name" placeholder="Nome do cliente" required><input name="contact" placeholder="Contacto" required><input class="full" name="identification" placeholder="NIF / identificação" required><button class="action primary full">Criar cliente</button></form><div id="client-select"></div></div>
<div class="card"><h2>2. Novo pedido</h2><form id="request-form"><input name="cargo_description" placeholder="Descrição da carga" required><input name="cargo_type" placeholder="Tipo de carga" required><input name="quantity" type="number" min="1" placeholder="Quantidade" required><input name="weight_kg" type="number" min="0" step="0.01" placeholder="Peso (kg)" required><input name="volume_m3" type="number" min="0" step="0.01" placeholder="Volume (m³)" required><input name="distance_km" type="number" min="0" step="0.1" placeholder="Distância experimental (km)"><input name="origin" placeholder="Origem" required><input name="destination" placeholder="Destino" required><input class="full" name="observations" placeholder="Observações"><select name="priority"><option value="normal">Prioridade normal</option><option value="high">Alta prioridade</option></select><button class="action primary full">Criar pedido</button></form><div id="request-detail"></div></div></section>
<section id="proforma" class="panel"><div class="card"><h2>3. Proforma</h2><div id="proforma-detail" class="empty">Crie um pedido para preparar a proforma.</div></div></section>
<section id="operacao" class="panel"><div class="card"><h2>4. Operação</h2><div id="operation-detail" class="empty">A operação fica bloqueada até o pagamento.</div></div></section>
</main><script>
(function(){"use strict";
const $=id=>document.getElementById(id);const post=async(path,body)=>{try{const r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body||{})});const d=await r.json();if(!r.ok)throw Error(d.error||"Erro");render(d)}catch(e){console.error(e);alert(e.message)}};
function submit(form,path){form.addEventListener("submit",e=>{e.preventDefault();post(path,Object.fromEntries(new FormData(form)))})}
function act(parent,label,path,body,primary){const b=document.createElement("button");b.className="action"+(primary?" primary":"");b.textContent=label;b.onclick=()=>post(path,body);parent.appendChild(b)}
function render(d){const t=d.transport||{};const r=t.request,p=t.proforma,o=t.operation;const c=[['Comercial',r?(r.status||'draft'):'sem pedido'],['Proforma',p?(p.status||'draft'):'não criada'],['Pagamento',p&&p.status==='paid'?'CONFIRMADO':p?'PENDENTE':'—'],['Operação',o?(o.status||'PLANNING'):t.operation_eligible?'elegível':'bloqueada']];$("state").innerHTML=c.map(x=>`<div class="metric"><b>${x[0]}</b><strong>${x[1]}</strong></div>`).join("");const stages=['PEDIDO','PROFORMA','PAGAMENTO','OPERAÇÃO'];let idx=r?1:0;if(p)idx=p.status==='paid'?3:2;if(o)idx=4;$("flow").innerHTML=stages.map((s,i)=>`<span class="${i<idx?'current':''}">${s}</span>`).join("");
$("client-current").innerHTML=t.selected_client?`<div class="notice"><b>${t.selected_client.name}</b><br>${t.selected_client.contact} · ${t.selected_client.identification}</div>`:'<div class="empty">Nenhum cliente seleccionado.</div>';
$("client-select").innerHTML=(t.clients||[]).length?'<select id="existing-client"><option value="">Seleccionar cliente existente</option>'+t.clients.map(x=>`<option value="${x.client_id}">${x.name} — ${x.identification}</option>`).join('')+'</select>':'';const es=$("existing-client");if(es)es.onchange=()=>es.value&&post('/api/transport/client/select',{client_id:es.value});
$("request-detail").innerHTML=r?`<div class="notice"><b>${r.request_id}</b> · ${r.origin} → ${r.destination}<br>${r.cargo_description} · ${r.weight_kg} kg · ${r.volume_m3} m³ · estado <span class="status">${r.status}</span></div>`:'<div class="empty">Nenhum pedido criado.</div>';
$("proforma-detail").innerHTML=p?`<div class="kv"><b>Proforma</b><span>${p.proforma_id}</span></div><div class="kv"><b>Pedido</b><span>${p.request_id}</span></div><div class="kv"><b>Cliente</b><span>${p.client_name}</span></div><div class="kv"><b>Rota</b><span>${p.origin} → ${p.destination}</span></div><div class="kv"><b>Total experimental</b><span>${p.total.toFixed(2)} EUR</span></div><div class="kv"><b>Estado</b><span class="status">${p.status}</span></div>`:'<div class="empty">Crie um pedido para preparar a proforma.</div>';if(p&&p.status==='payment_pending'){act($("proforma-detail"),'Confirmar pagamento','/api/transport/payment',{proforma_id:p.proforma_id},true)}
if(p&&p.status==='paid'&&!o){const box=document.createElement('div');box.className='notice';box.innerHTML='<b>Pagamento confirmado.</b> O pedido está elegível para operação.';$("proforma-detail").appendChild(box);act(box,'Preparar operação','/api/transport/operation',{request_id:p.request_id},true)}
if(o){let html=`<div class="kv"><b>Operação</b><span>${o.operation_id}</span></div><div class="kv"><b>Estado</b><span class="status ${o.status==='READY_FOR_EXECUTION'?'success':'warning'}">${o.status}</span></div><div class="kv"><b>Pedido</b><span>${o.request_id}</span></div><div class="kv"><b>Rota</b><span>${o.origin} → ${o.destination}</span></div><div class="kv"><b>Viatura</b><span>${o.vehicle_id||'por atribuir'}</span></div><div class="kv"><b>Motorista</b><span>${o.driver_id||'por atribuir'}</span></div>`;$("operation-detail").innerHTML=html;const box=document.createElement('div');box.className='notice';box.innerHTML='<b>Recursos experimentais</b>';const vs=document.createElement('select');vs.innerHTML='<option value="">Seleccionar viatura disponível</option>'+(t.vehicles||[]).filter(v=>v.status==='AVAILABLE').map(v=>`<option value="${v.vehicle_id}">${v.plate} · ${v.vehicle_type} · ${v.capacity_kg} kg</option>`).join('');box.appendChild(vs);const vb=document.createElement('button');vb.className='action primary';vb.textContent='Atribuir viatura';vb.onclick=()=>vs.value&&post('/api/transport/operation/vehicle',{operation_id:o.operation_id,vehicle_id:vs.value});box.appendChild(vb);const ds=document.createElement('select');ds.innerHTML='<option value="">Seleccionar motorista disponível</option>'+(t.drivers||[]).filter(v=>v.status==='AVAILABLE').map(v=>`<option value="${v.driver_id}">${v.name}</option>`).join('');box.appendChild(ds);const db=document.createElement('button');db.className='action primary';db.textContent='Atribuir motorista';db.onclick=()=>ds.value&&post('/api/transport/operation/driver',{operation_id:o.operation_id,driver_id:ds.value});box.appendChild(db);$("operation-detail").appendChild(box)}else{$("operation-detail").innerHTML=t.operation_eligible?'<div class="notice">Pagamento confirmado. A operação pode ser preparada.</div>':'<div class="notice blocked">Operação bloqueada: a proforma ainda não está paga.</div>'}
}
submit($("client-form"),'/api/transport/client');submit($("request-form"),'/api/transport/request');document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));b.classList.add('active');$(b.dataset.panel).classList.add('active')});fetch('/api/transport/state').then(r=>r.json()).then(render);
})();</script></body></html>'''


def serve(host="127.0.0.1", port=8010):
    HTTPServer((host, port), TransportHandler).serve_forever()


if __name__ == "__main__":
    serve()
