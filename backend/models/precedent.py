from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import UserDefinedType

from database import Base


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int):
        self.dimensions = dimensions

    def get_col_spec(self, **kw):
        return f"vector({self.dimensions})"


class Precedent(Base):
    __tablename__ = "precedents"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(60), nullable=False, default="law.go.kr")
    source_id = Column(String(80), nullable=False, unique=True, index=True)
    category = Column(String(80), nullable=False, index=True)
    case_number = Column(String(120), nullable=False, index=True)
    case_name = Column(String(500), nullable=False)
    primary_case_name = Column(String(200), nullable=True, index=True)
    court_name = Column(String(160), nullable=True)
    verdict_date = Column(String(40), nullable=True)
    verdict_type = Column(String(120), nullable=True)
    case_type = Column(String(80), nullable=True)
    charges = Column(JSONB, nullable=False, default=list)
    keywords = Column(JSONB, nullable=False, default=list)
    holding = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    fact_context = Column(Text, nullable=True)
    refs_articles = Column(Text, nullable=True)
    refs_cases = Column(Text, nullable=True)
    quality_score = Column(Float, nullable=False, default=0)
    rag_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    chunks = relationship("PrecedentChunk", back_populates="precedent", cascade="all, delete-orphan")


class PrecedentChunk(Base):
    __tablename__ = "precedent_chunks"

    id = Column(Integer, primary_key=True, index=True)
    precedent_id = Column(Integer, ForeignKey("precedents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_type = Column(String(40), nullable=False, index=True)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=False)
    weight = Column(Float, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    precedent = relationship("Precedent", back_populates="chunks")
