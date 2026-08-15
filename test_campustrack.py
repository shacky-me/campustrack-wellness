"""
Unit tests for CampusTrack (single-file edition).

Run with:  python -m unittest test_campustrack -v

All tests for models, the repository, the system, and analytics live in
this one file, organised into sections that mirror campustrack_app.py.
Repository/analytics tests use a temporary directory so they never
touch a real data/ or charts/ folder.
"""

import os
import shutil
import tempfile
import unittest

import pandas as pd

from campustrack_app import (
    CsvStudentRepository,
    ExerciseRecord,
    InMemoryStudentRepository,
    RecordNotFoundError,
    SleepPattern,
    Student,
    StudentNotFoundError,
    Survey,
    WellnessAnalytics,
    WellnessSystem,
)


# =====================================================================
# Models
# =====================================================================

class TestExerciseRecord(unittest.TestCase):

    def test_valid_record_created(self):
        record = ExerciseRecord(3, "Running", 45, "Monday", "07:30")
        self.assertEqual(record.exercise_type, "running")
        self.assertEqual(record.day, "monday")
        self.assertFalse(record.is_concern())

    def test_short_session_is_flagged_as_concern(self):
        record = ExerciseRecord(1, "yoga", 5, "friday", "18:00")
        self.assertTrue(record.is_concern())

    def test_invalid_days_per_week_raises(self):
        with self.assertRaises(ValueError):
            ExerciseRecord(9, "swimming", 30, "tuesday", "06:00")

    def test_invalid_duration_raises(self):
        with self.assertRaises(ValueError):
            ExerciseRecord(2, "swimming", 0, "tuesday", "06:00")

    def test_empty_exercise_type_raises(self):
        with self.assertRaises(ValueError):
            ExerciseRecord(2, "   ", 30, "tuesday", "06:00")

    def test_round_trip_to_dict_from_dict(self):
        original = ExerciseRecord(4, "cycling", 60, "sunday", "08:00")
        rebuilt = ExerciseRecord.from_dict(original.to_dict())
        self.assertEqual(original.record_id, rebuilt.record_id)
        self.assertEqual(original.to_dict(), rebuilt.to_dict())


class TestSleepPattern(unittest.TestCase):

    def test_hours_calculated_same_day(self):
        record = SleepPattern(True, "22:00", "23:30")
        self.assertEqual(record.hours_slept, 1.5)

    def test_hours_calculated_across_midnight(self):
        record = SleepPattern(True, "23:00", "07:00")
        self.assertEqual(record.hours_slept, 8.0)
        self.assertFalse(record.is_concern())

    def test_deficit_flagged_as_concern(self):
        record = SleepPattern(False, "01:00", "05:00")
        self.assertEqual(record.hours_slept, 4.0)
        self.assertTrue(record.is_concern())
        self.assertEqual(record.status, "Deficit")

    def test_round_trip_to_dict_from_dict(self):
        original = SleepPattern(True, "22:30", "06:30")
        rebuilt = SleepPattern.from_dict(original.to_dict())
        self.assertEqual(original.hours_slept, rebuilt.hours_slept)
        self.assertEqual(original.record_id, rebuilt.record_id)


class TestSurvey(unittest.TestCase):

    def test_wellbeing_percentage(self):
        survey = Survey("2026-01-01", 3, 8, [4, 4, 4, 4, 4])
        self.assertEqual(survey.wellbeing_raw_score(), 20)
        self.assertEqual(survey.wellbeing_percentage(), 80)
        self.assertFalse(survey.needs_attention())

    def test_high_stress_flags_attention(self):
        survey = Survey("2026-01-01", 9, 8, [4, 4, 4, 4, 4])
        self.assertTrue(survey.needs_attention())
        self.assertTrue(survey.is_concern())

    def test_low_wellbeing_flags_attention(self):
        survey = Survey("2026-01-01", 2, 8, [1, 1, 1, 1, 1])
        self.assertLess(survey.wellbeing_percentage(), 50)
        self.assertTrue(survey.needs_attention())

    def test_invalid_wellbeing_answers_length_raises(self):
        with self.assertRaises(ValueError):
            Survey("2026-01-01", 5, 5, [1, 2, 3])

    def test_invalid_stress_level_raises(self):
        with self.assertRaises(ValueError):
            Survey("2026-01-01", 11, 5, [1, 1, 1, 1, 1])

    def test_round_trip_to_dict_from_dict(self):
        original = Survey("2026-02-14", 6, 7, [3, 3, 3, 3, 3], notes="feeling okay")
        rebuilt = Survey.from_dict(original.to_dict())
        self.assertEqual(original.wellbeing_answers, rebuilt.wellbeing_answers)
        self.assertEqual(original.notes, rebuilt.notes)


class TestStudent(unittest.TestCase):

    def setUp(self):
        self.student = Student("s1", "Ada Lovelace", 21, "Computer Science")

    def test_student_id_is_uppercased(self):
        self.assertEqual(self.student.student_id, "S1")

    def test_invalid_age_raises(self):
        with self.assertRaises(ValueError):
            Student("s2", "Bad Age", 200, "Maths")

    def test_average_sleep_hours_with_no_records(self):
        self.assertEqual(self.student.average_sleep_hours(), 0.0)

    def test_total_exercise_minutes(self):
        self.student.add_exercise_record(ExerciseRecord(3, "running", 30, "mon", "07:00"))
        self.student.add_exercise_record(ExerciseRecord(3, "swimming", 45, "wed", "07:00"))
        self.assertEqual(self.student.total_exercise_minutes(), 75)

    def test_needs_intervention_on_low_sleep(self):
        for _ in range(3):
            self.student.add_sleep_record(SleepPattern(False, "02:00", "05:00"))  # 3 hrs
        self.assertTrue(self.student.needs_intervention())

    def test_find_and_remove_exercise_record(self):
        record = ExerciseRecord(3, "running", 30, "mon", "07:00")
        self.student.add_exercise_record(record)
        found = self.student.find_exercise_record(record.record_id)
        self.assertIs(found, record)

        self.student.remove_exercise_record(record.record_id)
        self.assertIsNone(self.student.find_exercise_record(record.record_id))


# =====================================================================
# Repository
# =====================================================================

class TestInMemoryStudentRepository(unittest.TestCase):

    def test_add_get_exists_all_count(self):
        repo = InMemoryStudentRepository()
        student = Student("s1", "Ada", 20, "CS")
        repo.add(student)

        self.assertTrue(repo.exists("S1"))
        self.assertEqual(repo.get("S1"), student)
        self.assertEqual(repo.count(), 1)
        self.assertEqual(repo.all(), [student])


class TestCsvStudentRepository(unittest.TestCase):
    """
    Uses a temporary directory + single data file for every test so the
    real project's data file is never touched by the test suite.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="campustrack_test_")
        self.data_path = os.path.join(self.tmp_dir, "campustrack_data.csv")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_creates_data_file_and_starts_empty(self):
        repo = CsvStudentRepository(self.data_path)
        self.assertEqual(repo.count(), 0)

    def test_add_student_writes_csv_row(self):
        repo = CsvStudentRepository(self.data_path)
        repo.add(Student("s1", "Grace Hopper", 30, "Computer Science"))

        self.assertTrue(os.path.exists(self.data_path))
        df = pd.read_csv(self.data_path)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["row_type"], "student")
        self.assertEqual(df.iloc[0]["student_id"], "S1")

    def test_records_persist_and_reload_correctly(self):
        repo = CsvStudentRepository(self.data_path)
        student = Student("s1", "Grace Hopper", 30, "Computer Science")
        repo.add(student)
        student.add_exercise_record(ExerciseRecord(3, "running", 45, "monday", "07:00"))
        student.add_sleep_record(SleepPattern(True, "22:00", "06:00"))
        student.add_survey(Survey("2026-01-05", 4, 6, [3, 3, 3, 3, 3], "ok"))
        repo.persist_exercise(student)
        repo.persist_sleep(student)
        repo.persist_survey(student)

        # simulate restarting the program: build a fresh repository over
        # the same single data file and confirm every record comes back.
        reloaded_repo = CsvStudentRepository(self.data_path)
        reloaded = reloaded_repo.get("S1")

        self.assertIsNotNone(reloaded)
        self.assertEqual(len(reloaded.exercise_records), 1)
        self.assertEqual(reloaded.exercise_records[0].exercise_type, "running")
        self.assertEqual(len(reloaded.sleep_records), 1)
        self.assertEqual(reloaded.sleep_records[0].hours_slept, 8.0)
        self.assertEqual(len(reloaded.surveys), 1)
        self.assertEqual(reloaded.surveys[0].stress_level, 4)

    def test_all_rows_land_in_one_file(self):
        repo = CsvStudentRepository(self.data_path)
        student = Student("s1", "Ada Lovelace", 25, "Mathematics")
        repo.add(student)
        student.add_exercise_record(ExerciseRecord(2, "yoga", 20, "friday", "18:00"))
        student.add_sleep_record(SleepPattern(True, "22:00", "06:00"))
        repo.persist_exercise(student)
        repo.persist_sleep(student)

        # everything - the student row and both record rows - is in the
        # single data file, distinguished by the row_type column.
        df = pd.read_csv(self.data_path)
        self.assertEqual(len(df), 3)
        self.assertSetEqual(set(df["row_type"]), {"student", "exercise", "sleep"})
        self.assertFalse(os.path.exists(os.path.join(self.tmp_dir, "students.csv")))

    def test_updating_a_record_persists_the_change_to_disk(self):
        repo = CsvStudentRepository(self.data_path)
        student = Student("s1", "Ada Lovelace", 25, "Mathematics")
        repo.add(student)
        record = ExerciseRecord(2, "yoga", 20, "friday", "18:00")
        student.add_exercise_record(record)
        repo.persist_exercise(student)

        record.duration = 90
        repo.persist_exercise(student)

        df = pd.read_csv(self.data_path)
        exercise_rows = df[df["row_type"] == "exercise"]
        self.assertEqual(len(exercise_rows), 1)  # rewritten in place, not appended
        self.assertEqual(int(exercise_rows.iloc[0]["duration"]), 90)

        reloaded_repo = CsvStudentRepository(self.data_path)
        reloaded_record = reloaded_repo.get("S1").exercise_records[0]
        self.assertEqual(reloaded_record.duration, 90)
        self.assertEqual(reloaded_record.record_id, record.record_id)

    def test_missing_data_file_loads_as_empty_without_crashing(self):
        repo = CsvStudentRepository(self.data_path)
        self.assertEqual(repo.count(), 0)

    def test_empty_data_file_does_not_crash_load(self):
        os.makedirs(self.tmp_dir, exist_ok=True)
        open(self.data_path, "w").close()  # zero-byte file
        repo = CsvStudentRepository(self.data_path)
        self.assertEqual(repo.count(), 0)


# =====================================================================
# System
# =====================================================================

class TestWellnessSystem(unittest.TestCase):

    def setUp(self):
        self.system = WellnessSystem(repository=InMemoryStudentRepository(), max_students=2)
        self.system.add_student(Student("s1", "Ada Lovelace", 22, "Computer Science"))
        self.system.add_student(Student("s2", "Alan Turing", 24, "Mathematics"))

    def test_is_full_respects_max_students(self):
        self.assertTrue(self.system.is_full())

    def test_require_student_raises_for_unknown_id(self):
        with self.assertRaises(StudentNotFoundError):
            self.system.require_student("ZZZ")

    def test_add_exercise_record_via_system(self):
        record = ExerciseRecord(3, "running", 40, "monday", "07:00")
        self.system.add_exercise_record("S1", record)
        student = self.system.get_student("S1")
        self.assertEqual(len(student.exercise_records), 1)

    def test_update_exercise_record_changes_object_in_place(self):
        record = ExerciseRecord(3, "running", 40, "monday", "07:00")
        self.system.add_exercise_record("S1", record)

        updated = self.system.update_exercise_record("S1", record.record_id, duration=90)
        self.assertEqual(updated.duration, 90)
        self.assertIs(updated, record)

    def test_update_unknown_record_id_raises(self):
        with self.assertRaises(RecordNotFoundError):
            self.system.update_exercise_record("S1", "doesnotexist", duration=10)

    def test_update_student_fields(self):
        self.system.update_student("S1", age=23, course="Software Engineering")
        student = self.system.get_student("S1")
        self.assertEqual(student.age, 23)
        self.assertEqual(student.course, "Software Engineering")
        self.assertEqual(student.name, "Ada Lovelace")

    def test_exercise_count_report(self):
        self.system.add_exercise_record("S1", ExerciseRecord(3, "running", 40, "monday", "07:00"))
        self.system.add_exercise_record("S1", ExerciseRecord(3, "cycling", 30, "tuesday", "07:00"))
        report = self.system.exercise_count_report()
        self.assertEqual(report["S1"], 2)
        self.assertEqual(report["S2"], 0)

    def test_students_needing_intervention(self):
        self.system.add_survey("S2", Survey("2026-01-01", 9, 2, [0, 0, 0, 0, 0], "stressed"))
        flagged = self.system.students_needing_intervention()
        flagged_ids = [s.student_id for s in flagged]
        self.assertIn("S2", flagged_ids)
        self.assertNotIn("S1", flagged_ids)

    def test_exercise_sessions_on_day_report(self):
        self.system.add_exercise_record("S1", ExerciseRecord(3, "running", 40, "monday", "07:00"))
        self.system.add_exercise_record("S2", ExerciseRecord(2, "swimming", 30, "friday", "18:00"))
        results = self.system.exercise_sessions_on_day("monday")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0].student_id, "S1")

    def test_all_concerns_report_is_polymorphic(self):
        self.system.add_exercise_record("S1", ExerciseRecord(1, "yoga", 5, "monday", "07:00"))  # short session
        self.system.add_sleep_record("S1", SleepPattern(False, "02:00", "05:00"))  # deficit
        concerns = self.system.all_concerns_report()
        kinds = {record.to_dict()["type"] for _student, record in concerns}
        self.assertIn("exercise", kinds)
        self.assertIn("sleep", kinds)


# =====================================================================
# Analytics
# =====================================================================

class TestWellnessAnalytics(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="campustrack_charts_")
        self.system = WellnessSystem(repository=InMemoryStudentRepository())
        self.system.add_student(Student("s1", "Ada Lovelace", 22, "Computer Science"))
        self.system.add_exercise_record("S1", ExerciseRecord(3, "running", 40, "monday", "07:00"))
        self.system.add_sleep_record("S1", SleepPattern(True, "22:00", "06:00"))
        self.system.add_survey("S1", Survey("2026-01-01", 4, 7, [3, 3, 3, 3, 3], "fine"))
        self.analytics = WellnessAnalytics(self.system, self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_exercise_dataframe_has_expected_rows_and_columns(self):
        df = self.analytics.exercise_dataframe()
        self.assertEqual(len(df), 1)
        self.assertIn("duration", df.columns)
        self.assertEqual(df.iloc[0]["student_name"], "Ada Lovelace")

    def test_plot_exercise_minutes_creates_png_file(self):
        path = self.analytics.plot_exercise_minutes_by_student()
        self.assertTrue(os.path.exists(path))
        self.assertGreater(os.path.getsize(path), 0)

    def test_plot_average_sleep_creates_png_file(self):
        path = self.analytics.plot_average_sleep_by_student()
        self.assertTrue(os.path.exists(path))

    def test_dashboard_creates_single_png_with_four_panels(self):
        path = self.analytics.build_dashboard()
        self.assertTrue(os.path.exists(path))
        self.assertGreater(os.path.getsize(path), 0)

    def test_charts_do_not_crash_with_no_data(self):
        empty_system = WellnessSystem(repository=InMemoryStudentRepository())
        empty_analytics = WellnessAnalytics(empty_system, self.tmp_dir)
        path = empty_analytics.build_dashboard(filename="empty_dashboard.png")
        self.assertTrue(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
