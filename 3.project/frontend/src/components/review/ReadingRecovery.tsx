import { Upload } from 'lucide-react';

export function ReadingRecovery({ failed, canReissue, onReissue }: {
  failed: boolean; canReissue: boolean; onReissue: () => void;
}) {
  return <aside className="reading-recovery" aria-label="판독 문제 해결 안내">
    <strong>{failed ? '서류를 읽지 못했습니다' : '읽은 값을 원문에서 확인해 주세요'}</strong>
    <p>흐리거나 잘린 부분, 숫자를 덮은 도장이 있다면 선명한 파일을 다시 받아 주세요.</p>
    <ul>
      <li>문서 네 모서리가 나오도록 정면에서 촬영합니다.</li>
      <li>그림자·빛 반사를 피하고 금액과 사업자번호가 읽히는지 확인합니다.</li>
      <li>가능하면 사진 대신 거래처의 원본 PDF를 받습니다.</li>
    </ul>
    {canReissue && <button className="button" onClick={onReissue}><Upload size={14}/>선명한 수정본 올리기</button>}
    <small>새 파일은 이전 본을 보관하며 등록됩니다. 저장값과 결재를 다시 확인합니다.</small>
  </aside>;
}
