export interface DocumentItem {
  id: number;
  filename: string;
  title: string | null;
  description: string | null;
  domain: string;
  source_type: string;
  language: string;
  file_size_bytes: number | null;
  status: string;
  error_message: string | null;
  chunk_count: number;
  has_file: boolean;
  created_at: string;
  updated_at: string;
}

export interface DocumentChunk {
  chunk_index: number;
  content: string;
}

export interface DocumentContentResponse {
  document_id: number;
  filename: string;
  title: string | null;
  total_chunks: number;
  chunks: DocumentChunk[];
}

export interface PaginatedDocuments {
  items: DocumentItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface DomainList {
  domains: string[];
  total: number;
}

export interface DocumentUploadData {
  file: File;
  domain: string;
  language: string;
  title?: string;
  description?: string;
}

export interface DocumentUpdateData {
  title?: string;
  description?: string;
  domain?: string;
  language?: string;
}
