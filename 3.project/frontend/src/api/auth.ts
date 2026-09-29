import {
  LoginRequest,
  LoginResponse,
  SendVerificationCodeRequest,
  SendVerificationCodeResponse,
  VerifyCodeRequest,
  VerifyCodeResponse,
  ChangePasswordRequest,
  ChangePasswordResponse,
} from '../types/auth';

const API_BASE = '/api/auth';

export const authApi = {
  async login(data: LoginRequest): Promise<LoginResponse> {
    const res = await fetch(`${API_BASE}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const result = await res.json();
    if (!res.ok) {
      throw new Error(result.detail || '로그인에 실패하였습니다.');
    }
    return result;
  },

  async sendVerificationCode(data: SendVerificationCodeRequest): Promise<SendVerificationCodeResponse> {
    const res = await fetch(`${API_BASE}/send-verification-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const result = await res.json();
    if (!res.ok) {
      throw new Error(result.detail || '인증번호 발송에 실패하였습니다.');
    }
    return result;
  },

  async verifyCode(data: VerifyCodeRequest): Promise<VerifyCodeResponse> {
    const res = await fetch(`${API_BASE}/verify-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const result = await res.json();
    if (!res.ok) {
      throw new Error(result.detail || '인증번호 검증에 실패하였습니다.');
    }
    return result;
  },

  async changePassword(data: ChangePasswordRequest): Promise<ChangePasswordResponse> {
    const res = await fetch(`${API_BASE}/change-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const result = await res.json();
    if (!res.ok) {
      throw new Error(result.detail || '비밀번호 변경에 실패하였습니다.');
    }
    return result;
  },
};
