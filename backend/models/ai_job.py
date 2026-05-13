from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class AiJob(Base):
    __tablename__ = "ai_jobs"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    request_type = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False, default="queued", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    encrypted_payload = Column(Text, nullable=True)
    encrypted_result = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    complaint = relationship("Complaint", back_populates="ai_jobs")
    user = relationship("User", back_populates="ai_jobs")
    ai_usage_logs = relationship("AiUsageLog", back_populates="ai_job")
