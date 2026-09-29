import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Mail,
  Lock,
  KeyRound,
  CheckCircle2,
  AlertCircle,
  Clock,
  ArrowRight,
  RefreshCw,
  Eye,
  EyeOff,
  Sparkles,
} from 'lucide-react';
import { authApi } from '../../api/auth';
import { useAuth } from '../../context/AuthContext';

interface AccountPasswordResetViewProps {
  onSuccessReturn?: () => void;
}

export const AccountPasswordResetView: React.FC<AccountPasswordResetViewProps> = ({
  onSuccessReturn,
}) => {
  const { user } = useAuth();

  // Current Step: 1 | 2 | 3
  const [step, setStep] = useState<1 | 2 | 3>(1);

  // Form Fields
  const [email, setEmail] = useState<string>(user?.email || 'nj445325@gmail.com');
  const [currentPassword, setCurrentPassword] = useState<string>('');
  const [verificationCode, setVerificationCode] = useState<string>('');
  const [newPassword, setNewPassword] = useState<string>('');
  const [newPasswordConfirm, setNewPasswordConfirm] = useState<string>('');

  // UI States
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [demoCode, setDemoCode] = useState<string | null>(null);

  // Verification Token
  const [verificationToken, setVerificationToken] = useState<string | null>(null);

  // Countdown timer for Step 2 (300 seconds = 5 mins)
  const [timeLeft, setTimeLeft] = useState<number>(300);
  const [isTimerActive, setIsTimerActive] = useState<boolean>(false);

  useEffect(() => {
    let timer: any = null;
    if (isTimerActive && timeLeft > 0) {
      timer = setInterval(() => {
        setTimeLeft((prev) => prev - 1);
      }, 1000);
    } else if (timeLeft === 0 && isTimerActive) {
      setIsTimerActive(false);
      setError('인증 유효시간(5분)이 만료되었습니다. 인증번호를 다시 발송해주세요.');
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isTimerActive, timeLeft]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  // Step 1: Send Verification Code
  const handleSendCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (!email.trim() || !currentPassword.trim()) {
      setError('이메일과 현재 비밀번호를 모두 입력해 주세요.');
      return;
    }

    try {
      setLoading(true);
      const res = await authApi.sendVerificationCode({
        email: email.trim(),
        password: currentPassword,
      });

      setStep(2);
      setTimeLeft(res.expires_in_seconds || 300);
      setIsTimerActive(true);
      if (res.demo_code) {
        setDemoCode(res.demo_code);
      }
      setSuccessMessage(res.message || '인증번호가 이메일로 전송되었습니다.');
    } catch (err: any) {
      setError(err.message || '인증번호 발송 실패');
    } finally {
      setLoading(false);
    }
  };

  // Step 2: Verify Code
  const handleVerifyCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (!verificationCode.trim()) {
      setError('6자리 인증번호를 입력해 주세요.');
      return;
    }

    try {
      setLoading(true);
      const res = await authApi.verifyCode({
        email: email.trim(),
        code: verificationCode.trim(),
      });

      if (res.verification_token) {
        setVerificationToken(res.verification_token);
        setIsTimerActive(false);
        setStep(3);
        setSuccessMessage('이메일 인증이 성공적으로 완료되었습니다.');
      }
    } catch (err: any) {
      setError(err.message || '인증번호가 유효하지 않습니다.');
    } finally {
      setLoading(false);
    }
  };

  // Step 3: Change Password
  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (!verificationToken) {
      setError('인증 토큰이 유효하지 않습니다. Step 1부터 다시 진행해주세요.');
      return;
    }

    if (newPassword.length < 8) {
      setError('새 비밀번호는 8자 이상이어야 합니다.');
      return;
    }

    // Password Complexity Rule check (letter + number + special char)
    const hasLetter = /[a-zA-Z]/.test(newPassword);
    const hasNumber = /[0-9]/.test(newPassword);
    const hasSpecial = /[^a-zA-Z0-9]/.test(newPassword);
    if (!hasLetter || !hasNumber || !hasSpecial) {
      setError('비밀번호는 영문, 숫자, 특수문자를 모두 포함해야 합니다.');
      return;
    }

    if (newPassword !== newPasswordConfirm) {
      setError('새 비밀번호와 비밀번호 확인이 일치하지 않습니다.');
      return;
    }

    try {
      setLoading(true);
      const res = await authApi.changePassword({
        email: email.trim(),
        verification_token: verificationToken,
        new_password: newPassword,
      });

      setSuccessMessage(res.message || '비밀번호가 성공적으로 변경되었습니다.');
      setTimeout(() => {
        if (onSuccessReturn) {
          onSuccessReturn();
        }
      }, 2000);
    } catch (err: any) {
      setError(err.message || '비밀번호 변경 실패');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto py-6">
      {/* Container Card */}
      <div className="bg-white/95 backdrop-blur-xl rounded-3xl border border-slate-200/90 shadow-xl overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-indigo-900 via-indigo-800 to-slate-900 p-8 text-white relative">
          <div className="flex items-center space-x-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/30 backdrop-blur-md border border-indigo-400/40 flex items-center justify-center text-indigo-300">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-xl font-extrabold tracking-tight">계정 보안 및 비밀번호 변경</h2>
              <p className="text-xs text-indigo-200/80 font-medium">
                안전한 이메일 인증 절차를 거쳐 신규 비밀번호를 설정합니다.
              </p>
            </div>
          </div>

          {/* Stepper Progress Bar */}
          <div className="mt-8 grid grid-cols-3 gap-2">
            <div
              className={`h-1.5 rounded-full transition-all duration-300 ${
                step >= 1 ? 'bg-indigo-400' : 'bg-slate-700/60'
              }`}
            />
            <div
              className={`h-1.5 rounded-full transition-all duration-300 ${
                step >= 2 ? 'bg-indigo-400' : 'bg-slate-700/60'
              }`}
            />
            <div
              className={`h-1.5 rounded-full transition-all duration-300 ${
                step >= 3 ? 'bg-indigo-400' : 'bg-slate-700/60'
              }`}
            />
          </div>

          <div className="flex justify-between text-[11px] font-bold text-indigo-200 mt-2">
            <span className={step === 1 ? 'text-white' : 'opacity-60'}>1. 본인 확인</span>
            <span className={step === 2 ? 'text-white' : 'opacity-60'}>2. 이메일 인증번호</span>
            <span className={step === 3 ? 'text-white' : 'opacity-60'}>3. 비밀번호 변경</span>
          </div>
        </div>

        {/* Content Body */}
        <div className="p-8">
          {/* Notifications */}
          {error && (
            <div className="mb-6 bg-rose-50 border border-rose-200/90 rounded-2xl p-4 flex items-start space-x-3 text-rose-800 text-xs font-semibold animate-shake">
              <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold text-sm">확인이 필요합니다</p>
                <p className="mt-0.5">{error}</p>
              </div>
            </div>
          )}

          {successMessage && (
            <div className="mb-6 bg-emerald-50 border border-emerald-200/90 rounded-2xl p-4 flex items-start space-x-3 text-emerald-800 text-xs font-semibold">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold text-sm">안내</p>
                <p className="mt-0.5">{successMessage}</p>
              </div>
            </div>
          )}

          {/* STEP 1 FORM */}
          {step === 1 && (
            <form onSubmit={handleSendCode} className="space-y-5">
              <div>
                <label className="block text-xs font-extrabold text-slate-700 uppercase tracking-wider mb-2">
                  로그인 아이디 (이메일)
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="nj445325@gmail.com"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2.5 text-sm font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-extrabold text-slate-700 uppercase tracking-wider mb-2">
                  현재 비밀번호
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
                  <input
                    type={showCurrentPassword ? 'text' : 'password'}
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder="현재 설정되어 있는 비밀번호 입력"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-10 py-2.5 text-sm font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                    className="absolute right-3.5 top-3 text-slate-400 hover:text-slate-600"
                  >
                    {showCurrentPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="pt-4">
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white font-extrabold py-3 px-4 rounded-xl text-sm shadow-lg shadow-indigo-500/25 flex items-center justify-center space-x-2 transition-all disabled:opacity-50"
                >
                  {loading ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <span>인증번호 받기</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </div>
            </form>
          )}

          {/* STEP 2 FORM */}
          {step === 2 && (
            <form onSubmit={handleVerifyCode} className="space-y-5">
              {demoCode && (
                <div className="bg-indigo-50/80 border border-indigo-200 rounded-2xl p-3.5 text-xs text-indigo-900 flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Sparkles className="w-4 h-4 text-indigo-600" />
                    <span>발송된 6자리 인증번호 (시연용): </span>
                  </div>
                  <span className="font-extrabold text-sm tracking-wider text-indigo-700 bg-white px-2.5 py-1 rounded-lg border border-indigo-200 shadow-2xs">
                    {demoCode}
                  </span>
                </div>
              )}

              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="block text-xs font-extrabold text-slate-700 uppercase tracking-wider">
                    이메일 6자리 인증번호
                  </label>
                  <div className="flex items-center space-x-1.5 text-xs font-extrabold text-rose-600 bg-rose-50 px-2.5 py-0.5 rounded-full border border-rose-200/60">
                    <Clock className="w-3.5 h-3.5" />
                    <span>남은 시간 {formatTime(timeLeft)}</span>
                  </div>
                </div>
                <div className="relative">
                  <KeyRound className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
                  <input
                    type="text"
                    maxLength={6}
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value)}
                    placeholder="6자리 숫자 입력"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2.5 text-base tracking-widest font-extrabold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
                    required
                  />
                </div>
              </div>

              <div className="flex items-center space-x-3 pt-2">
                <button
                  type="button"
                  onClick={() => setStep(1)}
                  className="w-1/3 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold py-3 px-4 rounded-xl text-sm transition-all"
                >
                  이전 단계
                </button>
                <button
                  type="submit"
                  disabled={loading || timeLeft === 0}
                  className="w-2/3 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white font-extrabold py-3 px-4 rounded-xl text-sm shadow-lg shadow-indigo-500/25 flex items-center justify-center space-x-2 transition-all disabled:opacity-50"
                >
                  {loading ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <span>인증 확인</span>
                      <CheckCircle2 className="w-4 h-4" />
                    </>
                  )}
                </button>
              </div>
            </form>
          )}

          {/* STEP 3 FORM */}
          {step === 3 && (
            <form onSubmit={handleChangePassword} className="space-y-5">
              <div>
                <label className="block text-xs font-extrabold text-slate-700 uppercase tracking-wider mb-2">
                  새 비밀번호
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
                  <input
                    type={showNewPassword ? 'text' : 'password'}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="8자 이상 (영문, 숫자, 특수문자 포함)"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-10 py-2.5 text-sm font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowNewPassword(!showNewPassword)}
                    className="absolute right-3.5 top-3 text-slate-400 hover:text-slate-600"
                  >
                    {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-extrabold text-slate-700 uppercase tracking-wider mb-2">
                  새 비밀번호 확인
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
                  <input
                    type={showNewPassword ? 'text' : 'password'}
                    value={newPasswordConfirm}
                    onChange={(e) => setNewPasswordConfirm(e.target.value)}
                    placeholder="새 비밀번호 다시 입력"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2.5 text-sm font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
                    required
                  />
                </div>
              </div>

              <div className="pt-4">
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white font-extrabold py-3.5 px-4 rounded-xl text-sm shadow-lg shadow-emerald-500/25 flex items-center justify-center space-x-2 transition-all disabled:opacity-50"
                >
                  {loading ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4" />
                      <span>비밀번호 변경 완료</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
