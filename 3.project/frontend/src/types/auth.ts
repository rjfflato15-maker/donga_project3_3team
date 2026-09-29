export interface User {
  user_id?: number;
  email: string;
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

export interface SendVerificationCodeRequest {
  email: string;
  password: string;
}

export interface SendVerificationCodeResponse {
  success: boolean;
  message: string;
  expires_in_seconds: number;
  demo_code?: string;
}

export interface VerifyCodeRequest {
  email: string;
  code: string;
}

export interface VerifyCodeResponse {
  success: boolean;
  verification_token?: string;
  message?: string;
}

export interface ChangePasswordRequest {
  email: string;
  verification_token: string;
  new_password: string;
}

export interface ChangePasswordResponse {
  success: boolean;
  message: string;
}
