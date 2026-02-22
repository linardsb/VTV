export interface Driver {
  id: number;
  employee_number: string;
  first_name: string;
  last_name: string;
  date_of_birth: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  photo_url: string | null;
  hire_date: string | null;
  license_categories: string | null;
  license_expiry_date: string | null;
  medical_cert_expiry: string | null;
  qualified_route_ids: string | null;
  default_shift: string;
  status: string;
  notes: string | null;
  training_records: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DriverCreate {
  first_name: string;
  last_name: string;
  employee_number: string;
  date_of_birth?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  photo_url?: string | null;
  hire_date?: string | null;
  license_categories?: string | null;
  license_expiry_date?: string | null;
  medical_cert_expiry?: string | null;
  qualified_route_ids?: string | null;
  default_shift?: string;
  status?: string;
  notes?: string | null;
  training_records?: string | null;
}

export interface DriverUpdate {
  first_name?: string;
  last_name?: string;
  employee_number?: string;
  date_of_birth?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  photo_url?: string | null;
  hire_date?: string | null;
  license_categories?: string | null;
  license_expiry_date?: string | null;
  medical_cert_expiry?: string | null;
  qualified_route_ids?: string | null;
  default_shift?: string;
  status?: string;
  notes?: string | null;
  training_records?: string | null;
  is_active?: boolean;
}

export interface PaginatedDrivers {
  items: Driver[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
