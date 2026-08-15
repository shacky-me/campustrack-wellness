"""
CampusTrack - Business Logic & Reports
MIS501 Assessment 3
Assigned section: Urbashi Barua

This module sits between the console/UI layer and the repository layer.
It contains application/business rules, update operations, filtering,
and report generation. Direct CSV/JSON handling belongs in repository.py.
"""

from __future__ import annotations

from typing import Any, Iterable

from .exceptions import RecordNotFoundError, StudentNotFoundError


class WellnessSystem:
    """Application service for CampusTrack business logic and reports."""

    VALID_RECORD_TYPES = ("exercise", "sleep", "survey")

    def __init__(self, repository, max_students: int = 20):
        self.repository = repository
        self.max_students = max_students

    # ------------------------------------------------------------------
    # Student business logic
    # ------------------------------------------------------------------
    def is_full(self) -> bool:
        """Return True when the configured student limit has been reached."""
        return self.repository.count() >= self.max_students

    def student_exists(self, student_id: str) -> bool:
        return self.repository.exists(self._normalise_student_id(student_id))

    def get_student(self, student_id: str):
        """Return one student or raise StudentNotFoundError."""
        student_id = self._normalise_student_id(student_id)
        student = self.repository.get(student_id)
        if student is None:
            raise StudentNotFoundError(
                f"Student '{student_id}' was not found."
            )
        return student

    def all_students(self):
        """Return all students managed by the repository."""
        return self.repository.all()

    def add_student(self, student):
        """
        Add a student after enforcing system-level rules.

        Model-level field validation is expected to be handled by Student.
        """
        if self.is_full():
            raise ValueError(
                f"CampusTrack can hold a maximum of {self.max_students} students."
            )

        student_id = self._normalise_student_id(student.student_id)

        if self.repository.exists(student_id):
            raise ValueError(
                f"Student ID '{student_id}' already exists."
            )

        self.repository.add(student)
        return student

    def update_student(
        self,
        student_id: str,
        *,
        name: str | None = None,
        age: int | None = None,
        course: str | None = None,
    ):
        """Update selected student details and persist the changed object."""
        student = self.get_student(student_id)

        if name is not None:
            student.name = name
        if age is not None:
            student.age = age
        if course is not None:
            student.course = course

        self._persist_update(student)
        return student

    # ------------------------------------------------------------------
    # Add record operations
    # ------------------------------------------------------------------
    def add_exercise_record(self, student_id: str, record):
        student = self.get_student(student_id)
        self._ensure_record_id(
            record,
            prefix="EX",
            records=student.exercise_records,
        )
        student.add_exercise_record(record)
        self._persist_update(student)
        return record

    def add_sleep_record(self, student_id: str, record):
        student = self.get_student(student_id)
        self._ensure_record_id(
            record,
            prefix="SL",
            records=student.sleep_records,
        )
        student.add_sleep_record(record)
        self._persist_update(student)
        return record

    def add_survey(self, student_id: str, survey):
        student = self.get_student(student_id)
        self._ensure_record_id(
            survey,
            prefix="SV",
            records=student.surveys,
        )
        student.add_survey(survey)
        self._persist_update(student)
        return survey

    # ------------------------------------------------------------------
    # Update-by-record-ID operations
    # ------------------------------------------------------------------
    def update_exercise_record(
        self,
        student_id: str,
        record_id: str,
        **changes,
    ):
        """Update an exercise record identified by record_id."""
        student = self.get_student(student_id)
        record = self._find_record(
            student.exercise_records,
            record_id,
            "exercise",
        )

        allowed = {
            "days_per_week",
            "exercise_type",
            "duration",
            "day",
            "time_of_day",
        }
        self._apply_allowed_changes(record, changes, allowed)
        self._persist_update(student)
        return record

    def update_sleep_record(
        self,
        student_id: str,
        record_id: str,
        **changes,
    ):
        """Update a sleep record and recalculate sleep duration if required."""
        student = self.get_student(student_id)
        record = self._find_record(
            student.sleep_records,
            record_id,
            "sleep",
        )

        allowed = {"had_good_sleep", "start", "end"}
        self._apply_allowed_changes(record, changes, allowed)

        # If the model stores calculated sleep hours, keep it consistent.
        if ("start" in changes or "end" in changes) and hasattr(
            record, "_calculate_hours"
        ):
            new_hours = record._calculate_hours(record.start, record.end)

            if hasattr(record, "_hours_slept"):
                record._hours_slept = new_hours
            elif hasattr(record, "hours_slept"):
                try:
                    record.hours_slept = new_hours
                except (AttributeError, TypeError):
                    pass

        self._persist_update(student)
        return record

    def update_survey(
        self,
        student_id: str,
        record_id: str,
        **changes,
    ):
        """Update a wellness survey identified by record_id."""
        student = self.get_student(student_id)
        survey = self._find_record(
            student.surveys,
            record_id,
            "survey",
        )

        allowed = {
            "entry_date",
            "stress_level",
            "mood_rating",
            "wellbeing_answers",
            "notes",
        }
        self._apply_allowed_changes(survey, changes, allowed)
        self._persist_update(student)
        return survey

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------
    def exercise_count_report(self) -> dict[str, int]:
        """Number of exercise records for every registered student."""
        return {
            student.student_id: len(student.exercise_records)
            for student in self.all_students()
        }

    def average_sleep_report(self) -> dict[str, float]:
        """Average nightly sleep for every registered student."""
        return {
            student.student_id: student.average_sleep_hours()
            for student in self.all_students()
        }

    def survey_summary_report(self) -> dict[str, dict[str, float | int]]:
        """Survey count and average wellness measures per student."""
        return {
            student.student_id: {
                "survey_count": len(student.surveys),
                "average_stress": student.average_stress_level(),
                "average_mood": student.average_mood_rating(),
                "average_wellbeing": student.average_wellbeing_percentage(),
            }
            for student in self.all_students()
        }

    def students_needing_intervention(self):
        """Return students whose combined wellness data requires attention."""
        return [
            student
            for student in self.all_students()
            if student.needs_intervention()
        ]

    def sessions_by_day_report(self, day: str):
        """Return all exercise sessions scheduled on a selected weekday."""
        day = str(day).strip().lower()

        if not day:
            raise ValueError("Day cannot be empty.")

        return [
            (student, record)
            for student in self.all_students()
            for record in student.exercise_records
            if str(record.day).strip().lower() == day
        ]

    def all_concerns_report(self):
        """
        Return all exercise, sleep and survey records currently flagged.

        This uses polymorphism: each WellnessRecord subtype provides
        is_concern(), summary_line() and to_dict().
        """
        concerns = []

        for student in self.all_students():
            for record in student.all_records():
                if record.is_concern():
                    record_type = self._safe_record_type(record)
                    concerns.append(
                        {
                            "student_id": student.student_id,
                            "student_name": student.name,
                            "record_id": getattr(record, "record_id", ""),
                            "record_type": record_type,
                            "summary": record.summary_line(),
                        }
                    )

        return concerns

    def student_wellness_summary(self, student_id: str) -> dict[str, Any]:
        """Generate a dashboard-style summary for one student."""
        student = self.get_student(student_id)

        return {
            "student_id": student.student_id,
            "name": student.name,
            "course": student.course,
            "exercise_records": len(student.exercise_records),
            "total_exercise_minutes": student.total_exercise_minutes(),
            "sleep_records": len(student.sleep_records),
            "average_sleep_hours": student.average_sleep_hours(),
            "survey_count": len(student.surveys),
            "average_stress": student.average_stress_level(),
            "average_mood": student.average_mood_rating(),
            "average_wellbeing": student.average_wellbeing_percentage(),
            "needs_intervention": student.needs_intervention(),
        }

    def overall_summary_report(self) -> dict[str, Any]:
        """
        Generate a whole-system text-dashboard summary.

        This is suitable for the Assessment 3 presentation logic requirement.
        """
        students = self.all_students()

        exercise_records = sum(
            len(student.exercise_records)
            for student in students
        )
        sleep_records = sum(
            len(student.sleep_records)
            for student in students
        )
        surveys = sum(
            len(student.surveys)
            for student in students
        )

        sleep_values = [
            student.average_sleep_hours()
            for student in students
            if student.sleep_records
        ]

        average_sleep = (
            round(sum(sleep_values) / len(sleep_values), 2)
            if sleep_values
            else 0.0
        )

        intervention_students = self.students_needing_intervention()

        return {
            "total_students": len(students),
            "total_exercise_records": exercise_records,
            "total_sleep_records": sleep_records,
            "total_surveys": surveys,
            "overall_average_sleep": average_sleep,
            "students_needing_intervention": len(intervention_students),
        }

    def filter_students(
        self,
        *,
        course: str | None = None,
        needs_intervention: bool | None = None,
    ):
        """
        Dynamically filter students by course and/or intervention status.

        This supports Assessment 3 scalability and dynamic filtering.
        """
        students = self.all_students()

        if course is not None:
            course_key = str(course).strip().lower()
            students = [
                student
                for student in students
                if str(student.course).strip().lower() == course_key
            ]

        if needs_intervention is not None:
            students = [
                student
                for student in students
                if student.needs_intervention() is needs_intervention
            ]

        return students

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _normalise_student_id(student_id: str) -> str:
        student_id = str(student_id).strip().upper()
        if not student_id:
            raise ValueError("Student ID cannot be empty.")
        return student_id

    def _persist_update(self, student) -> None:
        """
        Persist an existing student without doing file I/O in this layer.

        Required repository contract for Assessment 3:
        repository.update(student)

        A small compatibility fallback is included for earlier in-memory
        repositories where add(student) replaces the dictionary entry.
        """
        if hasattr(self.repository, "update"):
            self.repository.update(student)
            return

        # Compatibility with the Assessment 2 in-memory repository.
        if hasattr(self.repository, "add"):
            self.repository.add(student)
            return

        raise AttributeError(
            "Repository must implement update(student) or add(student)."
        )

    @staticmethod
    def _apply_allowed_changes(record, changes, allowed_fields) -> None:
        unknown = set(changes) - set(allowed_fields)

        if unknown:
            unknown_list = ", ".join(sorted(unknown))
            raise ValueError(
                f"Unsupported field(s): {unknown_list}"
            )

        if not changes:
            raise ValueError("At least one field must be supplied for update.")

        for field_name, value in changes.items():
            setattr(record, field_name, value)

    @staticmethod
    def _find_record(records: Iterable, record_id: str, label: str):
        record_id = str(record_id).strip().upper()

        for record in records:
            current_id = str(
                getattr(record, "record_id", "")
            ).strip().upper()

            if current_id == record_id:
                return record

        raise RecordNotFoundError(
            f"{label.capitalize()} record '{record_id}' was not found."
        )

    @staticmethod
    def _ensure_record_id(record, prefix: str, records: Iterable) -> str:
        """
        Ensure every record has a stable ID for Assessment 3 update operations.

        If Roshan's final model already supplies record_id, it is preserved.
        Otherwise a simple prefix-based ID is generated.
        """
        existing_ids = {
            str(getattr(item, "record_id", "")).strip().upper()
            for item in records
            if getattr(item, "record_id", None)
        }

        current_id = str(
            getattr(record, "record_id", "")
        ).strip().upper()

        if current_id:
            if current_id in existing_ids:
                raise ValueError(
                    f"Record ID '{current_id}' already exists."
                )
            return current_id

        next_number = 1
        while f"{prefix}{next_number:03d}" in existing_ids:
            next_number += 1

        generated_id = f"{prefix}{next_number:03d}"
        setattr(record, "record_id", generated_id)
        return generated_id

    @staticmethod
    def _safe_record_type(record) -> str:
        try:
            data = record.to_dict()
            if isinstance(data, dict) and data.get("type"):
                return str(data["type"])
        except (AttributeError, TypeError, ValueError):
            pass

        return record.__class__.__name__.lower()
