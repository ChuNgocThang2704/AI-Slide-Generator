import api from './axios';
import type {ApiResponse, Project, SlidePage, AITaskLog, ProjectExport, PageResponse} from '../types';

export const projectApi = {
  create: (data: any) => 
    api.post<ApiResponse<Project>>('/document/projects', data),
  
  getAll: (params: { search?: string, page?: number, size?: number }) => 
    api.get<ApiResponse<PageResponse<Project>>>('/document/projects', { params }),
  
  getById: (id: string) => 
    api.get<ApiResponse<Project>>(`/document/projects/${id}`),
  
  update: (id: string, data: any) => 
    api.post<ApiResponse<Project>>(`/document/projects/${id}`, data),
  
  delete: (ids: string[]) => 
    api.delete<ApiResponse<string>>('/document/projects', { data: ids }),
  
  getPages: (id: string) => 
    api.get<ApiResponse<SlidePage[]>>(`/document/projects/${id}/pages`),
  
  updatePage: (projectId: string, pageId: string, data: any) => 
    api.post<ApiResponse<SlidePage>>(`/document/projects/${projectId}/pages/${pageId}`, data),
  
  syncPages: (projectId: string, pages: any[]) =>
    api.post<ApiResponse<SlidePage[]>>(`/document/projects/${projectId}/pages/sync`, pages),

  getLogs: (id: string) => 
    api.get<ApiResponse<AITaskLog[]>>(`/document/projects/${id}/task-logs`),
  
  getExports: (id: string) => 
    api.get<ApiResponse<ProjectExport[]>>(`/document/projects/${id}/exports`),
};
