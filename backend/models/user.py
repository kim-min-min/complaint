from sqlalchemy import Column, Integer, String, BigInteger, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"

    # 서비스 내부 관리를 위한 고유 번호
    id = Column(Integer, primary_key=True, index=True)
    
    # 카카오에서 제공하는 고유 회원번호 (매우 크므로 BigInteger 권장)
    kakao_id = Column(BigInteger, unique=True, nullable=False, index=True)
    
    # 사용자 닉네임
    nickname = Column(String, nullable=False)
    
    # 이메일 (카카오 설정에 따라 없을 수도 있으므로 nullable=True)
    email = Column(String, unique=True, nullable=True)
    
    # 가입 및 수정 시간 자동 기록
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    complaints = relationship("Complaint", back_populates="user")
    ai_jobs = relationship("AiJob", back_populates="user")
    ai_usage_logs = relationship("AiUsageLog", back_populates="user")
