export type Locale = "en" | "ar";

export interface User {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  email_verified_at: string | null;
}

export interface Organisation {
  id: string;
  name: string;
  slug: string;
  status: string;
}

export interface AuthResponse {
  user: User;
  csrf_token: string;
}

export interface ApiErrorBody {
  code?: string;
  message?: string;
  detail?: string;
  error?: { code?: string; message?: string };
}
