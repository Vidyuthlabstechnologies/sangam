const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem("sangam_token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem("sangam_token");
      window.location.href = "/login";
      throw new Error("Unauthorized");
    }
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export const api = {
  workflows: {
    list: (params?: Record<string, string>) =>
      request<any>(`/workflows?${new URLSearchParams(params)}`),
    get: (id: string) => request<any>(`/workflows/${id}`),
    create: (data: any) =>
      request<any>("/workflows", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: any) =>
      request<any>(`/workflows/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    pause: (id: string) =>
      request<any>(`/workflows/${id}/pause`, { method: "POST" }),
    resume: (id: string) =>
      request<any>(`/workflows/${id}/resume`, { method: "POST" }),
    cancel: (id: string) =>
      request<any>(`/workflows/${id}/cancel`, { method: "POST" }),
    delete: (id: string) =>
      request<void>(`/workflows/${id}`, { method: "DELETE" }),
  },
  actors: {
    list: () => request<any[]>("/actors"),
    get: (id: string) => request<any>(`/actors/${id}`),
    create: (data: any) =>
      request<any>("/actors", { method: "POST", body: JSON.stringify(data) }),
  },
  approvals: {
    get: (id: string) => request<any>(`/approvals/${id}`),
    approve: (id: string) =>
      request<any>(`/approvals/${id}/approve`, { method: "POST" }),
    reject: (id: string, reason?: string) =>
      request<any>(`/approvals/${id}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
  },
};
