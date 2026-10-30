const API_BASE = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body && !(options.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail ?? body);
    } catch {
      // Keep the HTTP status message.
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/api/health"),
  benchmark: () => request<any>("/api/benchmark"),
  savedBenchmark: () => request<any>("/api/benchmark/saved"),
  scenarios: () => request<Scenario[]>("/api/benchmark/scenarios"),
  tasks: () => request<Task[]>("/api/tasks"),
  loadScenario: (id: string) =>
    request<{ id: string; event_count: number }>(
      `/api/benchmark/scenarios/${encodeURIComponent(id)}/load`,
      { method: "POST" },
    ),
  runTask: (task_id: string) =>
    request<Run>( "/api/tasks/run", {
      method: "POST",
      body: JSON.stringify({ task_id }),
    }),
  trace: (id: string) =>
    request<Trace>(`/api/traces/${encodeURIComponent(id)}`),
  analyzeTrace: (id: string) =>
    request<Analysis>(`/api/traces/${encodeURIComponent(id)}/analyze`, {
      method: "POST",
    }),
  analyzeRun: (id: string) =>
    request<Analysis>(`/api/runs/${encodeURIComponent(id)}/analyze`, {
      method: "POST",
    }),
  corrections: (id: string) =>
    request<Corrections>(`/api/runs/${encodeURIComponent(id)}/corrections`),
  replay: (id: string, approved_changes: Record<string, unknown>) =>
    request<Run>(`/api/runs/${encodeURIComponent(id)}/replay`, {
      method: "POST",
      body: JSON.stringify({ approved: true, approved_changes }),
    }),
  comparison: (id: string) =>
    request<any>(`/api/runs/${encodeURIComponent(id)}/comparison`),
  evaluate: (configuration: Record<string, unknown>) =>
    request<any>("/api/tasks/evaluate", {
      method: "POST",
      body: JSON.stringify({ configuration }),
    }),
  uploadTrace: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<{ id: string; event_count: number }>("/api/traces", {
      method: "POST",
      body,
    });
  },
};

export interface Scenario {
  scenario_id: string;
  split: string;
  description: string;
  expected_task_outcome: string;
  ground_truth_categories: string[];
  notes: string;
}

export interface Task {
  task_id: string;
  description: string;
}

export interface TraceEvent {
  event_id: string;
  event_type: string;
  [key: string]: unknown;
}

export interface Trace {
  run_id: string;
  events: TraceEvent[];
  [key: string]: unknown;
}

export interface Finding {
  finding_id: string;
  category: string;
  severity: "low" | "medium" | "high";
  evidence_event_ids: string[];
  observed_facts: string[];
  explanation: string;
  likely_root_cause: string;
  alternative_explanations: string[];
  recommended_action: string;
  confidence: number | null;
  explanation_source: string;
  verification_status: string;
}

export interface Analysis {
  run_id: string;
  findings: Finding[];
  detector_errors: unknown[];
}

export interface Correction {
  correction_id: string;
  title: string;
  description: string;
  finding_ids: string[];
  config_changes: Record<string, unknown>;
  requires_approval: boolean;
}

export interface Corrections {
  run_id: string;
  corrections: Correction[];
  combined_changes: Record<string, unknown>;
}

export interface Run {
  run_id: string;
  task_id: string;
  task_outcome: string;
  agent_reported_status: string;
  [key: string]: any;
}
