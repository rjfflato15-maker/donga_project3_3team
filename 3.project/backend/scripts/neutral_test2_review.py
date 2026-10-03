import argparse
import json
import sys
from pathlib import Path

PROJECT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PROJECT))
from backend.neutral_test2_review import build,compare,digest,write_new_or_identical

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Separate neutral recheck; never imports or changes labels.')
    parser.add_argument('--result',type=Path,help='Compare a real exported neutral response JSON; omit to build the page.')
    args=parser.parse_args()
    if args.result:
        raw=json.loads(args.result.read_text('utf-8-sig'))
        result=compare(PROJECT,raw)
        result['response_sha256']=digest(args.result)
        output=PROJECT/'docs/eval/test2/neutral_recheck'/result['response_sha256'][:16]
        source_text=args.result.read_bytes().decode('utf-8')  # preserve BOM/newlines too
        write_new_or_identical(output/'source_result.json',source_text)
        write_new_or_identical(output/'agreement.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        counts=result['counts']
        text=f"# test2 중립 문구 재확인\n\n기존 정답·답변·점수 변경 없음.\n\n일치 {counts['AGREE']}, 불일치 {counts['DISAGREE']}, 판단 어려움 {counts['UNCERTAIN']}, 미응답 {counts['UNANSWERED']} (선정 20개).\n\n비교 가능한 응답 {result['comparable_count']}개 중 일치율: {result['agreement_among_comparable']!r}. 전체 20개 기준 일치 비율: {result['agreement_over_all_selected']:.1%}.\n\nN/A 원문 사실 질문은 상태 라벨 일치로 계산하지 않으며 JSON의 by_construct로 구분한다. 같은 사람의 반복 확인이므로 기억·학습 효과를 분리할 수 없다.\n"
        write_new_or_identical(output/'README.md',text)
        print(output)
    else:
        public=build(PROJECT)
        print(f"중립 문항 {len(public['items'])}개 준비. 기존 답변·정답·점수 변경 없음.")
