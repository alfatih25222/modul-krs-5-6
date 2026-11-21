from sqlalchemy import Column, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class Mahasiswa(Base):
    __tablename__ = "mahasiswa"

    nim = Column(String(20), primary_key=True, index=True)
    nama = Column(String(100), nullable=False)
    semester_aktif = Column(Integer, nullable=False, default=1)
    max_sks = Column(Integer, nullable=False, default=24)

    krs_list = relationship("KRS", back_populates="mahasiswa", cascade="all, delete-orphan")
    nilai_lalu = relationship(
        "NilaiSemesterLalu", back_populates="mahasiswa", cascade="all, delete-orphan"
    )


class MataKuliah(Base):
    __tablename__ = "matakuliah"

    kode_mk = Column(String(20), primary_key=True, index=True)
    nama_mk = Column(String(120), nullable=False)
    sks = Column(Integer, nullable=False)
    hari = Column(String(20), nullable=False)
    jam_mulai = Column(String(10), nullable=False)
    jam_selesai = Column(String(10), nullable=False)
    sifat = Column(String(20), nullable=False, default="WAJIB")

    krs_details = relationship("KRSDetail", back_populates="matakuliah")
    prerequisites = relationship(
        "Prerequisite",
        foreign_keys="Prerequisite.kode_mk",
        back_populates="matakuliah",
        cascade="all, delete-orphan",
    )


class Prerequisite(Base):
    __tablename__ = "prerequisite"
    __table_args__ = (
        UniqueConstraint("kode_mk", "kode_mk_syarat", name="uq_prereq_mk_syarat"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    kode_mk = Column(String(20), ForeignKey("matakuliah.kode_mk"), nullable=False, index=True)
    kode_mk_syarat = Column(String(20), ForeignKey("matakuliah.kode_mk"), nullable=False)
    min_nilai_huruf = Column(String(5), nullable=False, default="C")

    matakuliah = relationship(
        "MataKuliah", foreign_keys=[kode_mk], back_populates="prerequisites"
    )


class NilaiSemesterLalu(Base):
    __tablename__ = "nilai_semester_lalu"
    __table_args__ = (
        UniqueConstraint("nim", "kode_mk", name="uq_nilai_nim_mk"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    nim = Column(String(20), ForeignKey("mahasiswa.nim"), nullable=False, index=True)
    kode_mk = Column(String(20), ForeignKey("matakuliah.kode_mk"), nullable=False)
    nilai_huruf = Column(String(5), nullable=False)

    mahasiswa = relationship("Mahasiswa", back_populates="nilai_lalu")


class KRS(Base):
    __tablename__ = "krs"
    __table_args__ = (
        UniqueConstraint("nim", "semester", name="uq_krs_nim_semester"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    nim = Column(String(20), ForeignKey("mahasiswa.nim"), nullable=False, index=True)
    semester = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="DRAFT")
    approved_by = Column(String(50), nullable=True)
    catatan_dosen = Column(Text, nullable=True)

    mahasiswa = relationship("Mahasiswa", back_populates="krs_list")
    details = relationship(
        "KRSDetail", back_populates="krs", cascade="all, delete-orphan"
    )


class KRSDetail(Base):
    __tablename__ = "krs_detail"
    __table_args__ = (
        UniqueConstraint("krs_id", "kode_mk", name="uq_krs_detail_mk"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    krs_id = Column(Integer, ForeignKey("krs.id"), nullable=False, index=True)
    kode_mk = Column(String(20), ForeignKey("matakuliah.kode_mk"), nullable=False)

    krs = relationship("KRS", back_populates="details")
    matakuliah = relationship("MataKuliah", back_populates="krs_details")
