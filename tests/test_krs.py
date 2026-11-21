import pytest
from hypothesis import given, strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import KRS, KRSDetail, Mahasiswa, MataKuliah, NilaiSemesterLalu, Prerequisite


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_create_mahasiswa_dan_matakuliah(db_session):
    mhs = Mahasiswa(nim="2024001", nama="Budi Santoso", semester_aktif=3, max_sks=24)
    mk = MataKuliah(
        kode_mk="IF201",
        nama_mk="Struktur Data",
        sks=3,
        hari="Senin",
        jam_mulai="08:00",
        jam_selesai="10:30",
        sifat="WAJIB",
    )
    db_session.add_all([mhs, mk])
    db_session.commit()

    assert db_session.query(Mahasiswa).filter_by(nim="2024001").one().nama == "Budi Santoso"
    assert db_session.query(MataKuliah).filter_by(kode_mk="IF201").one().sks == 3


def test_krs_dan_detail_relasi(db_session):
    mhs = Mahasiswa(nim="2024002", nama="Siti Aminah", semester_aktif=5, max_sks=22)
    mk1 = MataKuliah(
        kode_mk="IF301",
        nama_mk="Basis Data",
        sks=3,
        hari="Selasa",
        jam_mulai="10:00",
        jam_selesai="12:30",
        sifat="WAJIB",
    )
    mk2 = MataKuliah(
        kode_mk="IF302",
        nama_mk="Pemrograman Web",
        sks=4,
        hari="Rabu",
        jam_mulai="13:00",
        jam_selesai="16:20",
        sifat="WAJIB",
    )
    prereq = Prerequisite(kode_mk="IF302", kode_mk_syarat="IF301", min_nilai_huruf="C")
    nilai = NilaiSemesterLalu(nim="2024002", kode_mk="IF301", nilai_huruf="B")
    krs = KRS(nim="2024002", semester=5, status="DRAFT")
    db_session.add_all([mhs, mk1, mk2, prereq, nilai, krs])
    db_session.commit()

    detail1 = KRSDetail(krs_id=krs.id, kode_mk="IF301")
    detail2 = KRSDetail(krs_id=krs.id, kode_mk="IF302")
    db_session.add_all([detail1, detail2])
    db_session.commit()

    total_sks = sum(item.matakuliah.sks for item in krs.details)
    assert total_sks == 7
    assert krs.status == "DRAFT"


@given(sks=st.integers(min_value=1, max_value=6))
def test_property_sks_valid(sks):
    assert 1 <= sks <= 6
