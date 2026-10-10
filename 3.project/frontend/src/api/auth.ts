import {
  LoginRequest,
  LoginResponse,
} from '../types/auth';
import { requestJson } from './client';
import { User } from '../types/auth';

const API_BASE = '/api/auth';

export const authApi = {
  me: () => requestJson<User>(API_BASE + '/me'),
  logout: () => requestJson(API_BASE + '/logout', { method: 'POST' }),
  changeOwnPassword: (current_password: string, new_password: string) => requestJson<User>(API_BASE + '/password', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ current_password, new_password }),
  }),
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

};
