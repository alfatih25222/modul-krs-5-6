from dataclasses import dataclass
from typing import Optional
from sqlalchemy.orm import Session

from app.models import KRS, KRSDetail, Mahasiswa, MataKuliah
from app.state_machine import KRSStateMachine, KRSStatus
from app.validators import BaseValidator, build_validation_chain


@dataclass
class ServiceResult:
    success: bool
    message: str
    data: Optional[dict] = None


class KRSService:
    def __init__(self, db: Session, validator_chain: Optional[BaseValidator] = None):
        self.db = db
        self.validator_chain = validator_chain or build_validation_chain()

    def _get_or_create_krs(self, nim: str) -> tuple[Optional[KRS], Optional[str]]:
        mahasiswa = self.db.query(Mahasiswa).filter(Mahasiswa.nim == nim).first()
        if not mahasiswa:
            return None, f"Mahasiswa dengan NIM {nim} tidak ditemukan"

        krs = (
            self.db.query(KRS)
            .filter(KRS.nim == nim, KRS.semester == mahasiswa.semester_aktif)
            .first()
        )
        if not krs:
            krs = KRS(
                nim=nim,
                semester=mahasiswa.semester_aktif,
                status=KRSStatus.DRAFT.value,
            )
            self.db.add(krs)
            self.db.flush()

        return krs, None

    def add_course(self, nim: str, kode_mk: str) -> ServiceResult:
        try:
            krs, err = self._get_or_create_krs(nim)
            if err or krs is None:
                return ServiceResult(False, err or "Gagal memuat KRS")

            if krs.status not in {KRSStatus.DRAFT.value, KRSStatus.REVISION.value}:
                return ServiceResult(
                    False,
                    f"Tidak bisa menambah mata kuliah saat status KRS {krs.status}",
                )

            mk = self.db.query(MataKuliah).filter(MataKuliah.kode_mk == kode_mk).first()
            if not mk:
                return ServiceResult(False, f"Mata kuliah {kode_mk} tidak ditemukan")

            validation = self.validator_chain.validate(self.db, krs, mk)
            if not validation.passed:
                return ServiceResult(False, validation.message)

            detail = KRSDetail(krs_id=krs.id, kode_mk=mk.kode_mk)
            self.db.add(detail)
            self.db.commit()
            self.db.refresh(krs)

            total_sks = sum(d.matakuliah.sks for d in krs.details if d.matakuliah)
            return ServiceResult(
                True,
                f"Mata kuliah {mk.kode_mk} ({mk.nama_mk}) berhasil ditambahkan ke KRS",
                data={"nim": nim, "kode_mk": mk.kode_mk, "total_sks": total_sks},
            )
        except Exception as exc:
            self.db.rollback()
            return ServiceResult(False, f"Terjadi kesalahan saat menambah MK: {exc}")

    def remove_course(self, nim: str, kode_mk: str) -> ServiceResult:
        try:
            krs, err = self._get_or_create_krs(nim)
            if err or krs is None:
                return ServiceResult(False, err or "Gagal memuat KRS")

            if krs.status not in {KRSStatus.DRAFT.value, KRSStatus.REVISION.value}:
                return ServiceResult(
                    False,
                    f"Tidak bisa menghapus mata kuliah saat status KRS {krs.status}",
                )

            detail = (
                self.db.query(KRSDetail)
                .filter(KRSDetail.krs_id == krs.id, KRSDetail.kode_mk == kode_mk)
                .first()
            )
            if not detail:
                return ServiceResult(
                    False,
                    f"Mata kuliah {kode_mk} tidak ada di dalam KRS mahasiswa {nim}",
                )

            self.db.delete(detail)
            self.db.commit()
            self.db.refresh(krs)

            total_sks = sum(d.matakuliah.sks for d in krs.details if d.matakuliah)
            return ServiceResult(
                True,
                f"Mata kuliah {kode_mk} berhasil dihapus dari KRS",
                data={"nim": nim, "kode_mk": kode_mk, "total_sks": total_sks},
            )
        except Exception as exc:
            self.db.rollback()
            return ServiceResult(False, f"Terjadi kesalahan saat menghapus MK: {exc}")

    def validate_krs(self, nim: str) -> ServiceResult:
        krs, err = self._get_or_create_krs(nim)
        if err or krs is None:
            return ServiceResult(False, err or "Gagal memuat KRS")

        mahasiswa = self.db.query(Mahasiswa).filter(Mahasiswa.nim == nim).first()
        max_sks = min(mahasiswa.max_sks if mahasiswa and mahasiswa.max_sks else 24, 24)
        total_sks = sum(d.matakuliah.sks for d in krs.details if d.matakuliah)

        if total_sks > max_sks:
            return ServiceResult(
                False,
                f"Total SKS ({total_sks}) melebihi batas maksimal ({max_sks} SKS)",
            )

        # Cek ulang setiap MK yang sudah masuk di KRS terhadap MK lainnya
        seen_codes: set[str] = set()
        for detail in krs.details:
            mk = detail.matakuliah
            if not mk:
                continue

            if mk.kode_mk in seen_codes:
                return ServiceResult(False, f"Duplikasi mata kuliah {mk.kode_mk}")
            seen_codes.add(mk.kode_mk)

            # Cek prasyarat
            from app.validators import PrerequisiteValidator, ConflictValidator
            prereq_res = PrerequisiteValidator()._check(self.db, krs, mk)
            if not prereq_res.passed:
                return ServiceResult(False, prereq_res.message)

            # Cek bentrok jadwal dengan MK lain dalam KRS
            for other in krs.details:
                if other.kode_mk == mk.kode_mk or not other.matakuliah:
                    continue
                if ConflictValidator()._check(self.db, krs, mk).passed is False and (
                    other.matakuliah.hari.strip().lower() == mk.hari.strip().lower()
                ):
                    s1 = ConflictValidator._to_minutes(mk.jam_mulai)
                    e1 = ConflictValidator._to_minutes(mk.jam_selesai)
                    s2 = ConflictValidator._to_minutes(other.matakuliah.jam_mulai)
                    e2 = ConflictValidator._to_minutes(other.matakuliah.jam_selesai)
                    if s1 < e2 and s2 < e1:
                        return ServiceResult(
                            False,
                            f"Jadwal bentrok antara {mk.kode_mk} dan {other.kode_mk}",
                        )

        return ServiceResult(
            True,
            "KRS valid dan siap diajukan",
            data={"nim": nim, "total_sks": total_sks, "jumlah_mk": len(krs.details)},
        )

    def submit_krs(self, nim: str) -> ServiceResult:
        try:
            krs, err = self._get_or_create_krs(nim)
            if err or krs is None:
                return ServiceResult(False, err or "Gagal memuat KRS")

            if not krs.details:
                return ServiceResult(False, "KRS kosong, tambahkan minimal 1 mata kuliah sebelum submit")

            validation = self.validate_krs(nim)
            if not validation.success:
                return ServiceResult(False, f"Gagal submit KRS: {validation.message}")

            next_status = KRSStateMachine.transition(krs.status, KRSStatus.SUBMITTED)
            krs.status = next_status.value
            self.db.commit()
            self.db.refresh(krs)

            return ServiceResult(
                True,
                f"KRS berhasil di-submit (status sekarang: {krs.status})",
                data={"nim": nim, "status": krs.status},
            )
        except Exception as exc:
            self.db.rollback()
            return ServiceResult(False, str(exc))

    def approve_krs(
        self,
        nim: str,
        dosen_pa_id: str,
        approved: bool = True,
        catatan: Optional[str] = None,
    ) -> ServiceResult:
        try:
            krs, err = self._get_or_create_krs(nim)
            if err or krs is None:
                return ServiceResult(False, err or "Gagal memuat KRS")

            target = KRSStatus.APPROVED if approved else KRSStatus.REVISION
            next_status = KRSStateMachine.transition(krs.status, target)
            krs.status = next_status.value
            krs.catatan_dosen = catatan

            if approved:
                krs.approved_by = dosen_pa_id

            self.db.commit()
            self.db.refresh(krs)

            return ServiceResult(
                True,
                f"KRS diproses oleh dosen PA {dosen_pa_id} (status sekarang: {krs.status})",
                data={
                    "nim": nim,
                    "status": krs.status,
                    "approved_by": krs.approved_by,
                    "catatan_dosen": krs.catatan_dosen,
                },
            )
        except Exception as exc:
            self.db.rollback()
            return ServiceResult(False, str(exc))