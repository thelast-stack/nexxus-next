from dataclasses import dataclass


@dataclass
class Client:
    client_id: str
    name: str
    contact: str
    identification: str


@dataclass
class TransportRequest:
    request_id: str
    client_id: str
    cargo_description: str
    quantity: int
    weight_kg: float
    volume_m3: float
    cargo_type: str
    origin: str
    destination: str
    observations: str = ""
    priority: str = "normal"
    distance_km: float | None = None


@dataclass
class Proforma:
    proforma_id: str
    request_id: str
    client_id: str
    client_name: str
    origin: str
    destination: str
    cargo_description: str
    total: float
    status: str = "draft"


class TransportSalesState:
    """Small in-memory commercial slice for the Transportes prototype."""

    def __init__(self):
        self.clients: dict[str, Client] = {}
        self.requests: dict[str, TransportRequest] = {}
        self.proformas: dict[str, Proforma] = {}
        self.selected_client_id: str | None = None
        self.selected_request_id: str | None = None
        self._client_seq = 0
        self._request_seq = 0
        self._proforma_seq = 0

    def create_client(self, name: str, contact: str, identification: str) -> Client:
        if not name.strip() or not contact.strip() or not identification.strip():
            raise ValueError("client name, contact and identification are required")
        self._client_seq += 1
        client = Client(f"cli-{self._client_seq:03d}", name.strip(), contact.strip(), identification.strip())
        self.clients[client.client_id] = client
        self.selected_client_id = client.client_id
        return client

    def select_client(self, client_id: str) -> Client:
        try:
            client = self.clients[client_id]
        except KeyError as exc:
            raise ValueError("client not found") from exc
        self.selected_client_id = client.client_id
        return client

    def create_request(self, **data) -> TransportRequest:
        client_id = data.get("client_id") or self.selected_client_id
        if not client_id or client_id not in self.clients:
            raise ValueError("a valid client is required")
        required = ("cargo_description", "quantity", "weight_kg", "volume_m3", "cargo_type", "origin", "destination")
        if any(str(data.get(field, "")).strip() == "" for field in required):
            raise ValueError("cargo, quantity, weight, volume, type, origin and destination are required")
        self._request_seq += 1
        request = TransportRequest(
            request_id=f"req-{self._request_seq:03d}",
            client_id=client_id,
            cargo_description=str(data["cargo_description"]).strip(),
            quantity=int(data["quantity"]),
            weight_kg=float(data["weight_kg"]),
            volume_m3=float(data["volume_m3"]),
            cargo_type=str(data["cargo_type"]).strip(),
            origin=str(data["origin"]).strip(),
            destination=str(data["destination"]).strip(),
            observations=str(data.get("observations", "")).strip(),
            priority=str(data.get("priority", "normal")).strip() or "normal",
            distance_km=float(data["distance_km"]) if data.get("distance_km") not in (None, "") else None,
        )
        self.requests[request.request_id] = request
        self.selected_request_id = request.request_id
        return request

    @staticmethod
    def preliminary_price(request: TransportRequest) -> float:
        # Deliberately provisional formula; no maps or external pricing service.
        distance = request.distance_km or 0
        return round(500 + request.weight_kg * 0.35 + request.volume_m3 * 20 + distance * 0.50, 2)

    def create_proforma(self, request_id: str | None = None) -> Proforma:
        request_id = request_id or self.selected_request_id
        if not request_id or request_id not in self.requests:
            raise ValueError("a valid transport request is required")
        request = self.requests[request_id]
        client = self.clients[request.client_id]
        self._proforma_seq += 1
        proforma = Proforma(
            proforma_id=f"pro-{self._proforma_seq:03d}",
            request_id=request.request_id,
            client_id=client.client_id,
            client_name=client.name,
            origin=request.origin,
            destination=request.destination,
            cargo_description=request.cargo_description,
            total=self.preliminary_price(request),
            status="payment_pending",
        )
        self.proformas[proforma.proforma_id] = proforma
        return proforma

    def confirm_payment(self, proforma_id: str) -> Proforma:
        try:
            proforma = self.proformas[proforma_id]
        except KeyError as exc:
            raise ValueError("proforma not found") from exc
        if proforma.status != "payment_pending":
            raise ValueError("only a payment_pending proforma can be marked paid")
        proforma.status = "paid"
        return proforma

    def operation_eligibility(self, request_id: str | None = None) -> bool:
        request_id = request_id or self.selected_request_id
        if not request_id:
            return False
        paid = any(p.request_id == request_id and p.status == "paid" for p in self.proformas.values())
        return paid

    def snapshot(self) -> dict:
        client = self.clients.get(self.selected_client_id) if self.selected_client_id else None
        request = self.requests.get(self.selected_request_id) if self.selected_request_id else None
        proformas = [p for p in self.proformas.values() if not request or p.request_id == request.request_id]
        return {
            "clients": [c.__dict__ for c in self.clients.values()],
            "selected_client": client.__dict__ if client else None,
            "request": request.__dict__ if request else None,
            "proforma": proformas[-1].__dict__ if proformas else None,
            "operation_eligible": self.operation_eligibility(),
        }
