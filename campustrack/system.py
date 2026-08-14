"""
WellnessSystem is the "manager" class - the only thing that talks to
the repository. It manages add/update operations and owns every
report. cli.py and analytics.py both go through this class rather than
touching the repository or the models directly, so business rules
(what counts as "needs intervention," how faculties are filtered) live
in exactly one place.
"""

from campustrack.exceptions import StudentNotFoundError
from campustrack.repository import InMemoryStudentRepository


class WellnessSystem:

    def __init__(self, repository=None):
        self.repository = repository if repository is not None else InMemoryStudentRepository()

    # student management
    def add_student(self, student):
        self.repository.add(student)

    def get_student(self, student_id):
        student = self.repository.get(student_id)
        if student is None:
            raise StudentNotFoundError(student_id)
        return student

    def student_exists(self, student_id):
        return self.repository.exists(student_id)

    def all_students(self):
        return self.repository.all()

    def student_count(self):
        return self.repository.count()

    # adding records to an existing student
    def add_exercise_record(self, student_id, record):
        student = self.get_student(student_id)
        student.add_exercise_record(record)
        self.repository.persist()

    def add_sleep_record(self, student_id, record):
        student = self.get_student(student_id)
        student.add_sleep_record(record)
        self.repository.persist()

    def add_survey(self, student_id, survey):
        student = self.get_student(student_id)
        student.add_survey(survey)
        self.repository.persist()

    # faculty scoping
    def students_by_faculty(self, faculty):
        faculty = faculty.strip().lower()
        return [s for s in self.all_students() if s.faculty.lower() == faculty]

    def faculty_counts(self):
        counts = {}
        for s in self.all_students():
            counts[s.faculty] = counts.get(s.faculty, 0) + 1
        return counts

    def known_faculties(self):
        return sorted({s.faculty for s in self.all_students()})

    # reports
    def exercise_count_report(self):
        """{student_id: number of exercise records}"""
        return {s.student_id: len(s.exercise_records) for s in self.all_students()}

    def average_sleep_report(self):
        """{student_id: average hours slept}, students with no sleep data omitted."""
        report = {}
        for s in self.all_students():
            avg = s.average_sleep_hours()
            if avg is not None:
                report[s.student_id] = avg
        return report

    def students_needing_intervention(self):
        """Students with at least one record (exercise/sleep/survey)
        flagged as a concern."""
        return [s for s in self.all_students() if s.has_concerns()]

    def exercise_sessions_on_day(self, day):
        """All exercise records across all students on a given day of week."""
        day = day.strip().lower()
        sessions = []
        for s in self.all_students():
            for record in s.exercise_records:
                if record.day == day:
                    sessions.append((s, record))
        return sessions

    def survey_summary_report(self):
        """{student_id: [survey summary lines]}"""
        return {s.student_id: [sv.summary_line() for sv in s.surveys]
                for s in self.all_students() if s.surveys}

    def all_concerns_report(self):
        """{student_id: [concern summary lines]} - polymorphic across
        exercise/sleep/survey via WellnessRecord.is_concern()/summary_line()."""
        report = {}
        for s in self.all_students():
            concerns = s.concern_summaries()
            if concerns:
                report[s.student_id] = concerns
        return report
