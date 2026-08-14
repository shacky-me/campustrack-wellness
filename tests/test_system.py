import unittest

from campustrack.exceptions import StudentNotFoundError, DuplicateStudentError
from campustrack.models import Student, ExerciseRecord, SleepPattern, Survey
from campustrack.repository import InMemoryStudentRepository
from campustrack.system import WellnessSystem


class TestWellnessSystemStudentManagement(unittest.TestCase):

    def setUp(self):
        self.system = WellnessSystem(repository=InMemoryStudentRepository())

    def test_add_and_get_student(self):
        self.system.add_student(Student("S001", "Amina", 21, "BIT", "Information Technology"))
        self.assertEqual(self.system.get_student("S001").name, "Amina")

    def test_get_missing_student_raises(self):
        with self.assertRaises(StudentNotFoundError):
            self.system.get_student("NOPE")

    def test_duplicate_student_raises(self):
        self.system.add_student(Student("S001", "Amina", 21, "BIT", "Information Technology"))
        with self.assertRaises(DuplicateStudentError):
            self.system.add_student(Student("S001", "Someone", 22, "BBus", "Business"))

    def test_student_exists(self):
        self.system.add_student(Student("S001", "Amina", 21, "BIT", "Information Technology"))
        self.assertTrue(self.system.student_exists("S001"))
        self.assertFalse(self.system.student_exists("S999"))


class TestWellnessSystemRecords(unittest.TestCase):

    def setUp(self):
        self.system = WellnessSystem(repository=InMemoryStudentRepository())
        self.system.add_student(Student("S001", "Amina", 21, "BIT", "Information Technology"))

    def test_add_exercise_record_via_system(self):
        self.system.add_exercise_record("S001", ExerciseRecord(3, "running", 30, "monday", "07:00"))
        self.assertEqual(len(self.system.get_student("S001").exercise_records), 1)

    def test_add_record_to_missing_student_raises(self):
        with self.assertRaises(StudentNotFoundError):
            self.system.add_exercise_record("S999", ExerciseRecord(3, "running", 30, "monday", "07:00"))


class TestWellnessSystemFaculty(unittest.TestCase):

    def setUp(self):
        self.system = WellnessSystem(repository=InMemoryStudentRepository())
        self.system.add_student(Student("S001", "Amina", 21, "BIT", "Information Technology"))
        self.system.add_student(Student("S002", "Ben", 22, "BBus", "Business"))
        self.system.add_student(Student("S003", "Cleo", 23, "BSc IT", "Information Technology"))

    def test_students_by_faculty(self):
        it_students = self.system.students_by_faculty("Information Technology")
        self.assertEqual(len(it_students), 2)

    def test_students_by_faculty_case_insensitive(self):
        it_students = self.system.students_by_faculty("information technology")
        self.assertEqual(len(it_students), 2)

    def test_faculty_counts(self):
        counts = self.system.faculty_counts()
        self.assertEqual(counts["Information Technology"], 2)
        self.assertEqual(counts["Business"], 1)

    def test_known_faculties_sorted_unique(self):
        self.assertEqual(self.system.known_faculties(), ["Business", "Information Technology"])


class TestWellnessSystemReports(unittest.TestCase):

    def setUp(self):
        self.system = WellnessSystem(repository=InMemoryStudentRepository())
        self.system.add_student(Student("S001", "Amina", 21, "BIT", "Information Technology"))
        self.system.add_exercise_record("S001", ExerciseRecord(3, "running", 30, "monday", "07:00"))
        self.system.add_exercise_record("S001", ExerciseRecord(1, "walking", 5, "tuesday", "08:00"))
        self.system.add_sleep_record("S001", SleepPattern(True, "23:00", "06:00"))
        self.system.add_survey("S001", Survey("2026-08-06", 8, 2, [1, 1, 2, 1, 2], "Struggling"))

    def test_exercise_count_report(self):
        self.assertEqual(self.system.exercise_count_report()["S001"], 2)

    def test_average_sleep_report(self):
        self.assertEqual(self.system.average_sleep_report()["S001"], 7.0)

    def test_average_sleep_report_omits_students_without_data(self):
        self.system.add_student(Student("S002", "Ben", 22, "BBus", "Business"))
        report = self.system.average_sleep_report()
        self.assertNotIn("S002", report)

    def test_students_needing_intervention_flags_this_student(self):
        flagged = self.system.students_needing_intervention()
        self.assertEqual(len(flagged), 1)
        self.assertEqual(flagged[0].student_id, "S001")

    def test_exercise_sessions_on_day(self):
        sessions = self.system.exercise_sessions_on_day("monday")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0][1].exercise_type, "running")

    def test_exercise_sessions_on_day_no_matches(self):
        self.assertEqual(self.system.exercise_sessions_on_day("sunday"), [])

    def test_survey_summary_report(self):
        report = self.system.survey_summary_report()
        self.assertEqual(len(report["S001"]), 1)

    def test_all_concerns_report_includes_short_session_and_survey(self):
        report = self.system.all_concerns_report()
        # short walking session (5 min) + low mood survey should both flag
        self.assertGreaterEqual(len(report["S001"]), 2)


if __name__ == "__main__":
    unittest.main()
