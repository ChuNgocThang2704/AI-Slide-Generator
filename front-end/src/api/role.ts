import api from './axios';
import type { ApiResponse } from '../types';

export interface Role {
  name: string;
  description: string;
}

export const roleApi = {
  getAll: () => api.get<ApiResponse<Role[]>>('/roles'),
};
