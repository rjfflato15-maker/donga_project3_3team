import React, { useState } from 'react';
import { PipelineStep } from '../types';
import { api } from '../api/client';
import { X, Play, Loader2, Sparkles, Database } from 'lucide-react';

interface PipelineSimulatorProps {
  contractId: number;
  isOpen: boolean;
  onClose: () => void;
  onCompleted?: () => void;
}

export const PipelineSimulator: React.FC<PipelineSimulatorProps> = ({
  contractId,
  isOpen,
  onClose,
  onCompleted,
}) => {
  const [running, setRunning] = useState(false);
  const [steps, setSteps] = useState<PipelineStep[]>([]);
  const [activeStepIdx, setActiveStepIdx] = useState<number | null>(null);

  if (!isOpen) return null;

  const handleRunSimulation = async () => {
    setRunning(true);
    try {
      const res = await api.simulatePipeline(contractId);
      setSteps(res.steps);
      setActiveStepIdx(0);
      if (onCompleted) onCompleted();
    } catch (err) {
      console.error('Simulation error:', err);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header matching Slide 7 */}
        <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-gradient-to-r from-slate-50 to-blue-50/30">
          <div>
            <div className="flex items-center space-x-2">
              <Sparkles className="w-5 h-5 text-amber-500" />
              <h3 className="text-base font-bold text-slate-900">
                자동검수 데이터 처리 시뮬레이터 (ERD v1.1 파이프라인)
              </h3>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              원본 업로드 → 비동기 마스킹·검증(1:0..1) → AI 최신 추출 → 정규화 → 최종 대조 검수
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 rounded-xl transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Simulator body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          {/* Action button */}
          <div className="flex items-center justify-between p-4 bg-slate-50 rounded-xl border border-slate-200">
            <div>
              <span className="text-xs font-bold text-slate-700 block">파이프라인 실행 상태</span>
              <span className="text-xs text-slate-500">
                {steps.length > 0 ? '5단계 검수 프로세스 완료' : '시스템 대기 중'}
              </span>
            </div>
            <button
              onClick={handleRunSimulation}
              disabled={running}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white font-bold text-xs rounded-xl shadow-sm transition-all"
            >
              {running ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>시뮬레이션 진행 중...</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-white" />
                  <span>▶ 검수 시뮬레이션 실행</span>
                </>
              )}
            </button>
          </div>

          {/* 5-Step Process Bar matching slide 7 */}
          <div className="grid grid-cols-1 sm:grid-cols-5 gap-2">
            {[
              { num: 1, title: '계약/문서 업로드', sub: 'CONTRACTS, DOCUMENTS' },
              { num: 2, title: '마스킹 & 국세청', sub: '1:0..1 비동기 결과 적재' },
              { num: 3, title: 'AI OCR 분석', sub: '최신 추출 레코드 1:0..1' },
              { num: 4, title: '문서별 필드 정규화', sub: '가변 필드 매핑' },
              { num: 5, title: '최종 대조 검수', sub: 'extract_id 기반 대조' },
            ].map((s, idx) => {
              const stepResult = steps.find((item) => item.step === s.num);
              const isCompleted = !!stepResult;
              const isSelected = activeStepIdx === idx;

              return (
                <div
                  key={s.num}
                  onClick={() => isCompleted && setActiveStepIdx(idx)}
                  className={`p-3 rounded-xl border transition-all text-center ${
                    isCompleted
                      ? isSelected
                        ? 'bg-blue-50 border-blue-400 ring-2 ring-blue-400/20 cursor-pointer shadow-sm'
                        : 'bg-emerald-50/50 border-emerald-200 hover:bg-emerald-50 cursor-pointer'
                      : 'bg-slate-50 border-slate-200 text-slate-400'
                  }`}
                >
                  <div
                    className={`w-6 h-6 rounded-full mx-auto mb-1.5 flex items-center justify-center text-xs font-bold ${
                      isCompleted
                        ? 'bg-emerald-600 text-white'
                        : 'bg-slate-200 text-slate-600'
                    }`}
                  >
                    {isCompleted ? '✓' : s.num}
                  </div>
                  <div className="text-xs font-bold text-slate-800 line-clamp-1">{s.title}</div>
                  <div className="text-[10px] text-slate-400 mt-0.5 line-clamp-1">{s.sub}</div>
                </div>
              );
            })}
          </div>

          {/* Active Step Details */}
          {activeStepIdx !== null && steps[activeStepIdx] && (
            <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
              <div className="flex items-center space-x-2 mb-2">
                <Database className="w-4 h-4 text-blue-600" />
                <h4 className="text-sm font-bold text-slate-900">
                  단계 {steps[activeStepIdx].step}: {steps[activeStepIdx].title}
                </h4>
              </div>
              <p className="text-xs font-semibold text-slate-700 mb-3">
                {steps[activeStepIdx].message}
              </p>

              <div className="bg-white p-3 rounded-lg border border-slate-200 text-xs font-mono max-h-48 overflow-y-auto">
                <pre className="text-slate-700 whitespace-pre-wrap">
                  {JSON.stringify(steps[activeStepIdx].details, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-white border border-slate-300 text-slate-700 font-semibold text-xs rounded-xl hover:bg-slate-50 transition-colors"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
};
