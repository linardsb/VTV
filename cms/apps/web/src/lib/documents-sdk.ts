/**
 * Documents API client powered by @vtv/sdk.
 *
 * Drop-in replacement for documents-client.ts — same function signatures,
 * backed by the generated SDK instead of hand-written fetch calls.
 *
 * Exception: downloadDocument keeps authFetch for binary blob response.
 */

import "@/lib/sdk";
import {
  listDocumentsApiV1KnowledgeDocumentsGet,
  getDocumentApiV1KnowledgeDocumentsDocumentIdGet,
  uploadDocumentApiV1KnowledgeDocumentsPost,
  updateDocumentApiV1KnowledgeDocumentsDocumentIdPatch,
  deleteDocumentApiV1KnowledgeDocumentsDocumentIdDelete,
  getDocumentContentApiV1KnowledgeDocumentsDocumentIdContentGet,
  listDomainsApiV1KnowledgeDomainsGet,
} from "@vtv/sdk";
import { authFetch } from "@/lib/auth-fetch";
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

/** Error thrown when the documents API returns a non-OK response. */
export class DocumentsApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "DocumentsApiError";
    this.status = status;
  }
}

/** Fetch paginated documents with optional filters. */
export async function fetchDocuments(params: {
  page?: number;
  page_size?: number;
  domain?: string;
  status?: string;
  language?: string;
}): Promise<PaginatedDocuments> {
  const { data, error, response } =
    await listDocumentsApiV1KnowledgeDocumentsGet({
      query: {
        page: params.page,
        page_size: params.page_size,
        domain: params.domain ?? null,
        status: params.status ?? null,
      },
    });
  if (error || !data) {
    throw new DocumentsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch documents",
    );
  }
  return data as unknown as PaginatedDocuments;
}

/** Fetch a single document by ID. */
export async function fetchDocument(id: number): Promise<DocumentItem> {
  const { data, error, response } =
    await getDocumentApiV1KnowledgeDocumentsDocumentIdGet({
      path: { document_id: id },
    });
  if (error || !data) {
    throw new DocumentsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch document",
    );
  }
  return data as unknown as DocumentItem;
}

/** Upload a new document with file and metadata. */
export async function uploadDocument(
  data: DocumentUploadData,
): Promise<DocumentItem> {
  const { data: resData, error, response } =
    await uploadDocumentApiV1KnowledgeDocumentsPost({
      body: {
        file: data.file,
        domain: data.domain,
        language: data.language,
        title: data.title ?? "",
        description: data.description ?? "",
      },
    });
  if (error || !resData) {
    throw new DocumentsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to upload document",
    );
  }
  return resData as unknown as DocumentItem;
}

/** Update document metadata. */
export async function updateDocument(
  id: number,
  docData: DocumentUpdateData,
): Promise<DocumentItem> {
  const { data, error, response } =
    await updateDocumentApiV1KnowledgeDocumentsDocumentIdPatch({
      path: { document_id: id },
      body: docData,
    });
  if (error || !data) {
    throw new DocumentsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to update document",
    );
  }
  return data as unknown as DocumentItem;
}

/** Delete a document and its file. */
export async function deleteDocument(id: number): Promise<void> {
  const { error, response } =
    await deleteDocumentApiV1KnowledgeDocumentsDocumentIdDelete({
      path: { document_id: id },
    });
  if (error) {
    throw new DocumentsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to delete document",
    );
  }
}

/** Fetch extracted text chunks for a document. */
export async function fetchDocumentContent(
  id: number,
): Promise<DocumentContentResponse> {
  const { data, error, response } =
    await getDocumentContentApiV1KnowledgeDocumentsDocumentIdContentGet({
      path: { document_id: id },
    });
  if (error || !data) {
    throw new DocumentsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch document content",
    );
  }
  return data as unknown as DocumentContentResponse;
}

/** Download the original file as a Blob. Uses authFetch for binary response. */
export async function downloadDocument(id: number): Promise<Blob> {
  const response = await authFetch(
    `${BASE_URL}/api/v1/knowledge/documents/${id}/download`,
  );
  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new DocumentsApiError(response.status, detail);
  }
  return response.blob();
}

/** Fetch list of unique domains used across documents. */
export async function fetchDomains(): Promise<DomainList> {
  const { data, error, response } =
    await listDomainsApiV1KnowledgeDomainsGet();
  if (error || !data) {
    throw new DocumentsApiError(
      response.status,
      typeof error === "string" ? error : "Failed to fetch domains",
    );
  }
  return data as unknown as DomainList;
}
