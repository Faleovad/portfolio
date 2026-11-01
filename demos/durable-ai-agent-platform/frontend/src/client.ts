export type Row = Record<string, unknown>;
export interface Scenario {
  id: string;
  title: string;
  fault_plan: [string, number][];
  execution_steps: string[];
}
export interface Snapshot {
  task: Row;
  version: Row;
  provider: {
    state: string;
    mutations: number;
    dispatch_attempts: number;
    effects: Row[];
    domain_state: Record<string, Row[]>;
  };
  steps: Row[];
  runs: Row[];
  events: Row[];
  model_calls: Row[];
  tool_intents: Row[];
  tool_receipts: Row[];
  recovery_tasks: Row[];
  artifacts: Row[];
  evaluations: Row[];
  retrieval_hits: Row[];
  fault_plans: Row[];
}
export const value = (row: Row, key: string): string => String(row[key] ?? "—");
export async function request<T>(
  path: string,
  token = "",
  body?: unknown,
): Promise<T> {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const result = await response.json();
  if (!response.ok)
    throw new Error(
      `${response.status}: ${result.detail || "Request rejected"}`,
    );
  return result as T;
}
