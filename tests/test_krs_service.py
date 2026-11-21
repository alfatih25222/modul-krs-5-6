import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.krs_service import KRSService
from app.models import Mahasiswa, MataKuliah, NilaiSemesterLalu, Prerequisite


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


def test_alur_tambah_hapus_submit_dan_approve_krs(db_session):
    mhs = Mahasiswa(nim="2024010", nama="Raka Pratama", semester_aktif=3, max_sks=24)
    mk1 = MataKuliah(
        kode_mk="IF201",
        nama_mk="Struktur Data",
        sks=3,
        hari="Senin",
        jam_mulai="08:00",
        jam_selesai="10:30",
        sifat="WAJIB",
    )
    mk2 = MataKuliah(
        kode_mk="IF202",
        nama_mk="Algoritma Lanjut",
        sks=3,
        hari="Selasa",
        jam_mulai="10:00",
        jam_selesai="12:30",
        sifat="WAJIB",
    )
    prereq = Prerequisite(kode_mk="IF202", kode_mk_syarat="IF201", min_nilai_huruf="C")
    nilai = NilaiSemesterLalu(nim="2024010", kode_mk="IF201", nilai_huruf="B")
    db_session.add_all([mhs, mk1, mk2, prereq, nilai])
    db_session.commit()

    service = KRSService(db_session)

    res_add1 = service.add_course("2024010", "IF201")
    assert res_add1.success is True

    res_add2 = service.add_course("2024010", "IF202")
    assert res_add2.success is True

    res_rem = service.remove_course("2024010", "IF202")
    assert res_rem.success is True

    res_sub = service.submit_krs("2024010")
    assert res_sub.success is True

    res_app = service.approve_krs("2024010", dosen_pa_id="DSN01", approved=True, catatan="Disetujui")
    assert res_app.success is True


def test_validasi_bentrok_jadwal_dan_prasyarat(db_session):
    mhs = Mahasiswa(nim="2024011", nama="Nadia Putri", semester_aktif=3, max_sks=20)
    mk_awal = MataKuliah(
        kode_mk="IF101",
        nama_mk="Dasar Pemrograman",
        sks=3,
        hari="Senin",
        jam_mulai="08:00",
        jam_selesai="10:30",
        sifat="WAJIB",
    )
    mk_bentrok = MataKuliah(
        kode_mk="IF102",
        nama_mk="Pengantar Jaringan",
        sks=3,
        hari="Senin",
        jam_mulai="09:00",
        jam_selesai="11:30",
        sifat="WAJIB",
    )
    mk_syarat = MataKuliah(
        kode_mk="IF205",
        nama_mk="Rekayasa Perangkat Lunak",
        sks=3,
        hari="Rabu",
        jam_mulai="13:00",
        jam_selesai="15:30",
        sifat="WAJIB",
    )
    prereq = Prerequisite(kode_mk="IF205", kode_mk_syarat="IF101", min_nilai_huruf="C")
    nilai_kurang = NilaiSemesterLalu(nim="2024011", kode_mk="IF101", nilai_huruf="D")
    db_session.add_all([mhs, mk_awal, mk_bentrok, mk_syarat, prereq, nilai_kurang])
    db_session.commit()

    service = KRSService(db_session)
    assert service.add_course("2024011", "IF101").success is True
    assert service.add_course("2024011", "IF102").success is False
    assert service.add_course("2024011", "IF205").success is False
