import axios from 'axios';

const apiClient = axios.create({
  baseURL: '',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 响应拦截器：统一提取数据
apiClient.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const msg = err.response?.data?.detail || err.message || '请求失败';
    return Promise.reject(new Error(msg));
  },
);

export default apiClient;
