import os
import shutil
import tempfile
import unittest

from campustrack.exceptions import DataFileError, DuplicateStudentError
from campustrack.models import Student, ExerciseRecord, SleepPattern, Survey
from campustrack.repository import InMemoryStudentRepository, CsvStudentRepository


class TestInMemoryStudentRepository(unittest.TestCase):

    def setUp(self):
        self.repo = InMemoryStudentRepository()
        self.student = Student("S001", "Amina", 21, "BIT", "Information Technology")

    def test_add_and_get(self):
        self.repo.add(self.student)
        self.assertEqual(self.repo.get("S001"), self.student)

    def test_duplicate_add_rejected(self):
        self.repo.add(self.student)
        with self.assertRaises(DuplicateStudentError):
            self.repo.add(Student("S001", "Someone Else", 22, "BBus", "Business"))

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.repo.get("NOPE"))

    def test_exists(self):
        self.repo.add(self.student)
        self.assertTrue(self.repo.exists("s001"))  # case-insensitive lookup
        self.assertFalse(self.repo.exists("S999"))

    def test_count_and_all(self):
        self.repo.add(self.student)
        self.assertEqual(self.repo.count(), 1)
        self.assertEqual(self.repo.all(), [self.student])


class TestCsvStudentRepository(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_first_run_creates_empty_files(self):
        repo = CsvStudentRepository(self.tmp_dir)
        self.assertEqual(repo.count(), 0)
        self.assertTrue(os.path.exists(repo.students_path))

    def test_corrupted_exercise_record_raises_data_file_error(self):
        repo = CsvStudentRepository(self.tmp_dir)

        repo.add(
            Student(
                "S001",
                "Amina",
                21,
                "BIT",
                "Information Technology",
            )
        )

        with open(repo.exercise_path, "w") as f:
            f.write(
                "student_id,days_per_week,exercise_type,"
                "duration,day,time_of_day\n"
            )
            f.write(
                "S001,invalid,running,30,monday,07:00\n"
            )

        with self.assertRaises(DataFileError):
            CsvStudentRepository(self.tmp_dir)

    def test_corrupted_sleep_record_raises_data_file_error(self):
        repo = CsvStudentRepository(self.tmp_dir)

        repo.add(
            Student(
                "S001",
                "Amina",
                21,
                "BIT",
                "Information Technology",
            )
        )

        with open(repo.sleep_path, "w") as f:
            f.write(
                "student_id,had_good_sleep,start,end\n"
            )
            f.write(
                "S001,true,invalid-time,06:00\n"
            )

        with self.assertRaises(DataFileError):
            CsvStudentRepository(self.tmp_dir)

    def test_corrupted_survey_raises_data_file_error(self):
        repo = CsvStudentRepository(self.tmp_dir)

        repo.add(
            Student(
                "S001",
                "Amina",
                21,
                "BIT",
                "Information Technology",
            )
        )

        with open(repo.surveys_path, "w") as f:
            f.write(
                "student_id,entry_date,stress_level,mood_rating,"
                "wellbeing_answers,notes\n"
            )
            f.write(
                "S001,2026-08-06,invalid,8,4;4;4;4;4,Test\n"
            )

        with self.assertRaises(DataFileError):
            CsvStudentRepository(self.tmp_dir)
            
    def test_exercise_record_for_unknown_student_raises_data_file_error(self):
        repo = CsvStudentRepository(self.tmp_dir)

        with open(repo.exercise_path, "w") as f:
            f.write(
                "student_id,days_per_week,exercise_type,"
                "duration,day,time_of_day\n"
            )
            f.write(
                "S999,3,running,30,monday,07:00\n"
            )

        with self.assertRaises(DataFileError):
            CsvStudentRepository(self.tmp_dir)

    def test_sleep_record_for_unknown_student_raises_data_file_error(self):
        repo = CsvStudentRepository(self.tmp_dir)

        with open(repo.sleep_path, "w") as f:
            f.write(
                "student_id,had_good_sleep,start,end\n"
            )
            f.write(
                "S999,true,23:00,06:00\n"
            )

        with self.assertRaises(DataFileError):
            CsvStudentRepository(self.tmp_dir)

    def test_survey_for_unknown_student_raises_data_file_error(self):
        repo = CsvStudentRepository(self.tmp_dir)

        with open(repo.surveys_path, "w") as f:
            f.write(
                "student_id,entry_date,stress_level,mood_rating,"
                "wellbeing_answers,notes\n"
            )
            f.write(
                "S999,2026-08-06,3,8,4;4;4;4;4,Test\n"
            )

        with self.assertRaises(DataFileError):
            CsvStudentRepository(self.tmp_dir)

    def test_add_persists_to_disk(self):
        repo = CsvStudentRepository(self.tmp_dir)
        repo.add(Student("S001", "Amina", 21, "BIT", "Information Technology"))
        self.assertTrue(os.path.exists(repo.students_path))
        with open(repo.students_path) as f:
            content = f.read()
        self.assertIn("S001", content)

    def test_duplicate_add_rejected(self):
        repo = CsvStudentRepository(self.tmp_dir)
        repo.add(Student("S001", "Amina", 21, "BIT", "Information Technology"))
        with self.assertRaises(DuplicateStudentError):
            repo.add(Student("S001", "Duplicate", 22, "BBus", "Business"))

    def test_full_roundtrip_including_records(self):
        repo = CsvStudentRepository(self.tmp_dir)
        student = Student("S001", "Amina", 21, "BIT", "Information Technology")
        student.add_exercise_record(ExerciseRecord(3, "running", 30, "monday", "07:00"))
        student.add_sleep_record(SleepPattern(True, "23:00", "06:00"))
        student.add_survey(Survey("2026-08-06", 3, 8, [4, 4, 4, 4, 4], "Feeling good"))
        repo.add(student)
        repo.persist()  # explicit persist too, should be idempotent

        # Reload from disk into a brand new repository instance - this is
        # the real test: does everything survive a full close/reopen cycle.
        reloaded = CsvStudentRepository(self.tmp_dir)
        reloaded_student = reloaded.get("S001")

        self.assertIsNotNone(reloaded_student)
        self.assertEqual(reloaded_student.name, "Amina")
        self.assertEqual(len(reloaded_student.exercise_records), 1)
        self.assertEqual(len(reloaded_student.sleep_records), 1)
        self.assertEqual(len(reloaded_student.surveys), 1)
        self.assertEqual(reloaded_student.sleep_records[0].hours_slept, 7.0)
        self.assertEqual(reloaded_student.surveys[0].notes, "Feeling good")

    def test_corrupted_students_file_raises_data_file_error(self):
        os.makedirs(self.tmp_dir, exist_ok=True)
        bad_path = os.path.join(self.tmp_dir, "students.csv")
        with open(bad_path, "w") as f:
            f.write("student_id,name\nS001")  # missing required columns

        with self.assertRaises(DataFileError):
            CsvStudentRepository(self.tmp_dir)

    def test_missing_directory_is_created(self):
        nested = os.path.join(self.tmp_dir, "nested", "data")
        repo = CsvStudentRepository(nested)
        self.assertTrue(os.path.isdir(nested))
        self.assertEqual(repo.count(), 0)


if __name__ == "__main__":
    unittest.main()
