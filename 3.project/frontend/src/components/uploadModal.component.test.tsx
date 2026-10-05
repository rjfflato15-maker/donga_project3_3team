// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { UploadModal } from './UploadModal';

afterEach(cleanup);

const pick = (name = '견적서.pdf') => {
  const input = screen.getByLabelText('올릴 파일 고르기') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(['x'], name, { type: 'application/pdf' })] } });
};
const props = (over: Partial<React.ComponentProps<typeof UploadModal>> = {}) => ({
  contractId: 1, isOpen: true, onClose: () => undefined, onUpload: async () => undefined, loading: false, ...over,
});

describe('새 서류 추가 창의 파일 선택 상태', () => {
  it('취소(닫힘) 뒤 다시 열거나 다른 계약에서 열면 이전 파일이 없다', () => {
    const { rerender } = render(<UploadModal {...props()} />);
    pick();
    expect(screen.getByText('견적서.pdf')).toBeTruthy();
    rerender(<UploadModal {...props({ isOpen: false })} />);
    rerender(<UploadModal {...props()} />);
    expect(screen.queryByText('견적서.pdf')).toBeNull();
    pick('통장사본.pdf');
    rerender(<UploadModal {...props({ contractId: 2 })} />);
    expect(screen.queryByText('통장사본.pdf')).toBeNull();
    expect((screen.getByText('업로드 및 자동 검수 실행').closest('button') as HTMLButtonElement).disabled).toBe(true);
  });
  it('같은 창에서 실패하면 파일을 남겨 다시 시도할 수 있다', async () => {
    const onUpload = vi.fn().mockRejectedValue(new Error('서버 오류'));
    render(<UploadModal {...props({ onUpload })} />);
    pick();
    await act(async () => { fireEvent.click(screen.getByText('업로드 및 자동 검수 실행')); });
    expect(screen.getByRole('alert').textContent).toContain('서버 오류');
    expect(screen.getByText('견적서.pdf')).toBeTruthy();
  });
  it('업로드 중에 다른 계약으로 바뀌면 늦게 끝난 결과가 새 창을 닫거나 오류를 띄우지 않는다', async () => {
    let finish: () => void = () => undefined;
    const onClose = vi.fn();
    const onUpload = vi.fn((): Promise<void> => new Promise<void>((r) => { finish = r; }));
    const { rerender } = render(<UploadModal {...props({ onUpload, onClose })} />);
    pick();
    fireEvent.click(screen.getByText('업로드 및 자동 검수 실행'));
    rerender(<UploadModal {...props({ onUpload, onClose, contractId: 2 })} />);
    await act(async () => { finish(); });
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
