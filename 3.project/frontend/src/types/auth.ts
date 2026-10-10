export interface User {
  user_id?: number;
  email: string;
  role?: 'operator' | 'representative' | 'admin';
  display_name?: string;
  must_change_password?: boolean;
  deployment_mode?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  success: boolean;
  message: string;
  user?: User;
  token?: string;
}

