/**
 * Sangam TypeScript SDK — AI-Native Coordination Platform
 *
 * Usage:
 *   import { SangamClient } from "sangam-sdk";
 *
 *   const client = new SangamClient({ apiKey: "..." });
 *
 *   // Create a workflow
 *   const workflow = await client.workflows.create({
 *     name: "Procurement Request",
 *     initiator_id: "actor-uuid",
 *   });
 *
 *   // List workflows
 *   const workflows = await client.workflows.list();
 */

interface WorkflowCreateInput {
  name: string;
  initiator_id: string;
  description?: string;
  phases?: string[];
  metadata?: Record<string, unknown>;
}

interface WorkflowResponse {
  id: string;
  name: string;
  description: string | null;
  initiator_id: string;
  current_phase: string;
  state: string;
  phases: string[];
  created_at: string;
  updated_at: string;
  approvals: ApprovalResponse[];
  handoffs: HandoffResponse[];
  exceptions: ExceptionResponse[];
}

interface WorkflowListResponse {
  items: WorkflowResponse[];
  total: number;
  page: number;
  page_size: number;
}

interface ActorCreateInput {
  type: "human" | "agent" | "system";
  name: string;
  email?: string;
  roles?: string[];
  permissions?: string[];
  metadata?: Record<string, unknown>;
}

interface ActorResponse {
  id: string;
  type: string;
  name: string;
  email: string | null;
  roles: string[];
  permissions: string[];
  is_active: boolean;
}

interface ApprovalResponse {
  id: string;
  workflow_id: string;
  status: string;
  required_actors: string[];
  approved_by: string[];
}

interface HandoffResponse {
  id: string;
  from_actor_id: string;
  to_actor_id: string;
  verified: boolean;
}

interface ExceptionResponse {
  id: string;
  trigger: string;
  severity: string;
  message: string;
}

interface ClientOptions {
  apiKey: string;
  baseUrl?: string;
}

class SangamClientError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
    this.name = "SangamClientError";
  }
}

class WorkflowsAPI {
  constructor(private client: SangamClient) {}

  async create(input: WorkflowCreateInput): Promise<WorkflowResponse> {
    return this.client.post("/workflows", input);
  }

  async list(params?: {
    page?: number;
    page_size?: number;
    state?: string;
    current_phase?: string;
  }): Promise<WorkflowListResponse> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set("page", String(params.page));
    if (params?.page_size) searchParams.set("page_size", String(params.page_size));
    if (params?.state) searchParams.set("state", params.state);
    if (params?.current_phase) searchParams.set("current_phase", params.current_phase);
    const qs = searchParams.toString();
    return this.client.get(`/workflows${qs ? `?${qs}` : ""}`);
  }

  async get(id: string): Promise<WorkflowResponse> {
    return this.client.get(`/workflows/${id}`);
  }

  async update(id: string, data: Partial<WorkflowCreateInput>): Promise<WorkflowResponse> {
    return this.client.patch(`/workflows/${id}`, data);
  }

  async pause(id: string): Promise<WorkflowResponse> {
    return this.client.post(`/workflows/${id}/pause`, {});
  }

  async resume(id: string): Promise<WorkflowResponse> {
    return this.client.post(`/workflows/${id}/resume`, {});
  }

  async cancel(id: string): Promise<WorkflowResponse> {
    return this.client.post(`/workflows/${id}/cancel`, {});
  }

  async delete(id: string): Promise<void> {
    return this.client.delete(`/workflows/${id}`);
  }
}

class ActorsAPI {
  constructor(private client: SangamClient) {}

  async create(input: ActorCreateInput): Promise<ActorResponse> {
    return this.client.post("/actors", input);
  }

  async list(): Promise<ActorResponse[]> {
    return this.client.get("/actors");
  }

  async get(id: string): Promise<ActorResponse> {
    return this.client.get(`/actors/${id}`);
  }
}

class ApprovalsAPI {
  constructor(private client: SangamClient) {}

  async get(id: string): Promise<ApprovalResponse> {
    return this.client.get(`/approvals/${id}`);
  }

  async approve(id: string): Promise<ApprovalResponse> {
    return this.client.post(`/approvals/${id}/approve`, {});
  }

  async reject(id: string, reason?: string): Promise<ApprovalResponse> {
    return this.client.post(`/approvals/${id}/reject`, { reason });
  }
}

export class SangamClient {
  readonly workflows: WorkflowsAPI;
  readonly actors: ActorsAPI;
  readonly approvals: ApprovalsAPI;
  private baseUrl: string;
  private apiKey: string;

  constructor(options: ClientOptions) {
    this.apiKey = options.apiKey;
    this.baseUrl = (options.baseUrl || "https://api.sangam.ai/v1").replace(/\/+$/, "");
    this.workflows = new WorkflowsAPI(this);
    this.actors = new ActorsAPI(this);
    this.approvals = new ApprovalsAPI(this);
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown
  ): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        "Content-Type": "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      const text = await response.text();
      throw new SangamClientError(
        `API error ${response.status}: ${text}`,
        response.status
      );
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  async get<T>(path: string): Promise<T> {
    return this.request<T>("GET", path);
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>("POST", path, body);
  }

  async patch<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>("PATCH", path, body);
  }

  async delete<T>(path: string): Promise<T> {
    return this.request<T>("DELETE", path);
  }
}
