export interface User {
  id: number;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserCreate {
  email: string;
  name: string;
  password: string;
  role: string;
}

export interface UserUpdate {
  name?: string;
  email?: string;
  role?: string;
  is_active?: boolean;
}

export interface PaginatedUsers {
  items: User[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
