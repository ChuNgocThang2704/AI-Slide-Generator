import api from './axios';
import type {ApiResponse, SourceDocument, PageResponse} from '../types';

export const documentApi = {
  upload: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<ApiResponse<{url: string, fileName: string, fileSize: number}>>('/document/source-documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  },
  
  getAll: (params: { search?: string, page?: number, size?: number }) => 
    api.get<ApiResponse<PageResponse<SourceDocument>>>('/document/source-documents', { params }),
  
  getById: (id: string) => 
    api.get<ApiResponse<SourceDocument>>(`/document/source-documents/${id}`),
  
  getViewUrl: (id: string) => 
    api.get<ApiResponse<String>>(`/document/source-documents/${id}/view`),
    
  delete: (ids: string[]) => 
    api.delete<ApiResponse<string>>('/document/source-documents', { data: ids }),
};
