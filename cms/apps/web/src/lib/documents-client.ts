/**
 * VTV Documents API Client
 *
 * Connects to the FastAPI knowledge base endpoints for document management.
 *
 * Usage:
 *   import { fetchDocuments, uploadDocument } from "@/lib/documents-client"
 */

import type {
  DocumentItem,
  DocumentContentResponse,
  DocumentUpdateData,
  DocumentUploadData,
  DomainList,
  PaginatedDocuments,
} from "@/types/document";

const BASE_URL =
  process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";
const API_PREFIX = "/api/v1/knowledge";

/** Error thrown when the documents API returns a non-OK response. */
export class DocumentsApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "DocumentsApiError";
    this.status = status;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new DocumentsApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

/** Fetch paginated documents with optional filters. */
export async function fetchDocuments(params: {
  page?: number;
  page_size?: number;
  domain?: string;
  status?: string;
  language?: string;
}): Promise<PaginatedDocuments> {
  const searchParams = new URLSearchParams();
  if (params.page !== undefined) searchParams.set("page", String(params.page));
  if (params.page_size !== undefined) searchParams.set("page_size", String(params.page_size));
  if (params.domain) searchParams.set("domain", params.domain);
  if (params.status) searchParams.set("status", params.status);
  if (params.language) searchParams.set("language", params.language);

  const response = await fetch(
    `${BASE_URL}${API_PREFIX}/documents?${searchParams.toString()}`
  );
  return handleResponse<PaginatedDocuments>(response);
}

/** Fetch a single document by ID. */
export async function fetchDocument(id: number): Promise<DocumentItem> {
  const response = await fetch(`${BASE_URL}${API_PREFIX}/documents/${id}`);
  return handleResponse<DocumentItem>(response);
}

/** Upload a new document with file and metadata. */
export async function uploadDocument(
  data: DocumentUploadData
): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append("file", data.file);
  formData.append("domain", data.domain);
  formData.append("language", data.language);
  if (data.title) formData.append("title", data.title);
  if (data.description) formData.append("description", data.description);

  const response = await fetch(`${BASE_URL}${API_PREFIX}/documents`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<DocumentItem>(response);
}

/** Update document metadata. */
export async function updateDocument(
  id: number,
  data: DocumentUpdateData
): Promise<DocumentItem> {
  const response = await fetch(`${BASE_URL}${API_PREFIX}/documents/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<DocumentItem>(response);
}

/** Delete a document and its file. */
export async function deleteDocument(id: number): Promise<void> {
  const response = await fetch(`${BASE_URL}${API_PREFIX}/documents/${id}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new DocumentsApiError(response.status, detail);
  }
}

/** Fetch extracted text chunks for a document. */
export async function fetchDocumentContent(
  id: number
): Promise<DocumentContentResponse> {
  const response = await fetch(
    `${BASE_URL}${API_PREFIX}/documents/${id}/content`
  );
  return handleResponse<DocumentContentResponse>(response);
}

/** Download the original file as a Blob. */
export async function downloadDocument(id: number): Promise<Blob> {
  const response = await fetch(
    `${BASE_URL}${API_PREFIX}/documents/${id}/download`
  );
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new DocumentsApiError(response.status, detail);
  }
  return response.blob();
}

/** Fetch list of unique domains used across documents. */
export async function fetchDomains(): Promise<DomainList> {
  const response = await fetch(`${BASE_URL}${API_PREFIX}/domains`);
  return handleResponse<DomainList>(response);
}
