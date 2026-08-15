"""
CampusTrack - Fitness & Wellness Monitoring System
Single-file edition (console-based, no GUI)

Everything - custom exceptions, domain models, the CSV repository,
business logic/reports, pandas/matplotlib analytics, and the console
menu - lives in this one file so it's easy to read top-to-bottom or
submit as a single script. Unit tests live separately in
test_campustrack.py.

Sections in this file (search for the "# ==" banners):
  1. Exceptions
  2. Domain models        (Person/Student, WellnessRecord hierarchy)
  3. Repository            (StudentRepository ABC, InMemory, single-CSV)
  4. WellnessSystem        (orchestration + reports)
  5. Analytics             (pandas summaries + matplotlib charts)
  6. Console CLI           (menus, input validation, main())

Run with:  python campustrack_app.py
Data is stored in a single CSV file, campustrack_data.csv, saved in the
same folder as this script (created automatically on first run).
"""

import os
from abc import ABC, abstractmethod
from datetime import datetime
from functools import wraps
from uuid import uuid4

import matplotlib
matplotlib.use("Agg")  # no GUI - this is a console-only app; charts save to PNG
import matplotlib.pyplot as plt
import pandas as pd


# =====================================================================
# 1. EXCEPTIONS
# =====================================================================

class CampusTrackError(Exception):
    """Base class for every CampusTrack-specific error."""


class StudentNotFoundError(CampusTrackError):
    def __init__(self, student_id):
        super().__init__(f"No student found with ID '{student_id}'.")
        self.student_id = student_id


class DuplicateStudentError(CampusTrackError):
    def __init__(self, student_id):
        super().__init__(f"Student ID '{student_id}' already exists.")
        self.student_id = student_id


class RecordNotFoundError(CampusTrackError):
    def __init__(self, record_id, record_type="record"):
        super().__init__(f"No {record_type} found with ID '{record_id}'.")
        self.record_id = record_id


class DataFileError(CampusTrackError):
    """Wraps file-system / pandas parsing failures into one error type."""

    def __init__(self, path, action, original_exception=None):
        message = f"Could not {action} data file: {path}"
        if original_exception is not None:
            message += f" ({original_exception.__class__.__name__}: {original_exception})"
        super().__init__(message)
        self.path = path
        self.original_exception = original_exception


# =====================================================================
# 2. DOMAIN MODELS
# =====================================================================

SLEEP_BENCHMARK = 8          # benchmark hours of sleep per night
MAX_STUDENTS = 20            # maximum students the system can hold
SHORT_SESSION_MINUTES = 10   # exercise sessions shorter than this are flagged


def new_record_id():
    """Short, unique, CSV-friendly identifier for a single record."""
    return uuid4().hex[:8]


class WellnessRecord(ABC):
    """Abstract base for anything that can be logged against a student."""

    def __init__(self, record_id=None):
        self.record_id = record_id or new_record_id()

    @abstractmethod
    def is_concern(self):
        raise NotImplementedError

    @abstractmethod
    def summary_line(self):
        raise NotImplementedError

    @abstractmethod
    def to_dict(self):
        raise NotImplementedError

    def __str__(self):
        return self.summary_line()


class ExerciseRecord(WellnessRecord):

    def __init__(self, days_per_week, exercise_type, duration, day, time_of_day, record_id=None):
        super().__init__(record_id)
        self.days_per_week = days_per_week
        self.exercise_type = exercise_type
        self.duration = duration
        self.day = day
        self.time_of_day = time_of_day

    @property
    def days_per_week(self):
        return self._days_per_week

    @days_per_week.setter
    def days_per_week(self, value):
        value = int(value)
        if not (1 <= value <= 7):
            raise ValueError("days_per_week must be an integer between 1 and 7.")
        self._days_per_week = value

    @property
    def exercise_type(self):
        return self._exercise_type

    @exercise_type.setter
    def exercise_type(self, value):
        if not str(value).strip():
            raise ValueError("exercise_type cannot be empty.")
        self._exercise_type = str(value).strip().lower()

    @property
    def duration(self):
        return self._duration

    @duration.setter
    def duration(self, value):
        value = int(value)
        if not (1 <= value <= 1440):
            raise ValueError("duration must be an integer between 1 and 1440 minutes.")
        self._duration = value

    @property
    def day(self):
        return self._day

    @day.setter
    def day(self, value):
        if not str(value).strip():
            raise ValueError("day cannot be empty.")
        self._day = str(value).strip().lower()

    @property
    def time_of_day(self):
        return self._time_of_day

    @time_of_day.setter
    def time_of_day(self, value):
        self._time_of_day = value

    def is_concern(self):
        return self.duration < SHORT_SESSION_MINUTES

    def summary_line(self):
        return (f"{self.exercise_type.capitalize():<12} | {self.duration:>4} min | "
                f"{self.day.capitalize():<9} @ {self.time_of_day} | "
                f"{self.days_per_week}x/week")

    def to_dict(self):
        return {
            "record_id": self.record_id,
            "type": "exercise",
            "days_per_week": self.days_per_week,
            "exercise_type": self.exercise_type,
            "duration": self.duration,
            "day": self.day,
            "time_of_day": self.time_of_day,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            days_per_week=int(data["days_per_week"]),
            exercise_type=data["exercise_type"],
            duration=int(data["duration"]),
            day=data["day"],
            time_of_day=data["time_of_day"],
            record_id=data.get("record_id"),
        )


class SleepPattern(WellnessRecord):

    def __init__(self, had_good_sleep, start, end, record_id=None):
        super().__init__(record_id)
        self._had_good_sleep = bool(had_good_sleep)
        self.start = start
        self.end = end
        self._hours_slept = self._calculate_hours(self._start, self._end)

    @staticmethod
    def _calculate_hours(start, end):
        sh, sm = (int(part) for part in start.split(":"))
        eh, em = (int(part) for part in end.split(":"))
        start_h = sh + sm / 60.0
        end_h = eh + em / 60.0
        hours = (24 - start_h) + end_h if end_h < start_h else end_h - start_h
        return round(hours, 2)

    @property
    def had_good_sleep(self):
        return self._had_good_sleep

    @had_good_sleep.setter
    def had_good_sleep(self, value):
        self._had_good_sleep = bool(value)

    @property
    def start(self):
        return self._start

    @start.setter
    def start(self, value):
        self._start = value
        if hasattr(self, "_end"):
            self._hours_slept = self._calculate_hours(self._start, self._end)

    @property
    def end(self):
        return self._end

    @end.setter
    def end(self, value):
        self._end = value
        if hasattr(self, "_start"):
            self._hours_slept = self._calculate_hours(self._start, self._end)

    @property
    def hours_slept(self):
        return self._hours_slept

    @property
    def deficit(self):
        return round(SLEEP_BENCHMARK - self.hours_slept, 2)

    @property
    def status(self):
        return "Meets benchmark" if self.deficit <= 0 else "Deficit"

    def is_concern(self):
        return self.deficit > 0

    def summary_line(self):
        nap_label = "Yes" if self.had_good_sleep else "No"
        return (f"{self.start}-{self.end} | {self.hours_slept:>5} hrs | "
                f"Good sleep: {nap_label:<3} | {self.status}")

    def to_dict(self):
        return {
            "record_id": self.record_id,
            "type": "sleep",
            "had_good_sleep": self.had_good_sleep,
            "start": self.start,
            "end": self.end,
            "hours_slept": self.hours_slept,
        }

    @classmethod
    def from_dict(cls, data):
        had_good_sleep = data["had_good_sleep"]
        if isinstance(had_good_sleep, str):
            had_good_sleep = had_good_sleep.strip().lower() in ("true", "yes", "1")
        return cls(
            had_good_sleep=had_good_sleep,
            start=data["start"],
            end=data["end"],
            record_id=data.get("record_id"),
        )


class Survey(WellnessRecord):

    def __init__(self, entry_date, stress_level, mood_rating, wellbeing_answers, notes="", record_id=None):
        super().__init__(record_id)
        self.entry_date = entry_date
        self.stress_level = stress_level
        self.mood_rating = mood_rating
        self.wellbeing_answers = wellbeing_answers
        self.notes = notes

    @property
    def entry_date(self):
        return self._entry_date

    @entry_date.setter
    def entry_date(self, value):
        self._entry_date = value

    @property
    def stress_level(self):
        return self._stress_level

    @stress_level.setter
    def stress_level(self, value):
        value = int(value)
        if not (1 <= value <= 10):
            raise ValueError("stress_level must be an integer between 1 and 10.")
        self._stress_level = value

    @property
    def mood_rating(self):
        return self._mood_rating

    @mood_rating.setter
    def mood_rating(self, value):
        value = int(value)
        if not (1 <= value <= 10):
            raise ValueError("mood_rating must be an integer between 1 and 10.")
        self._mood_rating = value

    @property
    def wellbeing_answers(self):
        return list(self._wellbeing_answers)

    @wellbeing_answers.setter
    def wellbeing_answers(self, value):
        value = [int(v) for v in value]
        if len(value) != 5 or any(not (0 <= v <= 5) for v in value):
            raise ValueError("wellbeing_answers must be exactly 5 values, each 0-5.")
        self._wellbeing_answers = value

    @property
    def notes(self):
        return self._notes

    @notes.setter
    def notes(self, value):
        self._notes = value or ""

    def wellbeing_raw_score(self):
        """WHO-5 raw score: five responses, each scored from 0 to 5."""
        return sum(self.wellbeing_answers)

    def wellbeing_percentage(self):
        """WHO-5 percentage score, raw score multiplied by four."""
        return self.wellbeing_raw_score() * 4

    def wellbeing_status(self):
        percentage = self.wellbeing_percentage()
        if percentage < 28:
            return "Low wellbeing - needs attention"
        if percentage < 50:
            return "Below recommended wellbeing range"
        return "Healthy wellbeing range"

    def needs_attention(self):
        return (
            self.stress_level >= 7
            or self.mood_rating <= 4
            or self.wellbeing_percentage() < 50
        )

    def is_concern(self):
        return self.needs_attention()

    def summary_line(self):
        status = "Needs attention" if self.needs_attention() else "Healthy range"
        notes = self.notes if self.notes else "No notes"
        return (f"{self.entry_date} | Stress: {self.stress_level}/10 | "
                f"Mood: {self.mood_rating}/10 | "
                f"WHO-5: {self.wellbeing_raw_score()}/25 "
                f"({self.wellbeing_percentage()}%) | {status} | Notes: {notes}")

    def to_dict(self):
        return {
            "record_id": self.record_id,
            "type": "survey",
            "entry_date": self.entry_date,
            "stress_level": self.stress_level,
            "mood_rating": self.mood_rating,
            "wellbeing_answers": "|".join(str(v) for v in self.wellbeing_answers),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data):
        answers = data["wellbeing_answers"]
        if isinstance(answers, str):
            answers = [int(v) for v in answers.split("|")]
        return cls(
            entry_date=data["entry_date"],
            stress_level=int(data["stress_level"]),
            mood_rating=int(data["mood_rating"]),
            wellbeing_answers=answers,
            notes=data.get("notes", "") or "",
            record_id=data.get("record_id"),
        )


class Person(ABC):
    """Abstract base for anyone tracked in the system."""

    def __init__(self, person_id, name, age):
        self.person_id = person_id
        self.name = name
        self.age = age

    @property
    def person_id(self):
        return self._person_id

    @person_id.setter
    def person_id(self, value):
        if not str(value).strip():
            raise ValueError("ID cannot be empty.")
        self._person_id = str(value).strip().upper()

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if not str(value).strip():
            raise ValueError("Name cannot be empty.")
        self._name = str(value).strip()

    @property
    def age(self):
        return self._age

    @age.setter
    def age(self, value):
        value = int(value)
        if not (1 <= value <= 120):
            raise ValueError("Age must be an integer between 1 and 120.")
        self._age = value

    @abstractmethod
    def role_label(self):
        raise NotImplementedError

    def __str__(self):
        return f"{self.person_id:<8} | {self.name:<20} | Age {self.age:<3} | {self.role_label()}"


class Student(Person):

    def __init__(self, student_id, name, age, course):
        super().__init__(student_id, name, age)
        self.course = course
        self._exercise_records = []
        self._sleep_records = []
        self._surveys = []

    @property
    def student_id(self):
        return self.person_id

    @property
    def course(self):
        return self._course

    @course.setter
    def course(self, value):
        if not str(value).strip():
            raise ValueError("Course cannot be empty.")
        self._course = str(value).strip()

    def role_label(self):
        return f"Student ({self.course})"

    @property
    def exercise_records(self):
        return list(self._exercise_records)

    @property
    def sleep_records(self):
        return list(self._sleep_records)

    @property
    def surveys(self):
        return list(self._surveys)

    def add_exercise_record(self, record):
        if not isinstance(record, ExerciseRecord):
            raise TypeError("Expected an ExerciseRecord instance.")
        self._exercise_records.append(record)

    def add_sleep_record(self, record):
        if not isinstance(record, SleepPattern):
            raise TypeError("Expected a SleepPattern instance.")
        self._sleep_records.append(record)

    def add_survey(self, survey):
        if not isinstance(survey, Survey):
            raise TypeError("Expected a Survey instance.")
        self._surveys.append(survey)

    def find_exercise_record(self, record_id):
        return next((r for r in self._exercise_records if r.record_id == record_id), None)

    def find_sleep_record(self, record_id):
        return next((r for r in self._sleep_records if r.record_id == record_id), None)

    def find_survey(self, record_id):
        return next((r for r in self._surveys if r.record_id == record_id), None)

    def remove_exercise_record(self, record_id):
        self._exercise_records = [r for r in self._exercise_records if r.record_id != record_id]

    def remove_sleep_record(self, record_id):
        self._sleep_records = [r for r in self._sleep_records if r.record_id != record_id]

    def remove_survey(self, record_id):
        self._surveys = [r for r in self._surveys if r.record_id != record_id]

    def all_records(self):
        return self._exercise_records + self._sleep_records + self._surveys

    def average_stress_level(self):
        if not self._surveys:
            return 0.0
        return round(sum(s.stress_level for s in self._surveys) / len(self._surveys), 2)

    def average_mood_rating(self):
        if not self._surveys:
            return 0.0
        return round(sum(s.mood_rating for s in self._surveys) / len(self._surveys), 2)

    def average_wellbeing_percentage(self):
        if not self._surveys:
            return 0.0
        return round(sum(s.wellbeing_percentage() for s in self._surveys) / len(self._surveys), 2)

    def total_exercise_minutes(self):
        return sum(r.duration for r in self._exercise_records)

    def average_sleep_hours(self):
        if not self._sleep_records:
            return 0.0
        return round(sum(r.hours_slept for r in self._sleep_records) / len(self._sleep_records), 2)

    def deficit_nights(self):
        for record in self._sleep_records:
            if record.deficit > 0:
                yield record

    def needs_intervention(self):
        low_sleep = bool(self._sleep_records) and self.average_sleep_hours() < (SLEEP_BENCHMARK - 1.5)
        survey_attention = any(survey.needs_attention() for survey in self._surveys)
        return low_sleep or survey_attention

    def as_row(self):
        return "  {:<8} {:<20} {:<5} {}".format(self.student_id, self.name, self.age, self.course)

    def to_dict(self):
        return {
            "student_id": self.student_id,
            "name": self.name,
            "age": self.age,
            "course": self.course,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            student_id=data["student_id"],
            name=data["name"],
            age=int(data["age"]),
            course=data["course"],
        )

    def __str__(self):
        return f"{self.student_id:<8} | {self.name:<20} | Age {self.age:<3} | {self.course}"


# =====================================================================
# 3. REPOSITORY  (single-CSV persistence, using pandas)
# =====================================================================

# One CSV holds every row type. `row_type` tells us which columns apply;
# columns that don't apply to a given row are left blank.
DATA_COLUMNS = [
    "row_type", "student_id", "record_id",
    "name", "age", "course",                                        # student rows
    "days_per_week", "exercise_type", "duration", "day", "time_of_day",  # exercise rows
    "had_good_sleep", "start", "end", "hours_slept",                 # sleep rows
    "entry_date", "stress_level", "mood_rating", "wellbeing_answers", "notes",  # survey rows
]


class StudentRepository(ABC):

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

    def persist_student(self, student):
        pass

    def persist_exercise(self, student):
        pass

    def persist_sleep(self, student):
        pass

    def persist_survey(self, student):
        pass


class InMemoryStudentRepository(StudentRepository):
    """Plain-memory repository. No file I/O - handy for tests."""

    def __init__(self):
        self._students = {}

    def add(self, student):
        self._students[student.student_id] = student

    def get(self, student_id):
        return self._students.get(student_id)

    def exists(self, student_id):
        return student_id in self._students

    def all(self):
        return list(self._students.values())

    def count(self):
        return len(self._students)


class CsvStudentRepository(StudentRepository):
    """
    Single-CSV-file-backed repository, using pandas for reading/writing.

    Every mutating call rewrites the one data file in full - the
    simplest way to guarantee the file on disk never drifts out of
    sync with the objects in memory.
    """

    def __init__(self, data_path):
        self.data_path = data_path
        self._students = {}
        self._ensure_parent_dir()
        self.load()

    def _ensure_parent_dir(self):
        parent = os.path.dirname(self.data_path)
        if not parent:
            return
        try:
            os.makedirs(parent, exist_ok=True)
        except OSError as exc:
            raise DataFileError(parent, "create data directory", exc) from exc

    def _read_csv(self):
        if not os.path.exists(self.data_path):
            return pd.DataFrame(columns=DATA_COLUMNS)
        try:
            df = pd.read_csv(self.data_path, dtype=str)
        except pd.errors.EmptyDataError:
            return pd.DataFrame(columns=DATA_COLUMNS)
        except (pd.errors.ParserError, OSError, PermissionError) as exc:
            raise DataFileError(self.data_path, "read", exc) from exc
        for col in DATA_COLUMNS:
            if col not in df.columns:
                df[col] = pd.NA
        return df

    def load(self):
        """(Re)build the in-memory student dict from the single CSV file."""
        self._students = {}
        df = self._read_csv()

        # Pass 1: students, so records in pass 2 always have somewhere to attach.
        for _, row in df[df["row_type"] == "student"].iterrows():
            student = Student.from_dict(row.to_dict())
            self._students[student.student_id] = student

        # Pass 2: records, attached to their student by student_id.
        for _, row in df[df["row_type"] != "student"].iterrows():
            student = self._students.get(str(row["student_id"]).strip().upper())
            if student is None:
                continue  # orphaned row - student was removed/renamed
            row_type = row["row_type"]
            data = row.to_dict()
            if row_type == "exercise":
                student.add_exercise_record(ExerciseRecord.from_dict(data))
            elif row_type == "sleep":
                student.add_sleep_record(SleepPattern.from_dict(data))
            elif row_type == "survey":
                student.add_survey(Survey.from_dict(data))

    def _save(self):
        """Rewrite the whole data file from the current in-memory state."""
        rows = []
        for student in self._students.values():
            student_row = {col: "" for col in DATA_COLUMNS}
            student_row.update(student.to_dict())
            student_row["row_type"] = "student"
            rows.append(student_row)

            for record in student.exercise_records:
                row = {col: "" for col in DATA_COLUMNS}
                row.update(record.to_dict())
                row["row_type"] = "exercise"
                row["student_id"] = student.student_id
                rows.append(row)

            for record in student.sleep_records:
                row = {col: "" for col in DATA_COLUMNS}
                row.update(record.to_dict())
                row["row_type"] = "sleep"
                row["student_id"] = student.student_id
                rows.append(row)

            for survey in student.surveys:
                row = {col: "" for col in DATA_COLUMNS}
                row.update(survey.to_dict())
                row["row_type"] = "survey"
                row["student_id"] = student.student_id
                rows.append(row)

        try:
            df = pd.DataFrame(rows, columns=DATA_COLUMNS)
            df.to_csv(self.data_path, index=False)
        except (OSError, PermissionError) as exc:
            raise DataFileError(self.data_path, "write", exc) from exc

    # -- StudentRepository interface --------------------------------------
    def add(self, student):
        self._students[student.student_id] = student
        self._save()

    def get(self, student_id):
        return self._students.get(student_id)

    def exists(self, student_id):
        return student_id in self._students

    def all(self):
        return list(self._students.values())

    def count(self):
        return len(self._students)

    def persist_student(self, student):
        self._save()

    def persist_exercise(self, student):
        self._save()

    def persist_sleep(self, student):
        self._save()

    def persist_survey(self, student):
        self._save()


# =====================================================================
# 4. WELLNESS SYSTEM  (orchestration + reports)
# =====================================================================

class WellnessSystem:

    def __init__(self, repository=None, max_students=MAX_STUDENTS):
        self.repository = repository or InMemoryStudentRepository()
        self.max_students = max_students

    def is_full(self):
        return self.repository.count() >= self.max_students

    def exists(self, student_id):
        return self.repository.exists(student_id)

    def add_student(self, student):
        self.repository.add(student)

    def get_student(self, student_id):
        return self.repository.get(student_id)

    def require_student(self, student_id):
        student = self.repository.get(student_id)
        if student is None:
            raise StudentNotFoundError(student_id)
        return student

    def all_students(self):
        return self.repository.all()

    def update_student(self, student_id, name=None, age=None, course=None):
        student = self.require_student(student_id)
        if name is not None:
            student.name = name
        if age is not None:
            student.age = age
        if course is not None:
            student.course = course
        self.repository.persist_student(student)
        return student

    def update_exercise_record(self, student_id, record_id, **fields):
        student = self.require_student(student_id)
        record = student.find_exercise_record(record_id)
        if record is None:
            raise RecordNotFoundError(record_id, "exercise record")
        for field, value in fields.items():
            if value is not None:
                setattr(record, field, value)
        self.repository.persist_exercise(student)
        return record

    def update_sleep_record(self, student_id, record_id, **fields):
        student = self.require_student(student_id)
        record = student.find_sleep_record(record_id)
        if record is None:
            raise RecordNotFoundError(record_id, "sleep record")
        for field, value in fields.items():
            if value is not None:
                setattr(record, field, value)
        self.repository.persist_sleep(student)
        return record

    def update_survey(self, student_id, record_id, **fields):
        student = self.require_student(student_id)
        record = student.find_survey(record_id)
        if record is None:
            raise RecordNotFoundError(record_id, "survey")
        for field, value in fields.items():
            if value is not None:
                setattr(record, field, value)
        self.repository.persist_survey(student)
        return record

    def add_exercise_record(self, student_id, record):
        student = self.require_student(student_id)
        student.add_exercise_record(record)
        self.repository.persist_exercise(student)
        return record

    def add_sleep_record(self, student_id, record):
        student = self.require_student(student_id)
        student.add_sleep_record(record)
        self.repository.persist_sleep(student)
        return record

    def add_survey(self, student_id, survey):
        student = self.require_student(student_id)
        student.add_survey(survey)
        self.repository.persist_survey(student)
        return survey

    # -- Reports ------------------------------------------------------------
    def exercise_count_report(self):
        return {s.student_id: len(s.exercise_records) for s in self.all_students()}

    def average_sleep_report(self):
        return {s.student_id: s.average_sleep_hours() for s in self.all_students()}

    def survey_summary_report(self):
        return {
            s.student_id: {
                "survey_count": len(s.surveys),
                "average_stress": s.average_stress_level(),
                "average_mood": s.average_mood_rating(),
                "average_wellbeing": s.average_wellbeing_percentage(),
            }
            for s in self.all_students()
        }

    def students_needing_intervention(self):
        return [s for s in self.all_students() if s.needs_intervention()]

    def exercise_sessions_on_day(self, day_filter):
        day_filter = day_filter.lower()
        return [
            (student, record)
            for student in self.all_students()
            for record in student.exercise_records
            if record.day.lower() == day_filter
        ]

    def all_concerns_report(self):
        return [
            (student, record)
            for student in self.all_students()
            for record in student.all_records()
            if record.is_concern()
        ]


# =====================================================================
# 5. ANALYTICS  (pandas summaries + matplotlib charts)
# =====================================================================

CHART_DPI = 150


class WellnessAnalytics:
    """Builds pandas DataFrames from a WellnessSystem and renders charts."""

    def __init__(self, system, charts_dir):
        self.system = system
        self.charts_dir = charts_dir
        os.makedirs(self.charts_dir, exist_ok=True)

    def students_dataframe(self):
        rows = [s.to_dict() for s in self.system.all_students()]
        return pd.DataFrame(rows, columns=["student_id", "name", "age", "course"])

    def exercise_dataframe(self):
        rows = []
        for student in self.system.all_students():
            for record in student.exercise_records:
                row = record.to_dict()
                row["student_id"] = student.student_id
                row["student_name"] = student.name
                rows.append(row)
        return pd.DataFrame(rows)

    def sleep_dataframe(self):
        rows = []
        for student in self.system.all_students():
            for record in student.sleep_records:
                row = record.to_dict()
                row["student_id"] = student.student_id
                row["student_name"] = student.name
                rows.append(row)
        return pd.DataFrame(rows)

    def survey_dataframe(self):
        rows = []
        for student in self.system.all_students():
            for record in student.surveys:
                row = record.to_dict()
                row["student_id"] = student.student_id
                row["student_name"] = student.name
                rows.append(row)
        return pd.DataFrame(rows)

    def print_exercise_summary(self):
        df = self.exercise_dataframe()
        if df.empty:
            print("  No exercise data yet.")
            return
        by_student = df.groupby("student_name")["duration"].agg(["count", "sum", "mean"])
        by_student.columns = ["sessions", "total_minutes", "avg_minutes"]
        by_student["avg_minutes"] = by_student["avg_minutes"].round(1)
        print(by_student.to_string())

    def print_sleep_summary(self):
        df = self.sleep_dataframe()
        if df.empty:
            print("  No sleep data yet.")
            return
        df["hours_slept"] = df["hours_slept"].astype(float)
        by_student = df.groupby("student_name")["hours_slept"].agg(["count", "mean", "min", "max"])
        by_student.columns = ["nights", "avg_hours", "min_hours", "max_hours"]
        by_student = by_student.round(2)
        print(by_student.to_string())

    def print_survey_summary(self):
        df = self.survey_dataframe()
        if df.empty:
            print("  No survey data yet.")
            return
        df["stress_level"] = df["stress_level"].astype(float)
        df["mood_rating"] = df["mood_rating"].astype(float)
        by_student = df.groupby("student_name")[["stress_level", "mood_rating"]].mean().round(2)
        print(by_student.to_string())

    def plot_exercise_minutes_by_student(self, filename="exercise_minutes_by_student.png"):
        df = self.exercise_dataframe()
        path = os.path.join(self.charts_dir, filename)
        fig, ax = plt.subplots(figsize=(8, 5))
        if df.empty:
            ax.text(0.5, 0.5, "No exercise data yet", ha="center", va="center")
        else:
            totals = df.groupby("student_name")["duration"].sum().sort_values(ascending=False)
            totals.plot(kind="bar", ax=ax, color="#3B82F6")
            ax.set_ylabel("Total exercise minutes")
            ax.set_xlabel("Student")
            ax.set_title("Total Exercise Minutes per Student")
            plt.xticks(rotation=30, ha="right")
        fig.tight_layout()
        fig.savefig(path, dpi=CHART_DPI)
        plt.close(fig)
        return path

    def plot_average_sleep_by_student(self, filename="average_sleep_by_student.png"):
        df = self.sleep_dataframe()
        path = os.path.join(self.charts_dir, filename)
        fig, ax = plt.subplots(figsize=(8, 5))
        if df.empty:
            ax.text(0.5, 0.5, "No sleep data yet", ha="center", va="center")
        else:
            df["hours_slept"] = df["hours_slept"].astype(float)
            avg = df.groupby("student_name")["hours_slept"].mean().sort_values()
            colors = ["#EF4444" if v < 8 else "#22C55E" for v in avg]
            avg.plot(kind="barh", ax=ax, color=colors)
            ax.axvline(8, color="black", linestyle="--", linewidth=1, label="8 hr benchmark")
            ax.set_xlabel("Average hours slept")
            ax.set_title("Average Sleep per Student")
            ax.legend()
        fig.tight_layout()
        fig.savefig(path, dpi=CHART_DPI)
        plt.close(fig)
        return path

    def plot_stress_mood_trend(self, filename="stress_mood_trend.png"):
        df = self.survey_dataframe()
        path = os.path.join(self.charts_dir, filename)
        fig, ax = plt.subplots(figsize=(8, 5))
        if df.empty:
            ax.text(0.5, 0.5, "No survey data yet", ha="center", va="center")
        else:
            df["entry_date"] = pd.to_datetime(df["entry_date"])
            df = df.sort_values("entry_date")
            for student_name, group in df.groupby("student_name"):
                ax.plot(group["entry_date"], group["stress_level"], marker="o", label=f"{student_name} (stress)")
                ax.plot(group["entry_date"], group["mood_rating"], marker="s", linestyle="--",
                        label=f"{student_name} (mood)")
            ax.set_ylabel("Rating (1-10)")
            ax.set_xlabel("Survey date")
            ax.set_title("Stress & Mood Trend Over Time")
            ax.legend(fontsize="small")
            fig.autofmt_xdate()
        fig.tight_layout()
        fig.savefig(path, dpi=CHART_DPI)
        plt.close(fig)
        return path

    def build_dashboard(self, filename="dashboard.png"):
        """One combined 2x2 dashboard image summarising the whole system."""
        path = os.path.join(self.charts_dir, filename)
        exercise_df = self.exercise_dataframe()
        sleep_df = self.sleep_dataframe()
        survey_df = self.survey_dataframe()

        fig, axes = plt.subplots(2, 2, figsize=(12, 9))
        fig.suptitle("CampusTrack Wellness Dashboard", fontsize=16, fontweight="bold")

        ax = axes[0, 0]
        if exercise_df.empty:
            ax.text(0.5, 0.5, "No exercise data", ha="center", va="center")
        else:
            totals = exercise_df.groupby("student_name")["duration"].sum().sort_values(ascending=False)
            totals.plot(kind="bar", ax=ax, color="#3B82F6")
            plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        ax.set_title("Total Exercise Minutes")

        ax = axes[0, 1]
        if sleep_df.empty:
            ax.text(0.5, 0.5, "No sleep data", ha="center", va="center")
        else:
            sleep_df["hours_slept"] = sleep_df["hours_slept"].astype(float)
            avg = sleep_df.groupby("student_name")["hours_slept"].mean()
            colors = ["#EF4444" if v < 8 else "#22C55E" for v in avg]
            avg.plot(kind="bar", ax=ax, color=colors)
            ax.axhline(8, color="black", linestyle="--", linewidth=1)
            plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        ax.set_title("Average Sleep Hours (8 hr benchmark)")

        ax = axes[1, 0]
        if exercise_df.empty:
            ax.text(0.5, 0.5, "No exercise data", ha="center", va="center")
        else:
            counts = exercise_df["exercise_type"].value_counts()
            ax.pie(counts.values, labels=counts.index, autopct="%1.0f%%", startangle=90)
        ax.set_title("Exercise Type Breakdown")

        ax = axes[1, 1]
        if survey_df.empty:
            ax.text(0.5, 0.5, "No survey data", ha="center", va="center")
        else:
            survey_df["stress_level"] = survey_df["stress_level"].astype(float)
            survey_df["mood_rating"] = survey_df["mood_rating"].astype(float)
            grouped = survey_df.groupby("student_name")[["stress_level", "mood_rating"]].mean()
            grouped.plot(kind="bar", ax=ax, color=["#F97316", "#22C55E"])
            plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        ax.set_title("Average Stress vs Mood")

        fig.tight_layout(rect=[0, 0, 1, 0.96])
        fig.savefig(path, dpi=CHART_DPI)
        plt.close(fig)
        return path


# =====================================================================
# 6. CONSOLE CLI  (menus, input validation, main())
# =====================================================================

SEP = "-" * 55
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "campustrack_data.csv")
CHARTS_DIR = os.path.join(BASE_DIR, "charts")


def get_nonempty_string(prompt):
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("  ! This field cannot be empty.")


def get_optional_string(prompt):
    value = input(prompt).strip()
    return value if value else None


def get_int_in_range(prompt, low, high):
    while True:
        raw = input(prompt).strip()
        if not raw.lstrip("-").isdigit():
            print("  ! Must be a whole number.")
        elif not (low <= int(raw) <= high):
            print(f"  ! Must be between {low} and {high}.")
        else:
            return int(raw)


def get_optional_int_in_range(prompt, low, high):
    while True:
        raw = input(prompt).strip()
        if not raw:
            return None
        if not raw.lstrip("-").isdigit():
            print("  ! Must be a whole number, or blank to keep the current value.")
        elif not (low <= int(raw) <= high):
            print(f"  ! Must be between {low} and {high}.")
        else:
            return int(raw)


def get_yes_no(prompt):
    while True:
        raw = input(prompt).strip().lower()
        if raw in ("yes", "no"):
            return raw == "yes"
        print("  ! Please enter 'yes' or 'no'.")


def get_optional_yes_no(prompt):
    while True:
        raw = input(prompt).strip().lower()
        if not raw:
            return None
        if raw in ("yes", "no"):
            return raw == "yes"
        print("  ! Please enter 'yes', 'no', or blank to keep the current value.")


def get_time_hhmm(prompt):
    while True:
        raw = input(prompt).strip()
        parsed = _parse_hhmm(raw)
        if parsed is None:
            print("  ! Use HH:MM format (e.g. 07:30).")
            continue
        return parsed


def get_optional_time_hhmm(prompt):
    while True:
        raw = input(prompt).strip()
        if not raw:
            return None
        parsed = _parse_hhmm(raw)
        if parsed is None:
            print("  ! Use HH:MM format (e.g. 07:30), or blank to keep the current value.")
            continue
        return parsed


def _parse_hhmm(raw):
    if raw.count(":") != 1:
        return None
    hours, minutes = raw.split(":")
    if not (hours.isdigit() and minutes.isdigit()):
        return None
    hours, minutes = int(hours), int(minutes)
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        return None
    return f"{hours:02d}:{minutes:02d}"


def get_date_yyyy_mm_dd(prompt):
    while True:
        raw = input(prompt).strip()
        try:
            return datetime.strptime(raw, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            print("  ! Enter a valid date in YYYY-MM-DD format.")


def get_optional_date_yyyy_mm_dd(prompt):
    while True:
        raw = input(prompt).strip()
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            print("  ! Enter a valid date in YYYY-MM-DD format, or blank to keep the current value.")


def log_action(label):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            stamp = datetime.now().strftime("%H:%M:%S")
            print(f"  [log {stamp}] {label}")
            return result
        return wrapper
    return decorator


def safe_action(func):
    """
    Catch validation errors (ValueError from a model setter) and
    persistence errors (DataFileError / other CampusTrackError) so a
    bad input or a locked/missing CSV file never crashes the app.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DataFileError as exc:
            print(f"  ! Data file problem: {exc}")
        except CampusTrackError as exc:
            print(f"  ! {exc}")
        except ValueError as exc:
            print(f"  ! Invalid value: {exc}")
    return wrapper


def resolve_student(system):
    if not system.all_students():
        print("  No students registered yet.")
        return None
    student_id = get_nonempty_string("  Enter Student ID: ").upper()
    student = system.get_student(student_id)
    if student is None:
        print("  ! Student not found.")
    return student


# -- Add screens ---------------------------------------------------------
@safe_action
@log_action("Student added")
def handle_add_student(system):
    print("\n" + SEP)
    print("  ADD NEW STUDENT")
    print(SEP)

    if system.is_full():
        print(f"  System full. Max {system.max_students} students reached.")
        return

    while True:
        new_id = get_nonempty_string("  Enter Student ID   : ").upper()
        if system.exists(new_id):
            print("  ! ID already exists. Use a unique ID.")
        else:
            break

    new_name = get_nonempty_string("  Enter Full Name    : ")
    new_age = get_int_in_range("  Enter Age          : ", 1, 120)
    new_course = get_nonempty_string("  Enter Course Name  : ")

    system.add_student(Student(new_id, new_name, new_age, new_course))
    print(f"\n  Student {new_name} ({new_id}) added and saved to campustrack_data.csv.")


@safe_action
@log_action("Student updated")
def handle_update_student(system):
    student = resolve_student(system)
    if not student:
        return
    print("\n" + SEP)
    print(f"  UPDATE STUDENT - {student.name} ({student.student_id})")
    print("  Press ENTER to keep the current value.")
    print(SEP)

    name = get_optional_string(f"  Name [{student.name}]: ")
    age = get_optional_int_in_range(f"  Age [{student.age}]: ", 1, 120)
    course = get_optional_string(f"  Course [{student.course}]: ")

    system.update_student(student.student_id, name=name, age=age, course=course)
    print(f"\n  Student {student.student_id} updated and saved to campustrack_data.csv.")


@safe_action
@log_action("Exercise record added")
def handle_add_exercise(system, student):
    print("\n" + SEP)
    print(f"  ADD EXERCISE RECORD - {student.name}")
    print(SEP)

    days = get_int_in_range("  Days per week (1-7): ", 1, 7)
    ex_type = get_nonempty_string("  Exercise type      : ").lower()
    duration = get_int_in_range("  Duration (minutes) : ", 1, 1440)
    day = get_nonempty_string("  Day of week        : ").lower()
    time_of_day = get_time_hhmm("  Time of day (HH:MM): ")

    record = ExerciseRecord(days, ex_type, duration, day, time_of_day)
    system.add_exercise_record(student.student_id, record)
    print(f"\n  Exercise record [{record.record_id}] added and saved to campustrack_data.csv.")


@safe_action
@log_action("Exercise record updated")
def handle_update_exercise(system, student):
    if not student.exercise_records:
        print("  No exercise records found for this student.")
        return
    print("\n" + SEP)
    print(f"  UPDATE EXERCISE RECORD - {student.name}")
    print(SEP)
    for i, record in enumerate(student.exercise_records, start=1):
        print(f"  #{i} [{record.record_id}]  {record}")

    record_id = get_nonempty_string("\n  Enter record ID to update: ").strip()
    record = student.find_exercise_record(record_id)
    if record is None:
        print("  ! No exercise record with that ID.")
        return

    print("  Press ENTER to keep the current value.")
    days = get_optional_int_in_range(f"  Days per week [{record.days_per_week}]: ", 1, 7)
    ex_type = get_optional_string(f"  Exercise type [{record.exercise_type}]: ")
    duration = get_optional_int_in_range(f"  Duration mins [{record.duration}]: ", 1, 1440)
    day = get_optional_string(f"  Day of week [{record.day}]: ")
    time_of_day = get_optional_time_hhmm(f"  Time of day [{record.time_of_day}]: ")

    system.update_exercise_record(
        student.student_id, record_id,
        days_per_week=days, exercise_type=ex_type, duration=duration,
        day=day, time_of_day=time_of_day,
    )
    print(f"\n  Exercise record [{record_id}] updated and saved to campustrack_data.csv.")


@safe_action
@log_action("Sleep record added")
def handle_add_sleep(system, student):
    print("\n" + SEP)
    print(f"  ADD SLEEP PATTERN - {student.name}")
    print(SEP)

    had_good_sleep = get_yes_no("  Did you have a good sleep? (yes/no): ")
    start = get_time_hhmm("  Sleep start (HH:MM, 24hr): ")
    end = get_time_hhmm("  Wake-up time (HH:MM, 24hr): ")

    record = SleepPattern(had_good_sleep, start, end)
    system.add_sleep_record(student.student_id, record)

    print(f"\n  Sleep record [{record.record_id}] saved to campustrack_data.csv:", record.hours_slept, "hrs")
    if record.deficit > 0:
        print("  Sleep deficit:", record.deficit, f"hrs below {SLEEP_BENCHMARK} hr benchmark")
    else:
        print(f"  Great! Meets or exceeds the {SLEEP_BENCHMARK}-hr benchmark.")


@safe_action
@log_action("Sleep record updated")
def handle_update_sleep(system, student):
    if not student.sleep_records:
        print("  No sleep records found for this student.")
        return
    print("\n" + SEP)
    print(f"  UPDATE SLEEP PATTERN - {student.name}")
    print(SEP)
    for i, record in enumerate(student.sleep_records, start=1):
        print(f"  #{i} [{record.record_id}]  {record}")

    record_id = get_nonempty_string("\n  Enter record ID to update: ").strip()
    record = student.find_sleep_record(record_id)
    if record is None:
        print("  ! No sleep record with that ID.")
        return

    print("  Press ENTER to keep the current value.")
    had_good_sleep = get_optional_yes_no("  Good sleep? (yes/no) "
                                         f"[{'yes' if record.had_good_sleep else 'no'}]: ")
    start = get_optional_time_hhmm(f"  Sleep start [{record.start}]: ")
    end = get_optional_time_hhmm(f"  Wake-up time [{record.end}]: ")

    system.update_sleep_record(
        student.student_id, record_id,
        had_good_sleep=had_good_sleep, start=start, end=end,
    )
    print(f"\n  Sleep record [{record_id}] updated and saved to campustrack_data.csv "
          f"(now {record.hours_slept} hrs).")


@safe_action
@log_action("Wellness survey completed")
def handle_add_survey(system, student):
    print("\n" + SEP)
    print(f"  COMPLETE WELLNESS SURVEY - {student.name}")
    print(SEP)

    entry_date = get_date_yyyy_mm_dd("  Survey date (YYYY-MM-DD): ")
    stress_level = get_int_in_range("  Stress level (1-10)     : ", 1, 10)
    mood_rating = get_int_in_range("  Mood rating (1-10)      : ", 1, 10)

    print("""
          WHO-5 WELLBEING QUESTIONS
          During the last two weeks, how often have you experienced the following?
          0 = At no time
          1 = Some of the time
          2 = Less than half the time
          3 = More than half the time
          4 = Most of the time
          5 = All of the time
    """)

    wellbeing_questions = [
        "Felt cheerful and in good spirits",
        "Felt calm and relaxed",
        "Felt active and energetic",
        "Woke feeling fresh and rested",
        "Daily life included interesting things",
    ]
    wellbeing_answers = [
        get_int_in_range(f"  {i}. {q:<45} (0-5): ", 0, 5)
        for i, q in enumerate(wellbeing_questions, start=1)
    ]

    notes = input("  Notes (optional)        : ").strip()

    survey = Survey(entry_date, stress_level, mood_rating, wellbeing_answers, notes)
    system.add_survey(student.student_id, survey)

    print(f"""
          Survey [{survey.record_id}] saved to campustrack_data.csv.
          WHO-5 wellbeing score: {survey.wellbeing_raw_score()}/25 ({survey.wellbeing_percentage()}%)
          Wellbeing status: {survey.wellbeing_status()}
    """)
    if survey.needs_attention():
        print("  Survey result indicates that additional wellbeing support may be helpful.")
        print("  Consider healthy routines and speaking with a qualified support service if needed.")
    else:
        print("  Survey result is within a healthy range.")


@safe_action
@log_action("Wellness survey updated")
def handle_update_survey(system, student):
    if not student.surveys:
        print("  No wellness surveys found for this student.")
        return
    print("\n" + SEP)
    print(f"  UPDATE WELLNESS SURVEY - {student.name}")
    print(SEP)
    for i, survey in enumerate(student.surveys, start=1):
        print(f"  #{i} [{survey.record_id}]  {survey}")

    record_id = get_nonempty_string("\n  Enter survey ID to update: ").strip()
    survey = student.find_survey(record_id)
    if survey is None:
        print("  ! No survey with that ID.")
        return

    print("  Press ENTER to keep the current value.")
    entry_date = get_optional_date_yyyy_mm_dd(f"  Survey date [{survey.entry_date}]: ")
    stress_level = get_optional_int_in_range(f"  Stress level [{survey.stress_level}]: ", 1, 10)
    mood_rating = get_optional_int_in_range(f"  Mood rating [{survey.mood_rating}]: ", 1, 10)

    wellbeing_answers = None
    if get_yes_no("  Re-answer the 5 WHO-5 questions? (yes/no): "):
        wellbeing_answers = [
            get_int_in_range(f"    Q{i} (0-5): ", 0, 5) for i in range(1, 6)
        ]

    notes = get_optional_string(f"  Notes [{survey.notes or 'None'}]: ")

    system.update_survey(
        student.student_id, record_id,
        entry_date=entry_date, stress_level=stress_level, mood_rating=mood_rating,
        wellbeing_answers=wellbeing_answers, notes=notes,
    )
    print(f"\n  Survey [{record_id}] updated and saved to campustrack_data.csv.")


# -- Display screens -------------------------------------------------------
def handle_display_exercise(student):
    print("\n" + SEP)
    print(f"  EXERCISE INFORMATION - {student.name} ({student.student_id})")
    print(SEP)

    if not student.exercise_records:
        print("  No exercise records found for this student.")
        return

    for i, record in enumerate(student.exercise_records, start=1):
        print(f"  #{i} [{record.record_id}]  {record}")

    total = student.total_exercise_minutes()
    avg = total // len(student.exercise_records)
    print(SEP)
    print(f"  Records     : {len(student.exercise_records)}")
    print(f"  Total mins  : {total}")
    print(f"  Avg/session : {avg} min")


def handle_display_sleep(student):
    print("\n" + SEP)
    print(f"  WEEKLY SLEEP INFORMATION - {student.name} ({student.student_id})")
    print(SEP)

    if not student.sleep_records:
        print("  No sleep records found for this student.")
        return

    for i, record in enumerate(student.sleep_records, start=1):
        print(f"  Night #{i} [{record.record_id}]  {record}")

    total = sum(r.hours_slept for r in student.sleep_records)
    nights = len(student.sleep_records)
    avg = student.average_sleep_hours()
    weekly_benchmark = SLEEP_BENCHMARK * nights
    pct = round((total / weekly_benchmark) * 100, 1)

    print(SEP)
    print(f"""
          SLEEP SUMMARY

          Nights        : {nights}
          Total sleep   : {round(total, 2)} hrs
          Average/night : {avg} hrs
          Benchmark %   : {pct}%
    """)

    print("  Nights below benchmark:")
    deficit_found = False
    for record in student.deficit_nights():
        deficit_found = True
        print(f"    {record.start}-{record.end}  (deficit {record.deficit} hrs)")
    if not deficit_found:
        print("    None - every night met the benchmark.")


def handle_display_surveys(student):
    print("\n" + SEP)
    print(f"  WELLNESS SURVEY HISTORY - {student.name} ({student.student_id})")
    print(SEP)

    if not student.surveys:
        print("  No wellness surveys found for this student.")
        return

    for i, survey in enumerate(student.surveys, start=1):
        print(f"  Survey #{i} [{survey.record_id}]: {survey}")

    print(SEP)
    print(f"""
          STUDENT WELLNESS SUMMARY

          Surveys completed       : {len(student.surveys)}
          Average stress          : {student.average_stress_level()}/10
          Average mood            : {student.average_mood_rating()}/10
          Average WHO-5 wellbeing : {student.average_wellbeing_percentage()}%
    """)


def handle_display_all(system):
    print("\n" + SEP)
    print("  REGISTERED STUDENTS")
    print(SEP)

    if not system.all_students():
        print("  No students registered yet.")
        return

    print("  {:<8} {:<20} {:<5} {}".format("ID", "Name", "Age", "Course"))
    print("  " + "-" * 51)
    for student in system.all_students():
        print(student.as_row())


# -- Reports menu ------------------------------------------------------------
def handle_reports(system):
    viewing_reports = True
    while viewing_reports:
        print("\n" + SEP)
        print("  REPORTS MENU")
        print(SEP)
        print("""
              1. Exercise records per student
              2. Average sleep per student
              3. Students needing wellness intervention
              4. Exercise sessions on a given day (all students)
              5. Wellness survey summary per student
              6. All wellness concerns (exercise + sleep + survey)
              0. Back to main menu
        """)

        sub_choice = input("  Enter your choice: ").strip()

        if sub_choice == "1":
            print("\n  -- Exercise Records per Student --")
            for sid, count in system.exercise_count_report().items():
                print(f"    {system.get_student(sid).name} ({sid}): {count} record(s)")

        elif sub_choice == "2":
            print("\n  -- Average Sleep per Student --")
            for sid, avg in system.average_sleep_report().items():
                label = f"{avg} hrs" if avg else "No data"
                print(f"    {system.get_student(sid).name} ({sid}): {label}")

        elif sub_choice == "3":
            print("\n  -- Students Needing Wellness Intervention --")
            flagged = system.students_needing_intervention()
            if not flagged:
                print("    None. All students are within a healthy sleep range.")
            for student in flagged:
                sleep_label = (f"{student.average_sleep_hours()} hrs"
                               if student.sleep_records else "No sleep data")
                survey_label = (f"stress {student.average_stress_level()}/10, "
                                f"mood {student.average_mood_rating()}/10, "
                                f"WHO-5 {student.average_wellbeing_percentage()}%"
                                if student.surveys else "No survey data")
                print(f"    {student.name} ({student.student_id}): "
                      f"sleep {sleep_label}; {survey_label}")

        elif sub_choice == "4":
            day = get_nonempty_string("  Enter day of week (e.g. Monday): ")
            matches = system.exercise_sessions_on_day(day)
            print(f"\n  -- Exercise Sessions on {day.capitalize()} --")
            if not matches:
                print("    None found.")
            for student, record in matches:
                print(f"    {student.name} ({student.student_id}): {record}")

        elif sub_choice == "5":
            print("\n  -- Wellness Survey Summary per Student --")
            for sid, summary in system.survey_summary_report().items():
                student = system.get_student(sid)
                if summary["survey_count"] == 0:
                    print(f"    {student.name} ({sid}): No survey data")
                else:
                    print(f"    {student.name} ({sid}): "
                          f"surveys={summary['survey_count']}, "
                          f"avg stress={summary['average_stress']}/10, "
                          f"avg mood={summary['average_mood']}/10, "
                          f"avg WHO-5={summary['average_wellbeing']}%")

        elif sub_choice == "6":
            print("\n  -- All Wellness Concerns (polymorphic across record types) --")
            concerns = system.all_concerns_report()
            if not concerns:
                print("    None found - no records are currently flagged.")
            for student, record in concerns:
                kind = record.to_dict()["type"]
                print(f"    {student.name} ({student.student_id}) [{kind}]: {record.summary_line()}")

        elif sub_choice == "0":
            viewing_reports = False
            continue
        else:
            print("  ! Invalid choice.")

        input("\n  Press ENTER to return to the Reports menu...")


# -- Analytics menu ------------------------------------------------------
@safe_action
def handle_analytics(system):
    analytics = WellnessAnalytics(system, CHARTS_DIR)
    viewing = True
    while viewing:
        print("\n" + SEP)
        print("  ANALYTICS & DASHBOARD (pandas + matplotlib)")
        print(SEP)
        print("""
              1. Exercise summary table (pandas)
              2. Sleep summary table (pandas)
              3. Survey summary table (pandas)
              4. Chart: exercise minutes per student (PNG)
              5. Chart: average sleep per student (PNG)
              6. Chart: stress & mood trend (PNG)
              7. Build full dashboard (PNG, 4 panels)
              0. Back to main menu
        """)
        sub_choice = input("  Enter your choice: ").strip()

        if sub_choice == "1":
            print("\n  -- Exercise Summary --")
            analytics.print_exercise_summary()
        elif sub_choice == "2":
            print("\n  -- Sleep Summary --")
            analytics.print_sleep_summary()
        elif sub_choice == "3":
            print("\n  -- Survey Summary (avg stress / mood) --")
            analytics.print_survey_summary()
        elif sub_choice == "4":
            path = analytics.plot_exercise_minutes_by_student()
            print(f"\n  Chart saved to: {path}")
        elif sub_choice == "5":
            path = analytics.plot_average_sleep_by_student()
            print(f"\n  Chart saved to: {path}")
        elif sub_choice == "6":
            path = analytics.plot_stress_mood_trend()
            print(f"\n  Chart saved to: {path}")
        elif sub_choice == "7":
            path = analytics.build_dashboard()
            print(f"\n  Dashboard saved to: {path}")
        elif sub_choice == "0":
            viewing = False
            continue
        else:
            print("  ! Invalid choice.")

        if viewing:
            input("\n  Press ENTER to return to the Analytics menu...")


# -- Main loop -------------------------------------------------------------
def build_system():
    repository = CsvStudentRepository(DATA_PATH)
    return WellnessSystem(repository=repository)


def main():
    system = build_system()

    print("\n  Welcome to CampusTrack - Fitness & Wellness Monitoring System")
    print(f"  Data is loaded from and saved to: {DATA_PATH}")

    running = True
    while running:
        print("\n" + SEP)
        print("  CAMPUSTRACK - FITNESS & WELLNESS SYSTEM")
        print(SEP)
        print("""
              1.  Add Student
              2.  Update Student
              3.  Add Exercise Record
              4.  Update Exercise Record
              5.  Add Sleep Pattern
              6.  Update Sleep Pattern
              7.  Complete Wellness Survey
              8.  Update Wellness Survey
              9.  Display Exercise Info
              10. Display Sleep Info - Weekly
              11. Display Survey History
              12. Display All Students
              13. Reports
              14. Analytics & Dashboard (pandas / matplotlib)
              0.  Exit
        """)
        print(SEP)
        choice = input("  Enter your choice: ").strip()

        if choice == "1":
            handle_add_student(system)
        elif choice == "2":
            handle_update_student(system)
        elif choice == "3":
            student = resolve_student(system)
            if student:
                handle_add_exercise(system, student)
        elif choice == "4":
            student = resolve_student(system)
            if student:
                handle_update_exercise(system, student)
        elif choice == "5":
            student = resolve_student(system)
            if student:
                handle_add_sleep(system, student)
        elif choice == "6":
            student = resolve_student(system)
            if student:
                handle_update_sleep(system, student)
        elif choice == "7":
            student = resolve_student(system)
            if student:
                handle_add_survey(system, student)
        elif choice == "8":
            student = resolve_student(system)
            if student:
                handle_update_survey(system, student)
        elif choice == "9":
            student = resolve_student(system)
            if student:
                handle_display_exercise(student)
        elif choice == "10":
            student = resolve_student(system)
            if student:
                handle_display_sleep(student)
        elif choice == "11":
            student = resolve_student(system)
            if student:
                handle_display_surveys(student)
        elif choice == "12":
            handle_display_all(system)
        elif choice == "13":
            handle_reports(system)
        elif choice == "14":
            handle_analytics(system)
        elif choice == "0":
            print("\n  All data is saved. Thank you for using CampusTrack. Goodbye!")
            running = False
        else:
            print("  ! Invalid choice. Please enter 0-14.")

        if running:
            input("\n  Press ENTER to return to the menu...")


if __name__ == "__main__":
    main()