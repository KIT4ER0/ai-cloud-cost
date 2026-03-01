const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const getHeaders = () => {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = localStorage.getItem("token");
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
};

const request = {
  get: async (endpoint: string) => {
    const res = await fetch(`${API_URL}${endpoint}`, { headers: getHeaders() });
    if (!res.ok) {
      let errStr = `API Error: ${res.statusText}`;
      try {
        const errData = await res.json();
        if (errData.detail) errStr = typeof errData.detail === "string" ? errData.detail : JSON.stringify(errData.detail);
      } catch (e) {}
      throw new Error(errStr);
    }
    return res.json();
  },
  post: async (endpoint: string, body?: any) => {
    const options: RequestInit = {
      method: "POST",
      headers: getHeaders(),
    };
    if (body) {
      options.body = JSON.stringify(body);
    }
    const res = await fetch(`${API_URL}${endpoint}`, options);
    if (!res.ok) {
      let errStr = `API Error: ${res.statusText}`;
      try {
        const errData = await res.json();
        if (errData.detail) errStr = typeof errData.detail === "string" ? errData.detail : JSON.stringify(errData.detail);
      } catch (e) {}
      throw new Error(errStr);
    }
    return res.json();
  },
};

export const api = {
  ...request,
  auth: {
    login: (data: any) => request.post("/login", data),
    register: (data: any) => request.post("/register", data),
  },
  aws: {
    generateExternalId: () => request.post("/api/aws/generate-external-id"),
    connect: (data: any) => request.post("/api/aws/connect", data),
  },
  costs: {
    getAnalysis: (timeRange: string) => request.get(`/api/costs/analysis?time_range=${timeRange}`),
  },
  monitoring: {
    getResources: (service: string) => request.get(`/api/monitoring/${service.toLowerCase()}`),
    getMetrics: (service: string, resourceId: number) => request.get(`/api/monitoring/${service.toLowerCase()}/${resourceId}/metrics`),
  },
  sync: {
    costs: () => request.post("/sync/cost"),
    metrics: () => request.post("/sync/metrics"),
  },
};
