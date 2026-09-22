# 통일 ERD 및 데이터베이스 설계서 (v1.1)

계약 및 증빙문서 자동검수 시스템의 정규화 개선 데이터 모델 설계서입니다.

---

## 1. ERD 다이어그램 (Mermaid)

```mermaid
erDiagram
    USERS ||--o{ CONTRACTS : creates
    CONTRACTS ||--o{ DOCUMENTS : contains
    DOCUMENTS ||--o| BUSINESS_VERIFICATION : verifies
    DOCUMENTS ||--o| DOCUMENT_MASKINGS : masks
    DOCUMENTS ||--o| DOCUMENT_EXTRACTS : extracts
    DOCUMENT_EXTRACTS ||--o{ VALIDATION_RESULTS : validates
    CONTRACTS ||--o{ VALIDATION_RESULTS : has

    USERS {
        int user_id PK
        string email UK
        string password
    }

    CONTRACTS {
        int contract_id PK
        int user_id FK
        string title
        string vendor_name
        string business_number
        decimal contract_amount
        string review_status
        datetime created_at
        datetime updated_at
    }

    DOCUMENTS {
        int document_id PK
        int contract_id FK
        string file_name
        string storage_path
        string document_type
        float class_confidence
        string processing_status
        datetime uploaded_at
    }

    DOCUMENT_MASKINGS {
        int masking_id PK
        int document_id FK, UQ
        string masked_file_path
        string masking_status
        int masked_item_count
        json masked_types
        datetime processed_at
    }

    DOCUMENT_EXTRACTS {
        int extract_id PK
        int document_id FK, UQ
        string extracted_vendor_name
        string extracted_vendor_reg_no
        decimal extracted_amount
        string extracted_date
        string extracted_status
        float confidence
        json raw_fields
    }

    BUSINESS_VERIFICATION {
        int verification_id PK
        int document_id FK, UQ
        string business_number
        string business_status
        datetime verified_at
    }

    VALIDATION_RESULTS {
        int validation_id PK
        int contract_id FK
        int extract_id FK
        string validation_type
        boolean is_match
        string status
        string field
        string expected
        string actual
        text memo
        datetime created_at
    }
```

---

## 2. 정규화 개선 및 설계 원칙

1. **DOCUMENTS 마스킹 중복 제거**:
   - 원본 문서 메타데이터(파일명, 물리적 저장경로, 문서유형)를 `DOCUMENTS` 단일 엔티티에서 관리.
2. **1:0..1 비동기 관계 현실화**:
   - 국세청 진위검증(`BUSINESS_VERIFICATION`), 개인정보 마스킹(`DOCUMENT_MASKINGS`), AI 구조화 추출(`DOCUMENT_EXTRACTS`)을 1:0..1 관계로 분리하여 비동기 처리 파이프라인 수용.
3. **검수 중복 FK 제거**:
   - `VALIDATION_RESULTS`에 단일 대조 경로 보장 및 무결성 확보.
