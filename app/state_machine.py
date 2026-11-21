from enum import Enum


class KRSStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    REVISION = "REVISION"
    APPROVED = "APPROVED"


class InvalidStateTransitionError(Exception):
    """Dilempar ketika transisi status KRS melanggar aturan state machine."""


ALLOWED_TRANSITIONS: dict[KRSStatus, set[KRSStatus]] = {
    KRSStatus.DRAFT: {KRSStatus.SUBMITTED},
    KRSStatus.SUBMITTED: {KRSStatus.APPROVED, KRSStatus.REVISION},
    KRSStatus.REVISION: {KRSStatus.SUBMITTED},
    KRSStatus.APPROVED: set(),
}


class KRSStateMachine:
    """Enforce aturan transisi status KRS."""

    @staticmethod
    def can_transition(current_status: str | KRSStatus, target_status: str | KRSStatus) -> bool:
        curr = KRSStatus(current_status)
        nxt = KRSStatus(target_status)
        return nxt in ALLOWED_TRANSITIONS.get(curr, set())

    @staticmethod
    def transition(current_status: str | KRSStatus, target_status: str | KRSStatus) -> KRSStatus:
        curr = KRSStatus(current_status)
        nxt = KRSStatus(target_status)
        if not KRSStateMachine.can_transition(curr, nxt):
            raise InvalidStateTransitionError(
                f"Transisi status tidak diperbolehkan: {curr.value} -> {nxt.value}"
            )
        return nxt