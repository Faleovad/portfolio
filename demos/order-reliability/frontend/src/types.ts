export interface Line {
  sku: string;
  quantity: number;
}
export interface Order {
  id: string;
  external_id: string;
  state: string;
  lines: Line[];
  components: Line[];
  warehouse_id: string;
  crm_id: string | null;
  tracking: string;
  read_attempts: number;
  scenario: string;
  error: string | null;
  version: number;
}
export interface Inventory {
  warehouse_id: string;
  sku: string;
  on_hand: number;
  reserved: number;
  available: number;
  fulfilled: number;
}
export interface Scenario {
  id: string;
  title: string;
  description: string;
  expected: string;
  faults: { point: string; mode: string; times: number; delay_reads: number }[];
}
export interface Event {
  sequence: number;
  order_id: string | null;
  component: string;
  event: string;
  state: string | null;
  timestamp: string;
  details: Record<string, unknown>;
}
export interface Fence {
  resource_id: string;
  mutation_type: string;
  order_id: string;
  intent_id: string;
  state: string;
  owner: string | null;
  lease_until: number;
}
export interface Task {
  id: number;
  kind: string;
  state: string;
  attempts: number;
  reason: string;
}
export interface Journal {
  external_id: string;
  intent_id: string;
  state: string;
  crm_id: string | null;
}
export interface Receipt {
  intent_id: string;
  kind: string;
  proof: string;
  created_at: string;
}
export interface ExternalOrder {
  id: string;
  status: string;
  stock_status: string;
  tracking: string | null;
  hidden_reads: number;
}
export interface Snapshot {
  orders: Order[];
  inventory: Inventory[];
  reservations: (Line & { state: string })[];
  journals: Journal[];
  fences: Fence[];
  tasks: Task[];
  receipts: Receipt[];
  faults: { point: string; mode: string; remaining: number }[];
  events: Event[];
  external: {
    orders: ExternalOrder[];
    inventory: Inventory[];
    calls: { id: number; operation: string; committed: number; intent_id: string }[];
  };
}
