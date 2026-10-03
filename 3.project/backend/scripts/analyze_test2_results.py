import sys
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PROJECT))
from backend.test2_result_analysis import write_report

if __name__=='__main__':
    report=write_report(PROJECT,PROJECT/'docs/eval/test2/result_audit')
    print('저장 예측 분석 완료. 추가 추론 0회, 가드 실행 0회.')
    print(report['paired_comparison'])
