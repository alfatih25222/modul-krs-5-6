from typing import Optional
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.krs_service import KRSService
from app.models import KRS, Mahasiswa, MataKuliah

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Modul KRS API (Minggu 5-6)",
    description="API Kartu Rencana Studi: tambah/hapus MK, validasi Chain of Responsibility, state machine, submit, dan approval dosen PA.",
    version="1.0.0",
)


class CourseActionRequest(BaseModel):
    nim: str
    kode_mk: str


class ApproveKRSRequest(BaseModel):
    nim: str
    dosen_pa_id: str
    approved: bool = True
    catatan: Optional[str] = None


class MahasiswaCreateRequest(BaseModel):
    nim: str
    nama: str
    semester_aktif: int = 1
    max_sks: int = 24


class MataKuliahCreateRequest(BaseModel):
    kode_mk: str
    nama_mk: str
    sks: int
    hari: str
    jam_mulai: str
    jam_selesai: str


@app.get("/")
def root():
    return {
        "message": "Modul KRS API aktif",
        "docs": "/docs",
    }


@app.post("/mahasiswa")
def create_mahasiswa(payload: MahasiswaCreateRequest, db: Session = Depends(get_db)):
    existing = db.query(Mahasiswa).filter(Mahasiswa.nim == payload.nim).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Mahasiswa NIM {payload.nim} sudah ada")
    mhs = Mahasiswa(
        nim=payload.nim,
        nama=payload.nama,
        semester_aktif=payload.semester_aktif,
        max_sks=payload.max_sks,
    )
    db.add(mhs)
    db.commit()
    db.refresh(mhs)
    return {"success": True, "data": {"nim": mhs.nim, "nama": mhs.nama, "semester_aktif": mhs.semester_aktif}}


@app.post("/matakuliah")
def create_matakuliah(payload: MataKuliahCreateRequest, db: Session = Depends(get_db)):
    existing = db.query(MataKuliah).filter(MataKuliah.kode_mk == payload.kode_mk).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Mata kuliah {payload.kode_mk} sudah ada")
    mk = MataKuliah(
        kode_mk=payload.kode_mk,
        nama_mk=payload.nama_mk,
        sks=payload.sks,
        hari=payload.hari,
        jam_mulai=payload.jam_mulai,
        jam_selesai=payload.jam_selesai,
    )
    db.add(mk)
    db.commit()
    db.refresh(mk)
    return {"success": True, "data": {"kode_mk": mk.kode_mk, "nama_mk": mk.nama_mk, "sks": mk.sks}}


@app.get("/krs/{nim}")
def get_krs(nim: str, db: Session = Depends(get_db)):
    mhs = db.query(Mahasiswa).filter(Mahasiswa.nim == nim).first()
    if not mhs:
        raise HTTPException(status_code=404, detail=f"Mahasiswa {nim} tidak ditemukan")

    krs = (
        db.query(KRS)
        .filter(KRS.nim == nim, KRS.semester == mhs.semester_aktif)
        .first()
    )
    if not krs:
        return {
            "nim": nim,
            "semester": mhs.semester_aktif,
            "status": "DRAFT",
            "total_sks": 0,
            "courses": [],
        }

    courses = [
        {
            "kode_mk": d.kode_mk,
            "nama_mk": d.matakuliah.nama_mk if d.matakuliah else None,
            "sks": d.matakuliah.sks if d.matakuliah else 0,
            "hari": d.matakuliah.hari if d.matakuliah else None,
            "jam": f"{d.matakuliah.jam_mulai}-{d.matakuliah.jam_selesai}" if d.matakuliah else None,
        }
        for d in krs.details
    ]
    total_sks = sum(c["sks"] for c in courses)
    return {
        "nim": nim,
        "semester": krs.semester,
        "status": krs.status,
        "total_sks": total_sks,
        "courses": courses,
    }


@app.post("/krs/courses")
def add_course_endpoint(payload: CourseActionRequest, db: Session = Depends(get_db)):
    service = KRSService(db)
    res = service.add_course(payload.nim, payload.kode_mk)
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message)
    return {"success": True, "message": res.message, "data": res.data}


@app.delete("/krs/courses")
def remove_course_endpoint(payload: CourseActionRequest, db: Session = Depends(get_db)):
    service = KRSService(db)
    res = service.remove_course(payload.nim, payload.kode_mk)
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message)
    return {"success": True, "message": res.message, "data": res.data}


@app.post("/krs/{nim}/validate")
def validate_krs_endpoint(nim: str, db: Session = Depends(get_db)):
    service = KRSService(db)
    res = service.validate_krs(nim)
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message)
    return {"success": True, "message": res.message, "data": res.data}


@app.post("/krs/{nim}/submit")
def submit_krs_endpoint(nim: str, db: Session = Depends(get_db)):
    service = KRSService(db)
    res = service.submit_krs(nim)
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message)
    return {"success": True, "message": res.message, "data": res.data}


@app.post("/krs/approve")
def approve_krs_endpoint(payload: ApproveKRSRequest, db: Session = Depends(get_db)):
    service = KRSService(db)
    res = service.approve_krs(
        nim=payload.nim,
        dosen_pa_id=payload.dosen_pa_id,
        approved=payload.approved,
        catatan=payload.catatan,
    )
    if not res.success:
        raise HTTPException(status_code=400, detail=res.message)
    return {"success": True, "message": res.message, "data": res.data}