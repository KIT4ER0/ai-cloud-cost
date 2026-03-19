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
      } catch (e) { }
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
      } catch (e) { }
      throw new Error(errStr);
    }
    return res.json();
  },
};

export const api = {
  ...request,
  auth: {
    me: () => request.get("/me"),
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
    getSummary: () => request.get("/api/monitoring/summary"),
    getMetrics: (service: string, resourceId: number) => request.get(`/api/monitoring/${service.toLowerCase()}/${resourceId}/metrics`),
    getEIPs: () => request.get(`/api/monitoring/ec2/eips`),
  },
  sync: {
    costs: () => request.post("/sync/cost"),
    metrics: () => request.post("/sync/metrics"),
  },
forecast: {
    // Get available services and metrics
    getMetrics: () => request.get("/forecast/metrics"),
    // Get all resources per service for forecast selection
    getResources: () => request.get("/forecast/resources"),
    // Get saved forecast results (with costs) for a resource from DB
    getResults: (service: string, resourceId: number) =>
      request.get(`/forecast/results/${service}/${resourceId}`),
    // Run ensemble forecast with cost calculation
    runEnsemble: (data: {
      resource_id: number;
      service: string;
      metric?: string;
      horizon?: number;
    }) => request.post("/forecast/ensemble", data),
    // Run ensemble forecast for multiple resources at once
    runMultiEnsemble: (data: {
      resources: Array<{ service: string; resource_id: number }>;
      horizon?: number;
    }) => request.post("/forecast/multi-ensemble", data),
    // Get forecast runs history
    getRuns: () => request.get("/forecast/runs"),
    // Get specific forecast run with values
    getRunById: (runId: number) => request.get(`/forecast/runs/${runId}`),
  },
  recommendations: {
    list: () => request.get("/api/recommendations"),
    generate: () => request.post("/api/recommendations/generate"),
  },
};
