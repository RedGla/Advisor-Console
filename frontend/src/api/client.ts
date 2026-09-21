import axios from 'axios';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  withCredentials: true,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = axios.isAxiosError(error) ? error.response?.status : undefined;
    const onLoginPage = window.location.pathname === '/login';
    if (status === 401 && !onLoginPage) {
      sessionStorage.clear();
      window.location.assign('/login');
    }
    return Promise.reject(error);
  },
);