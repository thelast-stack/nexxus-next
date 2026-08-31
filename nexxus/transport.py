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
    status: str = "draft"


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


@dataclass
class Vehicle:
    vehicle_id: str
    plate: str
    vehicle_type: str
    capacity_kg: float
    status: str = "AVAILABLE"


@dataclass
class Driver:
    driver_id: str
    name: str
    status: str = "AVAILABLE"


@dataclass
class TransportOperation:
    operation_id: str
    request_id: str
    client_id: str
    origin: str
    destination: str
    cargo_description: str
    distance_km: float | None
    vehicle_id: str | None = None
    driver_id: str | None = None
    status: str = "PLANNING"


class TransportSalesState:
    """Small in-memory commercial-to-operation slice for the Transportes prototype."""

    def __init__(self):
        self.clients: dict[str, Client] = {}
        self.requests: dict[str, TransportRequest] = {}
        self.proformas: dict[str, Proforma] = {}
        self.operations: dict[str, TransportOperation] = {}
        self.vehicles: dict[str, Vehicle] = {
            "veh-001": Vehicle("veh-001", "LD-24-01", "tractor + semirreboque", 30000),
            "veh-002": Vehicle("veh-002", "LD-24-02", "tractor + contentor", 28000),
            "veh-003": Vehicle("veh-003", "LD-24-03", "camião rígido", 12000, "UNAVAILABLE"),
        }
        self.drivers: dict[str, Driver] = {
            "drv-001": Driver("drv-001", "Carlos Manuel"),
            "drv-002": Driver("drv-002", "João Pedro"),
            "drv-003": Driver("drv-003", "António Silva", "UNAVAILABLE"),
        }
        self.selected_client_id: str | None = None
        self.selected_request_id: str | None = None
        self.selected_operation_id: str | None = None
        self._client_seq = 0
        self._request_seq = 0
        self._proforma_seq = 0
        self._operation_seq = 0

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
            status="draft",
        )
        self.requests[request.request_id] = request
        self.selected_request_id = request.request_id
        return request

    @staticmethod
    def preliminary_price(request: TransportRequest) -> float:
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
        request.status = "awaiting_payment"
        return proforma

    def confirm_payment(self, proforma_id: str) -> Proforma:
        try:
            proforma = self.proformas[proforma_id]
        except KeyError as exc:
            raise ValueError("proforma not found") from exc
        if proforma.status != "payment_pending":
            raise ValueError("only a payment_pending proforma can be marked paid")
        proforma.status = "paid"
        self.requests[proforma.request_id].status = "confirmed"
        return proforma

    def operation_eligibility(self, request_id: str | None = None) -> bool:
        request_id = request_id or self.selected_request_id
        if not request_id:
            return False
        return any(p.request_id == request_id and p.status == "paid" for p in self.proformas.values())

    def create_operation(self, request_id: str | None = None) -> TransportOperation:
        request_id = request_id or self.selected_request_id
        if not self.operation_eligibility(request_id):
            raise ValueError("request is not eligible for operation: payment must be confirmed")
        if any(o.request_id == request_id for o in self.operations.values()):
            raise ValueError("operation already exists for request")
        request = self.requests[request_id]
        self._operation_seq += 1
        operation = TransportOperation(
            operation_id=f"op-{self._operation_seq:03d}",
            request_id=request.request_id,
            client_id=request.client_id,
            origin=request.origin,
            destination=request.destination,
            cargo_description=request.cargo_description,
            distance_km=request.distance_km,
        )
        self.operations[operation.operation_id] = operation
        self.selected_operation_id = operation.operation_id
        request.status = "operation_ready"
        return operation

    def assign_vehicle(self, operation_id: str, vehicle_id: str) -> TransportOperation:
        operation = self.operations.get(operation_id)
        vehicle = self.vehicles.get(vehicle_id)
        if not operation or not vehicle:
            raise ValueError("operation or vehicle not found")
        if vehicle.status != "AVAILABLE":
            raise ValueError("vehicle is not available")
        request = self.requests[operation.request_id]
        if vehicle.capacity_kg < request.weight_kg:
            raise ValueError("vehicle capacity is insufficient")
        vehicle.status = "ASSIGNED"
        operation.vehicle_id = vehicle.vehicle_id
        self._refresh_operation_status(operation)
        return operation

    def assign_driver(self, operation_id: str, driver_id: str) -> TransportOperation:
        operation = self.operations.get(operation_id)
        driver = self.drivers.get(driver_id)
        if not operation or not driver:
            raise ValueError("operation or driver not found")
        if driver.status != "AVAILABLE":
            raise ValueError("driver is not available")
        driver.status = "ASSIGNED"
        operation.driver_id = driver.driver_id
        self._refresh_operation_status(operation)
        return operation

    @staticmethod
    def _refresh_operation_status(operation: TransportOperation) -> None:
        if operation.vehicle_id and operation.driver_id:
            operation.status = "READY_FOR_EXECUTION"
        else:
            operation.status = "PLANNING"

    def snapshot(self) -> dict:
        client = self.clients.get(self.selected_client_id) if self.selected_client_id else None
        request = self.requests.get(self.selected_request_id) if self.selected_request_id else None
        proformas = [p for p in self.proformas.values() if not request or p.request_id == request.request_id]
        operation = self.operations.get(self.selected_operation_id) if self.selected_operation_id else None
        return {
            "clients": [c.__dict__ for c in self.clients.values()],
            "selected_client": client.__dict__ if client else None,
            "request": request.__dict__ if request else None,
            "proforma": proformas[-1].__dict__ if proformas else None,
            "operation_eligible": self.operation_eligibility(),
            "operation": operation.__dict__ if operation else None,
            "vehicles": [v.__dict__ for v in self.vehicles.values()],
            "drivers": [d.__dict__ for d in self.drivers.values()],
        }
