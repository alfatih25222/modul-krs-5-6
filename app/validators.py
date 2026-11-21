from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from sqlalchemy.orm import Session

from app.models import KRS, MataKuliah, Mahasiswa, NilaiSemesterLalu, Prerequisite

GRADE_WEIGHT: dict[str, float] = {
    "A": 4.0,
    "AB": 3.5,
    "B": 3.0,
    "BC": 2.5,
    "C": 2.0,
    "D": 1.0,
    "E": 0.0,
}


@dataclass
class ValidationResult:
    passed: bool
    message: str = "OK"
    validator_name: str = ""


class BaseValidator(ABC):
    def __init__(self, next_validator: Optional["BaseValidator"] = None):
        self._next = next_validator

    def set_next(self, validator: "BaseValidator") -> "BaseValidator":
        self._next = validator
        return validator

    def validate(self, db: Session, krs: KRS, candidate_mk: MataKuliah) -> ValidationResult:
        result = self._check(db, krs, candidate_mk)
        if not result.passed:
            return result
        if self._next is not None:
            return self._next.validate(db, krs, candidate_mk)
        return ValidationResult(passed=True, message="Semua validasi lolos", validator_name="Chain")

    @abstractmethod
    def _check(self, db: Session, krs: KRS, candidate_mk: MataKuliah) -> ValidationResult:
        pass


class DuplicateValidator(BaseValidator):
    """Cek double enrollment pada KRS yang sama."""

    def _check(self, db: Session, krs: KRS, candidate_mk: MataKuliah) -> ValidationResult:
        existing_codes = {detail.kode_mk for detail in krs.details}
        if candidate_mk.kode_mk in existing_codes:
            return ValidationResult(
                passed=False,
                message=f"Mata kuliah {candidate_mk.kode_mk} ({candidate_mk.nama_mk}) sudah terdaftar di KRS",
                validator_name="DuplicateValidator",
            )
        return ValidationResult(passed=True, validator_name="DuplicateValidator")


class SKSValidator(BaseValidator):
    """Cek total SKS tidak melebihi batas maksimal (default 24 SKS)."""

    def _check(self, db: Session, krs: KRS, candidate_mk: MataKuliah) -> ValidationResult:
        mahasiswa: Optional[Mahasiswa] = db.query(Mahasiswa).filter(Mahasiswa.nim == krs.nim).first()
        max_sks = mahasiswa.max_sks if mahasiswa and mahasiswa.max_sks else 24
        max_sks = min(max_sks, 24)

        current_sks = sum(detail.matakuliah.sks for detail in krs.details if detail.matakuliah)
        total_after_add = current_sks + candidate_mk.sks

        if total_after_add > max_sks:
            return ValidationResult(
                passed=False,
                message=(
                    f"Batas SKS terlampaui: total menjadi {total_after_add} SKS "
                    f"(maksimal {max_sks} SKS)"
                ),
                validator_name="SKSValidator",
            )
        return ValidationResult(passed=True, validator_name="SKSValidator")


class PrerequisiteValidator(BaseValidator):
    """Cek mata kuliah prasyarat lulus minimal nilai C di semester sebelumnya."""

    def _check(self, db: Session, krs: KRS, candidate_mk: MataKuliah) -> ValidationResult:
        prereqs = (
            db.query(Prerequisite)
            .filter(Prerequisite.kode_mk == candidate_mk.kode_mk)
            .all()
        )
        if not prereqs:
            return ValidationResult(passed=True, validator_name="PrerequisiteValidator")

        nilai_rows = (
            db.query(NilaiSemesterLalu)
            .filter(NilaiSemesterLalu.nim == krs.nim)
            .all()
        )
        nilai_map = {row.kode_mk: row.nilai_huruf.upper() for row in nilai_rows}

        missing_prereqs: list[str] = []
        for p in prereqs:
            min_grade = (p.min_nilai_huruf or "C").upper()
            min_weight = GRADE_WEIGHT.get(min_grade, GRADE_WEIGHT["C"])
            mhs_grade = nilai_map.get(p.kode_mk_syarat)

            if not mhs_grade:
                syarat_mk = db.query(MataKuliah).filter(MataKuliah.kode_mk == p.kode_mk_syarat).first()
                label = syarat_mk.nama_mk if syarat_mk else p.kode_mk_syarat
                missing_prereqs.append(label)
                continue

            mhs_weight = GRADE_WEIGHT.get(mhs_grade, 0.0)
            if mhs_weight < min_weight:
                syarat_mk = db.query(MataKuliah).filter(MataKuliah.kode_mk == p.kode_mk_syarat).first()
                label = syarat_mk.nama_mk if syarat_mk else p.kode_mk_syarat
                missing_prereqs.append(f"{label} (nilai {mhs_grade}, min {min_grade})")

        if missing_prereqs:
            return ValidationResult(
                passed=False,
                message=f"Prasyarat tidak terpenuhi: {', '.join(missing_prereqs)}",
                validator_name="PrerequisiteValidator",
            )

        return ValidationResult(passed=True, validator_name="PrerequisiteValidator")


class ConflictValidator(BaseValidator):
    """Cek bentrok jadwal (hari sama dan rentang jam beririsan)."""

    @staticmethod
    def _to_minutes(jam_str: str) -> int:
        parts = jam_str.strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])

    def _is_overlap(self, start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
        return start_a < end_b and start_b < end_a

    def _check(self, db: Session, krs: KRS, candidate_mk: MataKuliah) -> ValidationResult:
        cand_start = self._to_minutes(candidate_mk.jam_mulai)
        cand_end = self._to_minutes(candidate_mk.jam_selesai)

        for detail in krs.details:
            existing_mk = detail.matakuliah
            if not existing_mk:
                continue
            if existing_mk.hari.strip().lower() == candidate_mk.hari.strip().lower():
                ex_start = self._to_minutes(existing_mk.jam_mulai)
                ex_end = self._to_minutes(existing_mk.jam_selesai)
                if self._is_overlap(cand_start, cand_end, ex_start, ex_end):
                    return ValidationResult(
                        passed=False,
                        message=(
                            f"Jadwal bentrok dengan {existing_mk.kode_mk} ({existing_mk.nama_mk}) "
                            f"pada hari {existing_mk.hari} {existing_mk.jam_mulai}-{existing_mk.jam_selesai}"
                        ),
                        validator_name="ConflictValidator",
                    )

        return ValidationResult(passed=True, validator_name="ConflictValidator")


def build_validation_chain() -> BaseValidator:
    """Merangkai urutan chain of responsibility."""
    dup = DuplicateValidator()
    sks = SKSValidator()
    prereq = PrerequisiteValidator()
    conflict = ConflictValidator()

    dup.set_next(sks).set_next(prereq).set_next(conflict)
    return dup