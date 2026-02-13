const BASE_URL = 'http://localhost:8000';

export class ApiError extends Error {
    constructor(public status: number, message: string) {
        super(message);
        this.name = 'ApiError';
    }
}

async function handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new ApiError(response.status, errorData.detail || 'An error occurred');
    }
    return response.json();
}

function authHeaders(): Record<string, string> {
    const token = localStorage.getItem('token');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
}

export const api = {
    auth: {
        register: async (data: any) => {
            const response = await fetch(`${BASE_URL}/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            return handleResponse<any>(response);
        },
        login: async (data: any) => {
            const response = await fetch(`${BASE_URL}/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            return handleResponse<any>(response);
        }
    },
    monitoring: {
        getResources: async (service: string) => {
            const response = await fetch(`${BASE_URL}/api/monitoring/${service.toLowerCase()}`, {
                headers: authHeaders(),
            });
            return handleResponse<any[]>(response);
        },
        getMetrics: async (service: string, resourceId: number) => {
            const response = await fetch(`${BASE_URL}/api/monitoring/${service.toLowerCase()}/${resourceId}/metrics`, {
                headers: authHeaders(),
            });
            return handleResponse<any[]>(response);
        },
    },
    costs: {
        getAnalysis: async (timeRange: string) => {
            const response = await fetch(`${BASE_URL}/api/costs/analysis?time_range=${timeRange}`, {
                headers: authHeaders(),
            });
            return handleResponse<any>(response);
        }
    }
};
