import api from './axios';

export interface AiConfig {
  id?: string;
  roleCode: string;
  configName: string;
  language: string;
  tone: string;
  maxProjectsPerDay: number;
  minPagesPerProject: number;
  maxPagesPerProject: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export const aiConfigApi = {
  getAll: () => api.get<ApiResponse<AiConfig[]>>('/document/admin/ai-configs'),
  sync: (configs: AiConfig[]) => api.post<ApiResponse<AiConfig[]>>('/document/admin/ai-configs/sync', configs),
};
