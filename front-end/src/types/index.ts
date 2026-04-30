export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

export interface Role {
  name: string;
  description: string;
}

export interface User {
  id: string;
  username: string;
  email: string;
  roles: Role[];
}

export interface Project {
  id: string;
  name: string;
  ownerId: string;
  prompt?: string;
  fileUrl?: string;
  fileName?: string;
  fileSize?: number;
  status: number; // 1: Waiting, 2: Rendering, 3: Completed, 4: Failed
  slideUrl?: string;
  templateId?: string;
  createdAt: string;
  updatedAt: string;
}

export interface SlidePage {
  id: string;
  projectId: string;
  pageIndex: number;
  title: string;
  content: string;
  imagePrompt?: string;
  imageUrl?: string;
}

export interface AITaskLog {
  id: string;
  projectId: string;
  taskType: number;
  status: number;
  message: string;
  errorMessage?: string;
  createdAt: string;
}

export interface ProjectExport {
  id: string;
  projectId: string;
  exportType: number; // 0: pptx, 1: pdf
  s3Url: string;
  fileName: string;
  fileSize: number;
  createdAt: string;
}

export interface SourceDocument {
  id: string;
  userId: string;
  fileName: string;
  url: string;
  fileSize: number;
  fileType: number;
  createdAt: string;
}

export interface PageResponse<T> {
  page: number;
  size: number;
  totalElements: number;
  totalPages: number;
  items: T[];
}
