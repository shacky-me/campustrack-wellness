"""
Unit tests for CampusTrack Business Logic & Reports.
Assigned section: Urbashi Barua

These tests use the project's real models and in-memory repository.
They verify report accuracy, update-by-record-ID behaviour, filtering,
and the required StudentNotFoundError / RecordNotFoundError cases.
"""

import unittest

from campustrack.exceptions import RecordNotFoundError, StudentNotFoundError
from campustrack.models import ExerciseRecord, SleepPattern, Student, Survey
from campustrack.repository import InMemoryStudentRepository
from campustrack.system import WellnessSystem


class TestWellnessSystem(unittest.TestCase):

    def setUp(self):
        self.repository = InMemoryStudentRepository()
        self.system = WellnessSystem(
            self.repository,
            max_students=20,
        )

        self.student_1 = Student(
            "S001",
            "Alex Morgan",
            22,
            "Master of IT",
        )
        self.student_2 = Student(
            "S002",
            "Taylor Lee",
            24,
            "Master of Business",
        )

        self.system.add_student(self.student_1)
        self.system.add_student(self.student_2)

    # --------------------------------------------------------------
    # Helpers
    # --------------------------------------------------------------
    @staticmethod
    def make_exercise(
        duration=30,
        day="monday",
        exercise_type="walking",
    ):
        return ExerciseRecord(
            3,
            exercise_type,
            duration,
            day,
            "07:30",
        )

    @staticmethod
    def make_sleep(start="22:00", end="06:00", good=True):
        return SleepPattern(good, start, end)

    @staticmethod
    def make_survey(
        stress=4,
        mood=7,
        answers=None,
        notes="",
    ):
        if answers is None:
            answers = [4, 4, 4, 4, 4]

        return Survey(
            "2026-08-15",
            stress,
            mood,
            answers,
            notes,
        )

    # --------------------------------------------------------------
    # Student logic
    # --------------------------------------------------------------
    def test_get_student_returns_registered_student(self):
        student = self.system.get_student("s001")
        self.assertEqual(student.student_id, "S001")

    def test_get_student_raises_student_not_found(self):
        with self.assertRaises(StudentNotFoundError):
            self.system.get_student("S999")

    def test_duplicate_student_id_is_rejected(self):
        duplicate = Student(
            "S001",
            "Different Person",
            30,
            "MBA",
        )

        with self.assertRaises(ValueError):
            self.system.add_student(duplicate)

    def test_update_student_changes_selected_fields(self):
        updated = self.system.update_student(
            "S001",
            name="Alex M.",
            course="Data Science",
        )

        self.assertEqual(updated.name, "Alex M.")
        self.assertEqual(updated.course, "Data Science")

    # --------------------------------------------------------------
    # Record add/update logic
    # --------------------------------------------------------------
    def test_add_exercise_generates_record_id(self):
        record = self.make_exercise()

        added = self.system.add_exercise_record(
            "S001",
            record,
        )

        self.assertTrue(hasattr(added, "record_id"))
        self.assertEqual(added.record_id, "EX001")

    def test_update_exercise_record_by_id(self):
        record = self.make_exercise(duration=30)
        self.system.add_exercise_record("S001", record)

        updated = self.system.update_exercise_record(
            "S001",
            record.record_id,
            duration=45,
            day="tuesday",
        )

        self.assertEqual(updated.duration, 45)
        self.assertEqual(updated.day, "tuesday")

    def test_update_missing_record_raises_record_not_found(self):
        with self.assertRaises(RecordNotFoundError):
            self.system.update_exercise_record(
                "S001",
                "EX999",
                duration=40,
            )

    def test_update_sleep_recalculates_hours(self):
        record = self.make_sleep(
            start="22:00",
            end="06:00",
        )
        self.system.add_sleep_record("S001", record)

        updated = self.system.update_sleep_record(
            "S001",
            record.record_id,
            start="23:00",
            end="06:00",
        )

        self.assertEqual(updated.hours_slept, 7.0)

    # --------------------------------------------------------------
    # Reports
    # --------------------------------------------------------------
    def test_exercise_count_report(self):
        self.system.add_exercise_record(
            "S001",
            self.make_exercise(),
        )
        self.system.add_exercise_record(
            "S001",
            self.make_exercise(day="wednesday"),
        )
        self.system.add_exercise_record(
            "S002",
            self.make_exercise(),
        )

        report = self.system.exercise_count_report()

        self.assertEqual(report["S001"], 2)
        self.assertEqual(report["S002"], 1)

    def test_average_sleep_report(self):
        self.system.add_sleep_record(
            "S001",
            self.make_sleep("22:00", "06:00"),
        )
        self.system.add_sleep_record(
            "S001",
            self.make_sleep("23:00", "06:00"),
        )

        report = self.system.average_sleep_report()

        self.assertEqual(report["S001"], 7.5)
        self.assertEqual(report["S002"], 0.0)

    def test_sessions_by_day_report(self):
        self.system.add_exercise_record(
            "S001",
            self.make_exercise(day="monday"),
        )
        self.system.add_exercise_record(
            "S002",
            self.make_exercise(day="tuesday"),
        )

        matches = self.system.sessions_by_day_report("Monday")

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][0].student_id, "S001")

    def test_survey_summary_report(self):
        self.system.add_survey(
            "S001",
            self.make_survey(
                stress=4,
                mood=8,
                answers=[4, 4, 4, 4, 4],
            ),
        )

        report = self.system.survey_summary_report()
        summary = report["S001"]

        self.assertEqual(summary["survey_count"], 1)
        self.assertEqual(summary["average_stress"], 4.0)
        self.assertEqual(summary["average_mood"], 8.0)
        self.assertEqual(summary["average_wellbeing"], 80.0)

    def test_students_needing_intervention(self):
        self.system.add_sleep_record(
            "S001",
            self.make_sleep(
                start="01:00",
                end="05:00",
                good=False,
            ),
        )

        flagged = self.system.students_needing_intervention()
        ids = [student.student_id for student in flagged]

        self.assertIn("S001", ids)

    def test_all_concerns_report_uses_polymorphism(self):
        self.system.add_exercise_record(
            "S001",
            self.make_exercise(duration=5),
        )
        self.system.add_sleep_record(
            "S001",
            self.make_sleep(
                start="01:00",
                end="05:00",
                good=False,
            ),
        )
        self.system.add_survey(
            "S001",
            self.make_survey(
                stress=9,
                mood=3,
                answers=[1, 1, 1, 1, 1],
            ),
        )

        concerns = self.system.all_concerns_report()
        kinds = {
            item["record_type"]
            for item in concerns
        }

        self.assertIn("exercise", kinds)
        self.assertIn("sleep", kinds)
        self.assertIn("survey", kinds)

    def test_student_wellness_summary(self):
        self.system.add_exercise_record(
            "S001",
            self.make_exercise(duration=40),
        )
        self.system.add_sleep_record(
            "S001",
            self.make_sleep("22:00", "06:00"),
        )
        self.system.add_survey(
            "S001",
            self.make_survey(),
        )

        summary = self.system.student_wellness_summary("S001")

        self.assertEqual(summary["exercise_records"], 1)
        self.assertEqual(summary["total_exercise_minutes"], 40)
        self.assertEqual(summary["sleep_records"], 1)
        self.assertEqual(summary["survey_count"], 1)

    def test_overall_summary_report(self):
        self.system.add_exercise_record(
            "S001",
            self.make_exercise(),
        )
        self.system.add_sleep_record(
            "S001",
            self.make_sleep(),
        )
        self.system.add_survey(
            "S001",
            self.make_survey(),
        )

        report = self.system.overall_summary_report()

        self.assertEqual(report["total_students"], 2)
        self.assertEqual(report["total_exercise_records"], 1)
        self.assertEqual(report["total_sleep_records"], 1)
        self.assertEqual(report["total_surveys"], 1)

    def test_filter_students_by_course(self):
        matches = self.system.filter_students(
            course="master of it"
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].student_id, "S001")


if __name__ == "__main__":
    unittest.main()
