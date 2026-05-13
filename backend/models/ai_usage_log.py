from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class AiUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="SET NULL"), nullable=True, index=True)
    ai_job_id = Column(Integer, ForeignKey("ai_jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    usage_date = Column(Date, nullable=False, index=True)
    request_type = Column(String(30), nullable=False)
    model = Column(String(80), nullable=False)
    status = Column(String(30), nullable=False)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    cost_estimate_usd = Column(Numeric(12, 6), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="ai_usage_logs")
    complaint = relationship("Complaint", back_populates="ai_usage_logs")
    ai_job = relationship("AiJob", back_populates="ai_usage_logs")
