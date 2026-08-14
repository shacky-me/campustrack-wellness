"""
Domain classes only. No file I/O, no print(), no input() - this module
should never need to know that a console or a CSV file exists. That
separation is what lets repository.py and cli.py be built and tested
independently.

    Person (ABC)
      Student

    WellnessRecord (ABC)
      ExerciseRecord
      SleepPattern
      Survey
"""

from abc import ABC, abstractmethod
from datetime import datetime

from campustrack.exceptions import ValidationError

SLEEP_BENCHMARK = 8            # benchmark hours of sleep per night
SHORT_SESSION_MINUTES = 10     # exercise sessions shorter than this are flagged
STRESS_CONCERN_THRESHOLD = 7   # stress_level (1-10) at/above this is a concern
MOOD_CONCERN_THRESHOLD = 3     # mood_rating (1-10) at/below this is a concern

# People

class Person(ABC):
    """Common identity fields shared by anyone the system tracks."""

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
            raise ValidationError("Person ID cannot be empty.")
        self._person_id = str(value).strip().upper()

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if not str(value).strip():
            raise ValidationError("Name cannot be empty.")
        self._name = str(value).strip()

    @property
    def age(self):
        return self._age

    @age.setter
    def age(self, value):
        try:
            age = int(value)
        except (TypeError, ValueError):
            raise ValidationError("Age must be a whole number.")
        if not (1 <= age <= 120):
            raise ValidationError("Age must be between 1 and 120.")
        self._age = age

    @abstractmethod
    def role_label(self):
        """Polymorphic hook - each subclass describes itself."""
        raise NotImplementedError


class Student(Person):
    """A student plus their exercise/sleep/survey history."""

    def __init__(self, student_id, name, age, course, faculty):
        super().__init__(student_id, name, age)
        self.course = course
        self.faculty = faculty
        self._exercise_records = []
        self._sleep_records = []
        self._surveys = []

    # identity/academic fields
    @property
    def student_id(self):
        return self.person_id

    @property
    def course(self):
        return self._course

    @course.setter
    def course(self, value):
        if not str(value).strip():
            raise ValidationError("Course cannot be empty.")
        self._course = str(value).strip()

    @property
    def faculty(self):
        return self._faculty

    @faculty.setter
    def faculty(self, value):
        if not str(value).strip():
            raise ValidationError("Faculty cannot be empty.")
        self._faculty = str(value).strip()

    def role_label(self):
        return f"Student ({self.course}, {self.faculty})"

    # record collections (read-only views; mutate via add_* methods)
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
            raise ValidationError("Expected an ExerciseRecord instance.")
        self._exercise_records.append(record)

    def add_sleep_record(self, record):
        if not isinstance(record, SleepPattern):
            raise ValidationError("Expected a SleepPattern instance.")
        self._sleep_records.append(record)

    def add_survey(self, survey):
        if not isinstance(survey, Survey):
            raise ValidationError("Expected a Survey instance.")
        self._surveys.append(survey)

    # derived stats
    def average_sleep_hours(self):
        if not self._sleep_records:
            return None
        return round(sum(r.hours_slept for r in self._sleep_records) / len(self._sleep_records), 2)

    def has_concerns(self):
        """True if any single record (exercise, sleep, or survey) flags
        itself as a concern - used by the 'all wellness concerns' report."""
        all_records = [*self._exercise_records, *self._sleep_records, *self._surveys]
        return any(r.is_concern() for r in all_records)

    def concern_summaries(self):
        all_records = [*self._exercise_records, *self._sleep_records, *self._surveys]
        return [r.summary_line() for r in all_records if r.is_concern()]

    # persistence support
    def as_row(self):
        avg_sleep = self.average_sleep_hours()
        sleep_label = f"{avg_sleep}h" if avg_sleep is not None else "-"
        return "  {:<8} {:<20} {:<5} {:<22} {:<20} {}".format(
            self.student_id, self.name, self.age, self.course, self.faculty, sleep_label
        )

    def to_dict(self):
        return {
            "student_id": self.student_id,
            "name": self.name,
            "age": self.age,
            "course": self.course,
            "faculty": self.faculty,
        }

    def __str__(self):
        return f"{self.student_id:<8} | {self.name:<20} | Age {self.age:<3} | {self.course} | {self.faculty}"

    def __repr__(self):
        return f"Student({self.student_id!r}, {self.name!r})"

# Wellness records

class WellnessRecord(ABC):
    """Common contract for anything that can be logged against a student
    and flagged as a wellness concern. Polymorphism here is what lets
    Student.has_concerns()/concern_summaries() treat exercise, sleep and
    survey entries uniformly without an if/elif chain."""

    @abstractmethod
    def is_concern(self):
        """True if this record should be flagged in the intervention/
        concerns reports."""
        raise NotImplementedError

    @abstractmethod
    def summary_line(self):
        """One human-readable line describing this record, used in
        reports and concern listings."""
        raise NotImplementedError

    @abstractmethod
    def to_dict(self):
        """Plain-dict representation for persistence."""
        raise NotImplementedError


class ExerciseRecord(WellnessRecord):

    def __init__(self, days_per_week, exercise_type, duration, day, time_of_day):
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
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise ValidationError("Days per week must be a whole number.")
        if not (1 <= v <= 7):
            raise ValidationError("Days per week must be between 1 and 7.")
        self._days_per_week = v

    @property
    def exercise_type(self):
        return self._exercise_type

    @exercise_type.setter
    def exercise_type(self, value):
        if not str(value).strip():
            raise ValidationError("Exercise type cannot be empty.")
        self._exercise_type = str(value).strip().lower()

    @property
    def duration(self):
        return self._duration

    @duration.setter
    def duration(self, value):
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise ValidationError("Duration must be a whole number of minutes.")
        if not (1 <= v <= 1440):
            raise ValidationError("Duration must be between 1 and 1440 minutes.")
        self._duration = v

    @property
    def day(self):
        return self._day

    @day.setter
    def day(self, value):
        if not str(value).strip():
            raise ValidationError("Day cannot be empty.")
        self._day = str(value).strip().lower()

    @property
    def time_of_day(self):
        return self._time_of_day

    @time_of_day.setter
    def time_of_day(self, value):
        try:
            datetime.strptime(str(value), "%H:%M")
        except ValueError:
            raise ValidationError("Time of day must be in HH:MM 24-hour format.")
        self._time_of_day = str(value)

    def is_concern(self):
        return self.duration < SHORT_SESSION_MINUTES

    def summary_line(self):
        flag = " [SHORT SESSION]" if self.is_concern() else ""
        return (f"{self.exercise_type.title()} - {self.duration} min on "
                f"{self.day.title()} at {self.time_of_day}{flag}")

    def to_dict(self):
        return {
            "days_per_week": self.days_per_week,
            "exercise_type": self.exercise_type,
            "duration": self.duration,
            "day": self.day,
            "time_of_day": self.time_of_day,
        }


class SleepPattern(WellnessRecord):

    def __init__(self, had_good_sleep, start, end):
        self.had_good_sleep = had_good_sleep
        self.start = start
        self.end = end

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
        try:
            datetime.strptime(str(value), "%H:%M")
        except ValueError:
            raise ValidationError("Sleep start time must be in HH:MM 24-hour format.")
        self._start = str(value)

    @property
    def end(self):
        return self._end

    @end.setter
    def end(self, value):
        try:
            datetime.strptime(str(value), "%H:%M")
        except ValueError:
            raise ValidationError("Wake-up time must be in HH:MM 24-hour format.")
        self._end = str(value)

    @property
    def hours_slept(self):
        start_dt = datetime.strptime(self.start, "%H:%M")
        end_dt = datetime.strptime(self.end, "%H:%M")
        if end_dt <= start_dt:
            # crossed midnight - add a day to the end time
            end_dt = end_dt.replace(day=start_dt.day + 1)
        return round((end_dt - start_dt).seconds / 3600, 2)

    def is_concern(self):
        return self.hours_slept < SLEEP_BENCHMARK

    def summary_line(self):
        flag = " [BELOW BENCHMARK]" if self.is_concern() else ""
        return f"Slept {self.hours_slept}h ({self.start} - {self.end}){flag}"

    def to_dict(self):
        return {"had_good_sleep": self.had_good_sleep, "start": self.start, "end": self.end}


class Survey(WellnessRecord):

    def __init__(self, entry_date, stress_level, mood_rating, wellbeing_answers, notes=""):
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
        try:
            datetime.strptime(str(value), "%Y-%m-%d")
        except ValueError:
            raise ValidationError("Entry date must be in YYYY-MM-DD format.")
        self._entry_date = str(value)

    @property
    def stress_level(self):
        return self._stress_level

    @stress_level.setter
    def stress_level(self, value):
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise ValidationError("Stress level must be a whole number.")
        if not (1 <= v <= 10):
            raise ValidationError("Stress level must be between 1 and 10.")
        self._stress_level = v

    @property
    def mood_rating(self):
        return self._mood_rating

    @mood_rating.setter
    def mood_rating(self, value):
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise ValidationError("Mood rating must be a whole number.")
        if not (1 <= v <= 10):
            raise ValidationError("Mood rating must be between 1 and 10.")
        self._mood_rating = v

    @property
    def wellbeing_answers(self):
        return list(self._wellbeing_answers)

    @wellbeing_answers.setter
    def wellbeing_answers(self, value):
        try:
            answers = [int(a) for a in value]
        except (TypeError, ValueError):
            raise ValidationError("Wellbeing answers must be a list of whole numbers.")
        if not answers or any(not (1 <= a <= 5) for a in answers):
            raise ValidationError("Each wellbeing answer must be between 1 and 5.")
        self._wellbeing_answers = answers

    @property
    def notes(self):
        return self._notes

    @notes.setter
    def notes(self, value):
        self._notes = str(value).strip() if value else ""

    @property
    def wellbeing_average(self):
        return round(sum(self.wellbeing_answers) / len(self.wellbeing_answers), 2)

    def is_concern(self):
        return self.stress_level >= STRESS_CONCERN_THRESHOLD or self.mood_rating <= MOOD_CONCERN_THRESHOLD

    def summary_line(self):
        flag = " [FLAGGED]" if self.is_concern() else ""
        return (f"{self.entry_date}: stress {self.stress_level}/10, "
                f"mood {self.mood_rating}/10, wellbeing avg {self.wellbeing_average}/5{flag}")

    def to_dict(self):
        return {
            "entry_date": self.entry_date,
            "stress_level": self.stress_level,
            "mood_rating": self.mood_rating,
            "wellbeing_answers": self.wellbeing_answers,
            "notes": self.notes,
        }
