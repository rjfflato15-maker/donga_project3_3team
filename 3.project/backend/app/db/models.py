from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Boolean,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "app_users"

    user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)

    contracts = relationship("Contract", back_populates="user", cascade="all, delete-orphan")


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), nullable=False, index=True)
    code = Column(String(10), nullable=False)
    verification_token = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    is_verified = Column(Boolean, default=False)
    attempt_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)



class Contract(Base):
    __tablename__ = "contracts"

    contract_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("app_users.user_id"), nullable=True)
    title = Column(String(200), nullable=False)
    vendor_name = Column(String(200), nullable=False)
    business_number = Column(String(50), nullable=False)
    contract_amount = Column(Float, nullable=False, default=0.0)
    review_status = Column(String(50), nullable=False, default="REGISTERED")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="contracts")
    documents = relationship("Document", back_populates="contract", cascade="all, delete-orphan")
    validation_results = relationship("ValidationResult", back_populates="contract", cascade="all, delete-orphan")
    resubmission_requests = relationship("ResubmissionRequest", cascade="all, delete-orphan")
    approval_signoffs = relationship("ApprovalSignoff", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    document_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    contract_id = Column(Integer, ForeignKey("contracts.contract_id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    storage_path = Column(String(500), nullable=False)
    document_type = Column(String(50), nullable=False, default="unknown")
    class_confidence = Column(Float, nullable=True, default=0.0)
    processing_status = Column(String(50), nullable=False, default="UPLOADED")
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    contract = relationship("Contract", back_populates="documents")
    masking = relationship("DocumentMasking", back_populates="document", uselist=False, cascade="all, delete-orphan")
    extract = relationship("DocumentExtract", back_populates="document", uselist=False, cascade="all, delete-orphan")
    verification = relationship("BusinessVerification", back_populates="document", uselist=False, cascade="all, delete-orphan")
    version = relationship("DocumentVersion", uselist=False, cascade="all, delete-orphan")


class DocumentMasking(Base):
    __tablename__ = "document_maskings"

    masking_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.document_id"), unique=True, nullable=False)
    masked_file_path = Column(String(500), nullable=True)
    masking_status = Column(String(50), nullable=False, default="NOT_STARTED")
    masked_item_count = Column(Integer, nullable=False, default=0)
    masked_types = Column(Text, nullable=True)  # Comma-separated or JSON list of detected categories
    processed_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="masking")


class DocumentExtract(Base):
    __tablename__ = "document_extracts"

    extract_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.document_id"), unique=True, nullable=False)
    extracted_vendor_name = Column(String(200), nullable=True)
    extracted_vendor_reg_no = Column(String(50), nullable=True)
    extracted_amount = Column(Float, nullable=True)
    extracted_date = Column(String(50), nullable=True)
    extracted_status = Column(String(50), nullable=False, default="COMPLETED")
    confidence = Column(Float, nullable=True, default=0.0)
    raw_fields = Column(Text, nullable=True)  # JSON formatted fields

    document = relationship("Document", back_populates="extract")
    validation_results = relationship("ValidationResult", back_populates="extract")


class BusinessVerification(Base):
    __tablename__ = "business_verification"

    verification_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.document_id"), unique=True, nullable=False)
    business_number = Column(String(50), nullable=False)
    business_status = Column(String(50), nullable=False, default="계속사업자")  # 계속사업자, 휴업자, 폐업자
    verified_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="verification")


class ValidationResult(Base):
    __tablename__ = "validation_results"

    validation_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    contract_id = Column(Integer, ForeignKey("contracts.contract_id"), nullable=False)
    extract_id = Column(Integer, ForeignKey("document_extracts.extract_id"), nullable=True)
    validation_type = Column(String(100), nullable=False)  # REQUIRED_DOCUMENTS, BUSINESS_NO_MATCH, AMOUNT_MATCH, BUSINESS_STATUS
    is_match = Column(Boolean, nullable=False, default=True)
    status = Column(String(50), nullable=False, default="PASS")  # PASS, REVIEW, MISSING, FAIL
    field = Column(String(100), nullable=True)
    expected = Column(Text, nullable=True)
    actual = Column(Text, nullable=True)
    memo = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    contract = relationship("Contract", back_populates="validation_results")
    extract = relationship("DocumentExtract", back_populates="validation_results")


class UserProfile(Base):
    __tablename__ = "pilot_user_profiles"
    user_id = Column(Integer, ForeignKey("app_users.user_id"), primary_key=True)
    role = Column(String(30), nullable=False)
    display_name = Column(String(80), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    must_change_password = Column(Boolean, nullable=False, default=True)


class AuthSession(Base):
    __tablename__ = "pilot_auth_sessions"
    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("app_users.user_id"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)


class CompanySetting(Base):
    __tablename__ = "pilot_company_settings"
    key = Column(String(80), primary_key=True)
    value = Column(Text, nullable=False)


class ContractWorkflow(Base):
    __tablename__ = "pilot_contract_workflows"
    contract_id = Column(Integer, ForeignKey("contracts.contract_id", ondelete="CASCADE"), primary_key=True)
    revision = Column(Integer, nullable=False, default=1)
    amount_basis = Column(String(20), nullable=False, default="UNKNOWN")
    tax_amount = Column(Float, nullable=True)
    payment_mode = Column(String(20), nullable=False, default="FULL")


class ContractReview(Base):
    __tablename__ = "pilot_contract_reviews"
    review_id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(Integer, nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    actor_id = Column(Integer, nullable=False)
    actor_name = Column(String(80), nullable=False)
    decision = Column(String(30), nullable=False)
    note = Column(Text, nullable=False)
    snapshot_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AuditEvent(Base):
    __tablename__ = "pilot_audit_events"
    event_id = Column(Integer, primary_key=True, autoincrement=True)
    actor_id = Column(Integer, nullable=True)
    actor_name = Column(String(80), nullable=False)
    action = Column(String(80), nullable=False)
    contract_id = Column(Integer, nullable=True, index=True)
    document_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class DocumentFileInfo(Base):
    __tablename__ = "pilot_document_files"
    document_id = Column(Integer, ForeignKey("documents.document_id", ondelete="CASCADE"), primary_key=True)
    sha256 = Column(String(64), nullable=False)
    byte_size = Column(Integer, nullable=False)


class ResubmissionRequest(Base):
    __tablename__ = "pilot_resubmission_requests"
    request_id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(Integer, ForeignKey("contracts.contract_id", ondelete="CASCADE"), nullable=False, index=True)
    contact_method = Column(String(20), nullable=False)
    requested_on = Column(String(10), nullable=False)
    due_on = Column(String(10), nullable=True)
    memo = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="WAITING_RESPONSE")
    actor_id = Column(Integer, nullable=False)
    actor_name = Column(String(80), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, nullable=True)


class ApprovalSignoff(Base):
    __tablename__ = "pilot_approval_signoffs"
    signoff_id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(Integer, ForeignKey("contracts.contract_id", ondelete="CASCADE"), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    fingerprint = Column(String(64), nullable=False)
    cycle_review_id = Column(Integer, nullable=False, default=0)
    actor_id = Column(Integer, nullable=False)
    actor_name = Column(String(80), nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class DocumentVersion(Base):
    __tablename__ = "pilot_document_versions"
    document_id = Column(Integer, ForeignKey("documents.document_id", ondelete="CASCADE"), primary_key=True)
    logical_document_id = Column(Integer, nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    previous_document_id = Column(Integer, nullable=True)
    is_current = Column(Boolean, nullable=False, default=True)
    actor_id = Column(Integer, nullable=True)
    actor_name = Column(String(80), nullable=False)
    change_note = Column(Text, nullable=False)
    initial_fields_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    superseded_at = Column(DateTime, nullable=True)
    __table_args__ = (
        UniqueConstraint("logical_document_id", "version_number", name="uq_document_version_number"),
        Index("uq_current_logical_document", "logical_document_id", unique=True,
              sqlite_where=is_current.is_(True), postgresql_where=is_current.is_(True)),
    )
