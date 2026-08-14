import os
import shutil
import tempfile
import unittest

from campustrack.analytics import (
    students_dataframe, exercise_dataframe, faculty_summary_table,
    chart_average_sleep_bar, chart_exercise_minutes_by_day,
    chart_intervention_pie, chart_faculty_headcount, chart_dashboard,
    generate_all_charts,
)
from campustrack.models import Student, ExerciseRecord, SleepPattern, Survey
from campustrack.repository import InMemoryStudentRepository
from campustrack.system import WellnessSystem


def make_populated_system():
    system = WellnessSystem(repository=InMemoryStudentRepository())
    s1 = Student("S001", "Amina", 21, "BIT", "Information Technology")
    s1.add_exercise_record(ExerciseRecord(3, "running", 30, "monday", "07:00"))
    s1.add_sleep_record(SleepPattern(True, "22:00", "07:00"))  # 9h - healthy, not a concern
    s1.add_survey(Survey("2026-08-06", 3, 8, [4, 4, 4, 4, 4], "Good"))
    system.add_student(s1)

    s2 = Student("S002", "Ben", 22, "BBus", "Business")
    s2.add_exercise_record(ExerciseRecord(1, "walking", 5, "wednesday", "12:00"))
    s2.add_sleep_record(SleepPattern(False, "02:00", "05:00"))
    s2.add_survey(Survey("2026-08-07", 8, 2, [1, 1, 2, 1, 2], "Struggling"))
    system.add_student(s2)

    return system


class TestDataFrames(unittest.TestCase):

    def setUp(self):
        self.system = make_populated_system()

    def test_students_dataframe_row_count(self):
        df = students_dataframe(self.system)
        self.assertEqual(len(df), 2)

    def test_students_dataframe_columns(self):
        df = students_dataframe(self.system)
        expected = {"student_id", "name", "age", "course", "faculty",
                    "avg_sleep_hours", "exercise_sessions", "survey_count", "flagged"}
        self.assertEqual(set(df.columns), expected)

    def test_students_dataframe_flags_correct_student(self):
        df = students_dataframe(self.system)
        ben_row = df[df["student_id"] == "S002"].iloc[0]
        self.assertTrue(ben_row["flagged"])
        amina_row = df[df["student_id"] == "S001"].iloc[0]
        self.assertFalse(amina_row["flagged"])

    def test_students_dataframe_empty_system(self):
        empty_system = WellnessSystem(repository=InMemoryStudentRepository())
        df = students_dataframe(empty_system)
        self.assertTrue(df.empty)

    def test_exercise_dataframe_row_count(self):
        df = exercise_dataframe(self.system)
        self.assertEqual(len(df), 2)

    def test_faculty_summary_table_headcounts(self):
        table = faculty_summary_table(self.system)
        it_row = table[table["faculty"] == "Information Technology"].iloc[0]
        self.assertEqual(it_row["headcount"], 1)

    def test_faculty_summary_table_empty_system(self):
        empty_system = WellnessSystem(repository=InMemoryStudentRepository())
        table = faculty_summary_table(empty_system)
        self.assertTrue(table.empty)


class TestCharts(unittest.TestCase):

    def setUp(self):
        self.system = make_populated_system()
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_average_sleep_chart_creates_file(self):
        path = chart_average_sleep_bar(self.system, self.tmp_dir)
        self.assertTrue(os.path.exists(path))

    def test_average_sleep_chart_none_when_no_data(self):
        empty_system = WellnessSystem(repository=InMemoryStudentRepository())
        path = chart_average_sleep_bar(empty_system, self.tmp_dir)
        self.assertIsNone(path)

    def test_exercise_by_day_chart_creates_file(self):
        path = chart_exercise_minutes_by_day(self.system, self.tmp_dir)
        self.assertTrue(os.path.exists(path))

    def test_intervention_pie_creates_file(self):
        path = chart_intervention_pie(self.system, self.tmp_dir)
        self.assertTrue(os.path.exists(path))

    def test_intervention_pie_none_when_no_students(self):
        empty_system = WellnessSystem(repository=InMemoryStudentRepository())
        path = chart_intervention_pie(empty_system, self.tmp_dir)
        self.assertIsNone(path)

    def test_faculty_headcount_chart_creates_file(self):
        path = chart_faculty_headcount(self.system, self.tmp_dir)
        self.assertTrue(os.path.exists(path))

    def test_dashboard_creates_file(self):
        path = chart_dashboard(self.system, self.tmp_dir)
        self.assertTrue(os.path.exists(path))

    def test_dashboard_none_when_empty_system(self):
        empty_system = WellnessSystem(repository=InMemoryStudentRepository())
        path = chart_dashboard(empty_system, self.tmp_dir)
        self.assertIsNone(path)

    def test_generate_all_charts_returns_all_five_labels(self):
        results = generate_all_charts(self.system, self.tmp_dir)
        self.assertEqual(len(results), 5)
        self.assertTrue(all(os.path.exists(p) for p in results.values() if p))

    def test_charts_directory_auto_created(self):
        nested = os.path.join(self.tmp_dir, "nested", "charts")
        generate_all_charts(self.system, nested)
        self.assertTrue(os.path.isdir(nested))


if __name__ == "__main__":
    unittest.main()
