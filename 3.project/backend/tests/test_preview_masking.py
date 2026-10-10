import pytest
from PIL import Image
from backend.app.services import preview_masking_service as masking


def words_line(values, y=10):
    return {'text':' '.join(values), 'words':[{'text':value,'bounding_rect':{
        'x':10+index*100,'y':y,'width':80,'height':20}} for index,value in enumerate(values)]}


def test_split_supplier_and_unknown_buyer_names_are_masked_but_issue_date_is_not(monkeypatch):
    lines=[words_line(['상호:', '가상', '공급업체']),words_line(['상호:', '다른', '구매업체'],40),
           words_line(['발행일:', '2026-09-01'],70),words_line(['번호:', '220-88-12345'],100)]
    monkeypatch.setattr(masking,'_safe_winocr_recognize',lambda *a,**k:{'lines':lines})
    with Image.new('RGB',(450,150),'white') as image:
        protected=masking.mask_image_with_ocr(image,{'company_name':'가상 공급업체'})
        try:
            assert protected.getpixel((120,15))==(45,45,45)
            assert protected.getpixel((220,15))==(45,45,45)
            assert protected.getpixel((220,45))==(45,45,45)
            assert protected.getpixel((120,75))==(255,255,255)
            assert protected.getpixel((120,105))==(45,45,45)
            assert protected.getpixel((20,15))==(255,255,255)
        finally:
            protected.close()


def test_company_and_date_on_same_line_preserve_date(monkeypatch):
    monkeypatch.setattr(masking,'_safe_winocr_recognize',lambda *a,**k:{
        'lines':[words_line(['상호:', '공급업체', '발행일:', '2026-09-01'])]})
    with Image.new('RGB',(450,80),'white') as image:
        protected=masking.mask_image_with_ocr(image)
        try:
            assert protected.getpixel((120,15))==(45,45,45)
            assert protected.getpixel((320,15))==(255,255,255)
        finally:
            protected.close()


@pytest.mark.parametrize('result',[None,{'lines':[]},{'lines':[{'text':'상호: 공급업체','words':[]}]}])
def test_missing_ocr_positions_fail_closed(monkeypatch,result):
    monkeypatch.setattr(masking,'_safe_winocr_recognize',lambda *a,**k:result)
    with Image.new('RGB',(200,100),'white') as image:
        with pytest.raises(RuntimeError):
            masking.mask_image_with_ocr(image)


def test_export_text_covers_old_names_and_keeps_dates_and_amounts():
    text='과거 업체: 이전 공급업체\n상호: 새로운 공급업체\n발행일: 2026-09-01\n합계금액: 110원\n사업자번호: 220-88-12345'
    result=masking.mask_export_text(text,{'company_name':['이전 공급업체','새로운 공급업체']})
    assert '이전 공급업체' not in result and '새로운 공급업체' not in result
    assert '220-88-12345' not in result and '2026-09-01' in result and '110원' in result


@pytest.mark.parametrize('text,expected', [
    ('계좌번호: 123456789012', '123456789012'),
    ('대표 홍길동', '홍길동'),
    ('담당자 홍길동', '홍길동'),
    ('가상업체 주식회사', '가상업체 주식회사'),
    ('123-456-12345678', '123-456-12345678'),
])
def test_shared_native_policy_preserves_existing_sensitive_patterns(text, expected):
    spans = masking.sensitive_spans(text)
    assert any(expected in text[start:end] for start, end in spans)


def test_multiline_native_labels_do_not_erase_following_dates_amounts():
    text = '상호: 가상업체\r\n발행일: 2026-09-01\r\n합계: 110\r\n성명: 홍길동'
    spans = masking.sensitive_spans(text)
    values = [text[start:end] for start, end in spans]
    assert '가상업체' in values and '홍길동' in values
    assert not any('2026' in value or '110' in value for value in values)


def test_shared_policy_does_not_treat_settlement_header_as_representative_name():
    for text in ('대표 최종 확인 상태', '자동 검사 상태', '현재 자료 최종 확인일 (한국시간)'):
        assert masking.mask_export_text(text) == text


@pytest.mark.parametrize('text,name', [('대표 김철수 (인)', '김철수'),
    ('대표 김 철 수 (인)', '김 철 수'), ('대표: 김철수 (서명)', '김철수'),
    ('대표 김철수 인', '김철수')])
def test_bare_representative_signature_retains_native_name_coverage(text, name):
    assert any(name in text[start:end] for start, end in masking.sensitive_spans(text))
