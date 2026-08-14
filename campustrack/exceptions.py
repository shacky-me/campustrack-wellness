"""
campustrack.exceptions
A small custom exception hierarchy so every layer (repository, system,
cli) can raise/catch something more specific than a bare Exception.
Everything inherits from CampusTrackError, so the CLI can catch that
one type at the top level as a last-resort safety net while still
handling the specific ones with tailored messages.

"""


class CampusTrackError(Exception):
    """Base class for every error raised by this application."""


class StudentNotFoundError(CampusTrackError):
    """Raised when a student ID doesn't exist in the repository."""

    def __init__(self, student_id):
        self.student_id = student_id
        super().__init__(f"No student found with ID '{student_id}'.")


class DuplicateStudentError(CampusTrackError):
    """Raised when trying to add a student ID that already exists."""

    def __init__(self, student_id):
        self.student_id = student_id
        super().__init__(f"Student ID '{student_id}' already exists.")


class RecordNotFoundError(CampusTrackError):
    """Raised when looking up a specific wellness record that doesn't exist."""

    def __init__(self, message="The requested record could not be found."):
        super().__init__(message)


class ValidationError(CampusTrackError):
    """Raised by model setters when a value fails validation.

    Kept separate from Python's built-in ValueError so callers can
    choose to catch validation problems specifically without also
    swallowing unrelated ValueErrors from elsewhere (e.g. int() parsing).
    """


class DataFileError(CampusTrackError):
    """Raised when a data file can't be read or written - missing,
    corrupted, or a permissions problem. The repository layer catches
    the underlying OSError/pandas error and re-raises this instead, so
    the CLI only ever needs to know about one persistence-error type."""
