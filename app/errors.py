from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApplicationError(Exception):
    status_code: int
    code: str
    message: str
