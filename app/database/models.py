from datetime import datetime
from sqlalchemy import (Column, Integer, String, Boolean, DateTime,
                        ForeignKey, UniqueConstraint)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Year(Base):
    __tablename__ = "years"
    id = Column(Integer, primary_key=True)
    year = Column(Integer, unique=True, nullable=False)
    months = relationship("MonthSetting", cascade="all, delete-orphan",
                          back_populates="year_ref")


class MonthSetting(Base):
    __tablename__ = "month_settings"
    __table_args__ = (UniqueConstraint("year_id", "month"),)
    id = Column(Integer, primary_key=True)
    year_id = Column(Integer, ForeignKey("years.id"), nullable=False)
    month = Column(Integer, nullable=False)
    norm_hours = Column(Integer, default=0)
    holidays = Column(String, default="")
    year_ref = relationship("Year", back_populates="months")


class Setting(Base):
    __tablename__ = "settings"
    key = Column(String, primary_key=True)
    value = Column(String, default="")


class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True)
    full_name = Column(String, nullable=False)
    position = Column(String, default="")
    group = Column(String, default="security")
    is_signatory = Column(Boolean, default=False)
    auto_7h = Column(Boolean, default=False) # <--- НОВОЕ


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    doc_type = Column(String, nullable=False)
    group = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    instance_number = Column(Integer, default=0)
    manual_mode = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    rows = relationship("DocumentRow", cascade="all, delete-orphan",
                        back_populates="document")


class DocumentRow(Base):
    __tablename__ = "document_rows"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    employee_name = Column(String, default="")
    employee_position = Column(String, default="")
    auto_7h = Column(Boolean, default=False) # <--- НОВОЕ
    document = relationship("Document", back_populates="rows")
    cells = relationship("DocumentCell", cascade="all, delete-orphan",
                         back_populates="row")
    overrides = relationship("ManualOverride", cascade="all, delete-orphan",
                             back_populates="row")


class DocumentCell(Base):
    __tablename__ = "document_cells"
    __table_args__ = (UniqueConstraint("row_id", "day"),)
    id = Column(Integer, primary_key=True)
    row_id = Column(Integer, ForeignKey("document_rows.id"), nullable=False)
    day = Column(Integer, nullable=False)
    code = Column(String, default="")
    row = relationship("DocumentRow", back_populates="cells")


class ManualOverride(Base):
    __tablename__ = "manual_overrides"
    __table_args__ = (UniqueConstraint("row_id", "column_key"),)
    id = Column(Integer, primary_key=True)
    row_id = Column(Integer, ForeignKey("document_rows.id"), nullable=False)
    column_key = Column(String, nullable=False)
    value = Column(String, default="")
    row = relationship("DocumentRow", back_populates="overrides")
