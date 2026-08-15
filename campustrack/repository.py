"""
campustrack.repository

Persistence layer. StudentRepository defines the contract every storage
backend must satisfy; WellnessSystem (system.py) only ever talks to
that abstract interface, never to a concrete class. That's what lets
InMemoryStudentRepository (fast, used in tests) and CsvStudentRepository
(real CSV files, used by the actual app) be swapped in with a single
line change and nothing else in the codebase needs to know or care.

CSV layout (four normalized files, one row per record - flat CSV can't
represent a student's nested exercise/sleep/survey lists directly, so
each record type gets its own file linked back by student_id):

    students.csv          student_id, name, age, course, faculty
    exercise_records.csv  student_id, days_per_week, exercise_type,
                           duration, day, time_of_day
    sleep_records.csv     student_id, had_good_sleep, start, end
    surveys.csv           student_id, entry_date, stress_level,
                           mood_rating, wellbeing_answers, notes

wellbeing_answers is stored as a semicolon-joined string (e.g. "4;4;3;5;4")
since a raw Python list doesn't round-trip through a CSV cell cleanly.
"""

import os
from abc import ABC, abstractmethod

import pandas as pd

from campustrack.exceptions import (
    DataFileError,
    DuplicateStudentError,
    ValidationError,
)
from campustrack.models import Student, ExerciseRecord, SleepPattern, Survey


class StudentRepository(ABC):
    """Contract every storage backend must implement."""

    @abstractmethod
    def add(self, student):
        raise NotImplementedError

    @abstractmethod
    def get(self, student_id):
        raise NotImplementedError

    @abstractmethod
    def exists(self, student_id):
        raise NotImplementedError

    @abstractmethod
    def all(self):
        raise NotImplementedError

    @abstractmethod
    def count(self):
        raise NotImplementedError

    @abstractmethod
    def persist(self):
        """Write the current in-memory state to durable storage. A no-op
        for repositories that have nothing to flush (e.g. in-memory)."""
        raise NotImplementedError


class InMemoryStudentRepository(StudentRepository):
    """No file I/O at all - used by the unit tests so they run fast and
    don't touch disk, and as a safe default if the app is started
    without a data directory configured."""

    def __init__(self):
        self._students = {}

    def add(self, student):
        if self.exists(student.student_id):
            raise DuplicateStudentError(student.student_id)
        self._students[student.student_id] = student

    def get(self, student_id):
        return self._students.get(student_id.strip().upper())

    def exists(self, student_id):
        return student_id.strip().upper() in self._students

    def all(self):
        return list(self._students.values())

    def count(self):
        return len(self._students)

    def persist(self):
        pass  # nothing to flush - everything already lives in memory


class CsvStudentRepository(StudentRepository):
    """Real persistence: reads all four CSVs on startup and rebuilds full
    Student objects (including their record history), and rewrites all
    four files on every persist() call. Writes are atomic - each file is
    written to a temp path first, then swapped into place with os.replace,
    so a crash mid-write can't leave a half-written CSV on disk."""

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.students_path = os.path.join(data_dir, "students.csv")
        self.exercise_path = os.path.join(data_dir, "exercise_records.csv")
        self.sleep_path = os.path.join(data_dir, "sleep_records.csv")
        self.surveys_path = os.path.join(data_dir, "surveys.csv")
        self._students = {}
        self._load()

    # loading
    def _read_csv_safe(self, path, columns):
        """Read a CSV, or return an empty frame with the right columns
        if the file doesn't exist yet (first run) or is unreadable."""
        if not os.path.exists(path):
            return pd.DataFrame(columns=columns)
        try:
            df = pd.read_csv(path, dtype=str).fillna("")
            missing = [c for c in columns if c not in df.columns]
            if missing:
                raise DataFileError(
                    f"{os.path.basename(path)} is missing expected column(s): {missing}"
                )
            return df
        except pd.errors.EmptyDataError:
            return pd.DataFrame(columns=columns)
        except pd.errors.ParserError as exc:
            raise DataFileError(f"Could not parse {os.path.basename(path)}: {exc}") from exc
        except OSError as exc:
            raise DataFileError(f"Could not read {os.path.basename(path)}: {exc}") from exc

    def _load(self):
        os.makedirs(self.data_dir, exist_ok=True)

        students_df = self._read_csv_safe(
            self.students_path, ["student_id", "name", "age", "course", "faculty"]
        )
        exercise_df = self._read_csv_safe(
            self.exercise_path,
            ["student_id", "days_per_week", "exercise_type", "duration", "day", "time_of_day"],
        )
        sleep_df = self._read_csv_safe(
            self.sleep_path, ["student_id", "had_good_sleep", "start", "end"]
        )
        surveys_df = self._read_csv_safe(
            self.surveys_path,
            ["student_id", "entry_date", "stress_level", "mood_rating",
             "wellbeing_answers", "notes"],
        )

        self._students = {}
        for _, row in students_df.iterrows():
            try:
                student = Student(
                    row["student_id"], row["name"], int(row["age"]), row["course"], row["faculty"]
                )
            except (ValueError, KeyError) as exc:
                raise DataFileError(f"Malformed row in students.csv: {exc}") from exc
            self._students[student.student_id] = student

        for _, row in exercise_df.iterrows():
            student = self._students.get(row["student_id"])

            if student is None:
                raise DataFileError(
                    f"exercise_records.csv contains record for unknown student "
                    f"'{row['student_id']}'."
                )

            try:
                record = ExerciseRecord(
                    int(row["days_per_week"]),
                    row["exercise_type"],
                    int(row["duration"]),
                    row["day"],
                    row["time_of_day"],
                )

                student.add_exercise_record(record)

            except (ValueError, KeyError, ValidationError) as exc:
                raise DataFileError(
                    f"Malformed row in exercise_records.csv: {exc}"
                ) from exc

        for _, row in sleep_df.iterrows():
            student = self._students.get(row["student_id"])

            if student is None:
                raise DataFileError(
                    f"sleep_records.csv contains record for unknown student "
                    f"'{row['student_id']}'."
                )

            try:
                had_good_sleep = (
                    str(row["had_good_sleep"]).strip().lower()
                    in ("true", "1", "yes")
                )

                record = SleepPattern(
                    had_good_sleep,
                    row["start"],
                    row["end"],
                )

                student.add_sleep_record(record)

            except (ValueError, KeyError, ValidationError) as exc:
                raise DataFileError(
                    f"Malformed row in sleep_records.csv: {exc}"
                ) from exc

        for _, row in surveys_df.iterrows():
            student = self._students.get(row["student_id"])

            if student is None:
                raise DataFileError(
                    f"surveys.csv contains record for unknown student "
                    f"'{row['student_id']}'."
                )

            try:
                answers_raw = str(row["wellbeing_answers"])
                answers = [
                    int(a)
                    for a in answers_raw.split(";")
                    if a.strip()
                ]

                survey = Survey(
                    row["entry_date"],
                    int(row["stress_level"]),
                    int(row["mood_rating"]),
                    answers,
                    row.get("notes", ""),
                )

                student.add_survey(survey)

            except (ValueError, KeyError, ValidationError) as exc:
                raise DataFileError(
                    f"Malformed row in surveys.csv: {exc}"
                ) from exc

        # First run - none of the four files exist yet. Create them now
        # (empty, headers only) rather than waiting for the first add(),
        # so the data directory is in a known, inspectable state as soon
        # as the app starts.
        if not any(os.path.exists(p) for p in
                   (self.students_path, self.exercise_path, self.sleep_path, self.surveys_path)):
            self.persist()

    # saving
    def _atomic_write(self, df, path):
        tmp_path = path + ".tmp"

        try:
            df.to_csv(tmp_path, index=False)
            os.replace(tmp_path, path)  # atomic on POSIX and Windows

        except OSError as exc:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

            raise DataFileError(
                f"Could not save {os.path.basename(path)}: {exc}"
            ) from exc

    def persist(self):
        os.makedirs(self.data_dir, exist_ok=True)

        student_rows, exercise_rows, sleep_rows, survey_rows = [], [], [], []
        for student in self._students.values():
            student_rows.append(student.to_dict())
            for r in student.exercise_records:
                exercise_rows.append({"student_id": student.student_id, **r.to_dict()})
            for r in student.sleep_records:
                sleep_rows.append({"student_id": student.student_id, **r.to_dict()})
            for s in student.surveys:
                d = s.to_dict()
                d["wellbeing_answers"] = ";".join(str(a) for a in d["wellbeing_answers"])
                survey_rows.append({"student_id": student.student_id, **d})

        self._atomic_write(
            pd.DataFrame(student_rows, columns=["student_id", "name", "age", "course", "faculty"]),
            self.students_path,
        )
        self._atomic_write(
            pd.DataFrame(exercise_rows, columns=[
                "student_id", "days_per_week", "exercise_type", "duration", "day", "time_of_day"
            ]),
            self.exercise_path,
        )
        self._atomic_write(
            pd.DataFrame(sleep_rows, columns=["student_id", "had_good_sleep", "start", "end"]),
            self.sleep_path,
        )
        self._atomic_write(
            pd.DataFrame(survey_rows, columns=[
                "student_id", "entry_date", "stress_level", "mood_rating",
                "wellbeing_answers", "notes"
            ]),
            self.surveys_path,
        )

    # StudentRepository interface
    def add(self, student):
        if self.exists(student.student_id):
            raise DuplicateStudentError(student.student_id)
        self._students[student.student_id] = student
        self.persist()

    def get(self, student_id):
        return self._students.get(student_id.strip().upper())

    def exists(self, student_id):
        return student_id.strip().upper() in self._students

    def all(self):
        return list(self._students.values())

    def count(self):
        return len(self._students)
