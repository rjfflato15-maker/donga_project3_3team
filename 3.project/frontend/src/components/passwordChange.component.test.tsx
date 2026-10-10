// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { PilotPasswordChange } from './PilotPasswordChange';
import { requestJson } from '../api/client';
const auth = vi.hoisted(() => ({ updateUser: vi.fn(), logout: vi.fn() }));
vi.mock('../api/client', () => ({ requestJson: vi.fn() }));
vi.mock('../context/AuthContext', () => ({ useAuth: () => auth }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it('existing self-password form uses the authenticated endpoint and updates the session user', async () => {
  const user = { email: 'test@example.com', must_change_password: false };
  const done = vi.fn(); vi.mocked(requestJson).mockResolvedValue(user);
  render(<PilotPasswordChange onDone={done} />);
  fireEvent.change(screen.getByLabelText('현재 비밀번호'), { target: { value: 'old-test-password' } });
  fireEvent.change(screen.getByLabelText('새 비밀번호'), { target: { value: 'new-test-password' } });
  fireEvent.change(screen.getByLabelText('새 비밀번호 확인'), { target: { value: 'new-test-password' } });
  fireEvent.click(screen.getByRole('button', { name: '변경하고 계속하기' }));
  await waitFor(() => expect(done).toHaveBeenCalledOnce());
  expect(requestJson).toHaveBeenCalledWith('/api/auth/password', expect.objectContaining({ method: 'POST', body: JSON.stringify({ current_password: 'old-test-password', new_password: 'new-test-password' }) }));
  expect(auth.updateUser).toHaveBeenCalledWith(user);
});

it('mismatched confirmation never sends a password request', () => {
  render(<PilotPasswordChange />);
  fireEvent.change(screen.getByLabelText('현재 비밀번호'), { target: { value: 'old-test-password' } });
  fireEvent.change(screen.getByLabelText('새 비밀번호'), { target: { value: 'new-test-password' } });
  fireEvent.change(screen.getByLabelText('새 비밀번호 확인'), { target: { value: 'other-test-password' } });
  fireEvent.click(screen.getByRole('button', { name: '변경하고 계속하기' }));
  expect(screen.getByRole('alert').textContent).toContain('서로 다릅니다');
  expect(requestJson).not.toHaveBeenCalled();
});
