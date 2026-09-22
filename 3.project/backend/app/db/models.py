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
)
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)

    contracts = relationship("Contract", back_populates="user", cascade="all, delete-orphan")


class Contract(Base):
    __tablename__ = "contracts"

    contract_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
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
