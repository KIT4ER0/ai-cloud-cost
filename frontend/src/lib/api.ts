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
    }
};
