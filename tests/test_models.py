import unittest

from campustrack.exceptions import ValidationError
from campustrack.models import Student, ExerciseRecord, SleepPattern, Survey


class TestStudentValidation(unittest.TestCase):

    def test_valid_student_created(self):
        s = Student("s001", "Amina Yusuf", 21, "BIT", "Information Technology")
        self.assertEqual(s.student_id, "S001")  # normalized to uppercase
        self.assertEqual(s.name, "Amina Yusuf")

    def test_empty_name_rejected(self):
        with self.assertRaises(ValidationError):
            Student("S001", "  ", 21, "BIT", "Information Technology")

    def test_empty_faculty_rejected(self):
        with self.assertRaises(ValidationError):
            Student("S001", "Amina", 21, "BIT", "")

    def test_age_out_of_range_rejected(self):
        with self.assertRaises(ValidationError):
            Student("S001", "Amina", 200, "BIT", "Information Technology")

    def test_age_non_numeric_rejected(self):
        with self.assertRaises(ValidationError):
            Student("S001", "Amina", "twenty", "BIT", "Information Technology")

    def test_role_label_includes_course_and_faculty(self):
        s = Student("S001", "Amina", 21, "BIT", "Information Technology")
        self.assertIn("BIT", s.role_label())
        self.assertIn("Information Technology", s.role_label())


class TestStudentRecords(unittest.TestCase):

    def setUp(self):
        self.student = Student("S001", "Amina", 21, "BIT", "Information Technology")

    def test_add_exercise_record(self):
        self.student.add_exercise_record(ExerciseRecord(3, "running", 30, "monday", "07:00"))
        self.assertEqual(len(self.student.exercise_records), 1)

    def test_add_wrong_type_rejected(self):
        with self.assertRaises(ValidationError):
            self.student.add_exercise_record(SleepPattern(True, "23:00", "06:00"))

    def test_average_sleep_hours_none_when_no_records(self):
        self.assertIsNone(self.student.average_sleep_hours())

    def test_average_sleep_hours_computed_correctly(self):
        self.student.add_sleep_record(SleepPattern(True, "23:00", "07:00"))  # 8h
        self.student.add_sleep_record(SleepPattern(False, "01:00", "05:00"))  # 4h
        self.assertEqual(self.student.average_sleep_hours(), 6.0)

    def test_has_concerns_false_when_all_healthy(self):
        self.student.add_sleep_record(SleepPattern(True, "22:00", "07:00"))  # 9h, fine
        self.assertFalse(self.student.has_concerns())

    def test_has_concerns_true_when_flagged(self):
        self.student.add_sleep_record(SleepPattern(False, "02:00", "05:00"))  # 3h, concern
        self.assertTrue(self.student.has_concerns())

    def test_concern_summaries_only_includes_flagged(self):
        self.student.add_sleep_record(SleepPattern(True, "22:00", "07:00"))    # fine
        self.student.add_sleep_record(SleepPattern(False, "02:00", "05:00"))   # concern
        self.assertEqual(len(self.student.concern_summaries()), 1)

    def test_to_dict_roundtrip_fields(self):
        d = self.student.to_dict()
        self.assertEqual(d["student_id"], "S001")
        self.assertEqual(d["faculty"], "Information Technology")


class TestExerciseRecord(unittest.TestCase):

    def test_valid_record(self):
        r = ExerciseRecord(3, "running", 30, "monday", "07:00")
        self.assertEqual(r.exercise_type, "running")

    def test_days_per_week_out_of_range_rejected(self):
        with self.assertRaises(ValidationError):
            ExerciseRecord(9, "running", 30, "monday", "07:00")

    def test_bad_time_format_rejected(self):
        with self.assertRaises(ValidationError):
            ExerciseRecord(3, "running", 30, "monday", "7:00pm")

    def test_short_session_is_a_concern(self):
        r = ExerciseRecord(1, "walking", 5, "monday", "07:00")
        self.assertTrue(r.is_concern())

    def test_normal_session_not_a_concern(self):
        r = ExerciseRecord(3, "running", 30, "monday", "07:00")
        self.assertFalse(r.is_concern())


class TestSleepPattern(unittest.TestCase):

    def test_hours_slept_same_day(self):
        r = SleepPattern(True, "23:00", "23:30")
        self.assertEqual(r.hours_slept, 0.5)

    def test_hours_slept_crossing_midnight(self):
        r = SleepPattern(True, "23:00", "06:00")
        self.assertEqual(r.hours_slept, 7.0)

    def test_below_benchmark_is_concern(self):
        r = SleepPattern(False, "02:00", "05:00")
        self.assertTrue(r.is_concern())

    def test_bad_time_format_rejected(self):
        with self.assertRaises(ValidationError):
            SleepPattern(True, "eleven pm", "06:00")


class TestSurvey(unittest.TestCase):

    def test_valid_survey(self):
        s = Survey("2026-08-06", 3, 8, [4, 4, 4, 4, 4], "All good")
        self.assertEqual(s.wellbeing_average, 4.0)

    def test_bad_date_format_rejected(self):
        with self.assertRaises(ValidationError):
            Survey("06/08/2026", 3, 8, [4, 4, 4, 4, 4])

    def test_stress_out_of_range_rejected(self):
        with self.assertRaises(ValidationError):
            Survey("2026-08-06", 15, 8, [4, 4, 4, 4, 4])

    def test_wellbeing_answer_out_of_range_rejected(self):
        with self.assertRaises(ValidationError):
            Survey("2026-08-06", 3, 8, [4, 4, 9, 4, 4])

    def test_high_stress_is_concern(self):
        s = Survey("2026-08-06", 9, 8, [4, 4, 4, 4, 4])
        self.assertTrue(s.is_concern())

    def test_low_mood_is_concern(self):
        s = Survey("2026-08-06", 3, 2, [4, 4, 4, 4, 4])
        self.assertTrue(s.is_concern())

    def test_healthy_survey_not_a_concern(self):
        s = Survey("2026-08-06", 3, 8, [4, 4, 4, 4, 4])
        self.assertFalse(s.is_concern())


if __name__ == "__main__":
    unittest.main()
