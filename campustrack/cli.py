"""
This is the only file in the whole codebase that calls input() or
print(). Every menu handler is "exception-safe" - it catches
CampusTrackError (and its subclasses from exceptions.py) at the point
of use and prints a friendly message instead of letting the program
crash. system.py and analytics.py don't know a console exists; this
file is the entire console-facing layer.
"""

import os

from campustrack.analytics import (
    generate_all_charts, students_dataframe, faculty_summary_table,
)
from campustrack.exceptions import CampusTrackError, ValidationError
from campustrack.models import Student, ExerciseRecord, SleepPattern, Survey
from campustrack.repository import CsvStudentRepository
from campustrack.system import WellnessSystem

SEP = "-" * 60
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHARTS_DIR = os.path.join(BASE_DIR, "charts")

FACULTIES = [
    "Business",
    "Engineering",
    "Health Sciences",
    "Information Technology",
    "Arts & Design",
]


# Input helpers - every one of these loops until it gets a valid value,
# so handlers below never need their own retry logic.

def get_nonempty_string(prompt):
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("  ! This field cannot be empty.")


def get_int_in_range(prompt, low, high):
    while True:
        raw = input(prompt).strip()
        if raw.lstrip("-").isdigit() and low <= int(raw) <= high:
            return int(raw)
        print(f"  ! Enter a whole number between {low} and {high}.")


def get_time_hhmm(prompt):
    while True:
        raw = input(prompt).strip()
        parts = raw.split(":")
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            h, m = int(parts[0]), int(parts[1])
            if 0 <= h <= 23 and 0 <= m <= 59:
                return f"{h:02d}:{m:02d}"
        print("  ! Enter a time as HH:MM in 24-hour format, e.g. 07:30.")


def get_date_yyyy_mm_dd(prompt):
    while True:
        raw = input(prompt).strip()
        parts = raw.split("-")
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            return raw
        print("  ! Enter a date as YYYY-MM-DD, e.g. 2026-08-10.")


def get_yes_no(prompt):
    while True:
        raw = input(prompt).strip().lower()
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  ! Enter yes or no.")


def get_faculty(prompt="  Choose a faculty (number): "):
    print("  Faculties:")
    for i, fac in enumerate(FACULTIES, start=1):
        print(f"    {i}. {fac}")
    while True:
        raw = input(prompt).strip()
        if raw.isdigit() and 1 <= int(raw) <= len(FACULTIES):
            return FACULTIES[int(raw) - 1]
        print(f"  ! Enter a number between 1 and {len(FACULTIES)}.")


def resolve_student(system):
    """Prompt for a student ID and return the Student, or None (with a
    friendly message already printed) if it doesn't exist."""
    student_id = get_nonempty_string("  Enter Student ID: ")
    try:
        return system.get_student(student_id)
    except CampusTrackError as exc:
        print(f"  ! {exc}")
        return None


def pause():
    input("\n  Press ENTER to continue...")

# Menu handlers

def handle_add_student(system):
    print("\n" + SEP)
    print("  ADD NEW STUDENT")
    print(SEP)
    student_id = get_nonempty_string("  Enter Student ID   : ")
    name = get_nonempty_string("  Enter Full Name    : ")
    age = get_int_in_range("  Enter Age          : ", 1, 120)
    course = get_nonempty_string("  Enter Course Name  : ")
    faculty = get_faculty("  Enter Faculty (number): ")

    try:
        system.add_student(Student(student_id, name, age, course, faculty))
    except (CampusTrackError, ValidationError) as exc:
        print(f"  ! Could not add student: {exc}")
        return
    print(f"\n  Student {name} ({student_id.upper()}) added successfully.")


def handle_add_exercise(system):
    student = resolve_student(system)
    if student is None:
        return
    print("\n" + SEP)
    print(f"  ADD EXERCISE RECORD - {student.name}")
    print(SEP)
    try:
        days = get_int_in_range("  Days per week (1-7): ", 1, 7)
        ex_type = get_nonempty_string("  Exercise type      : ")
        duration = get_int_in_range("  Duration (minutes) : ", 1, 1440)
        day = get_nonempty_string("  Day of week        : ")
        time_of_day = get_time_hhmm("  Time of day (HH:MM): ")
        record = ExerciseRecord(days, ex_type, duration, day, time_of_day)
        system.add_exercise_record(student.student_id, record)
    except (CampusTrackError, ValidationError) as exc:
        print(f"  ! Could not add exercise record: {exc}")
        return
    print(f"\n  Exercise record added for {student.name}.")


def handle_add_sleep(system):
    student = resolve_student(system)
    if student is None:
        return
    print("\n" + SEP)
    print(f"  ADD SLEEP PATTERN - {student.name}")
    print(SEP)
    try:
        had_good_sleep = get_yes_no("  Did you have a good sleep? (yes/no): ")
        start = get_time_hhmm("  Sleep start (HH:MM, 24hr): ")
        end = get_time_hhmm("  Wake-up time (HH:MM, 24hr): ")
        record = SleepPattern(had_good_sleep, start, end)
        system.add_sleep_record(student.student_id, record)
    except (CampusTrackError, ValidationError) as exc:
        print(f"  ! Could not add sleep record: {exc}")
        return
    print(f"\n  Sleep hours recorded: {record.hours_slept} hrs")


def handle_add_survey(system):
    student = resolve_student(system)
    if student is None:
        return
    print("\n" + SEP)
    print(f"  COMPLETE WELLNESS SURVEY - {student.name}")
    print(SEP)
    try:
        entry_date = get_date_yyyy_mm_dd("  Date (YYYY-MM-DD)  : ")
        stress = get_int_in_range("  Stress level (1-10): ", 1, 10)
        mood = get_int_in_range("  Mood rating (1-10) : ", 1, 10)
        print("  Rate the following 1 (poor) - 5 (great):")
        answers = [
            get_int_in_range("    Energy levels      : ", 1, 5),
            get_int_in_range("    Focus/concentration: ", 1, 5),
            get_int_in_range("    Social connection  : ", 1, 5),
            get_int_in_range("    Physical health    : ", 1, 5),
            get_int_in_range("    Overall wellbeing  : ", 1, 5),
        ]
        notes = input("  Notes (optional)   : ").strip()
        survey = Survey(entry_date, stress, mood, answers, notes)
        system.add_survey(student.student_id, survey)
    except (CampusTrackError, ValidationError) as exc:
        print(f"  ! Could not save survey: {exc}")
        return
    print(f"\n  Survey saved for {student.name}. Wellbeing average: {survey.wellbeing_average}/5")


def handle_display_exercise(system):
    student = resolve_student(system)
    if student is None:
        return
    print(f"\n  -- Exercise records for {student.name} --")
    if not student.exercise_records:
        print("    No exercise records yet.")
    for r in student.exercise_records:
        print(f"    {r.summary_line()}")


def handle_display_sleep(system):
    student = resolve_student(system)
    if student is None:
        return
    print(f"\n  -- Sleep records for {student.name} --")
    if not student.sleep_records:
        print("    No sleep records yet.")
    for r in student.sleep_records:
        print(f"    {r.summary_line()}")


def handle_display_surveys(system):
    student = resolve_student(system)
    if student is None:
        return
    print(f"\n  -- Wellness surveys for {student.name} --")
    if not student.surveys:
        print("    No surveys yet.")
    for s in student.surveys:
        print(f"    {s.summary_line()}")


def handle_display_all(system):
    print("\n" + SEP)
    print("  ALL STUDENTS")
    print(SEP)
    if system.student_count() == 0:
        print("  No students registered yet.")
        return
    print("  {:<8} {:<20} {:<5} {:<22} {:<20} {}".format(
        "ID", "Name", "Age", "Course", "Faculty", "Avg Sleep"
    ))
    print("  " + "-" * 90)
    for student in system.all_students():
        print(student.as_row())

    print("\n  Students per faculty:")
    for faculty, count in system.faculty_counts().items():
        print(f"    {faculty}: {count}")

# Reports submenu

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
              7. Filter students by faculty
              8. Faculty summary table (pandas)
              9. Generate charts + dashboard (saved to /charts)
              0. Back to main menu
        """)
        sub_choice = input("  Enter your choice: ").strip()

        if sub_choice == "1":
            print("\n  -- Exercise records per student --")
            report = system.exercise_count_report()
            if not report:
                print("    No students registered yet.")
            for student_id, count in report.items():
                print(f"    {student_id}: {count} record(s)")

        elif sub_choice == "2":
            print("\n  -- Average sleep per student --")
            report = system.average_sleep_report()
            if not report:
                print("    No sleep data recorded yet.")
            for student_id, avg in report.items():
                print(f"    {student_id}: {avg} hrs")

        elif sub_choice == "3":
            print("\n  -- Students needing wellness intervention --")
            flagged = system.students_needing_intervention()
            if not flagged:
                print("    No students currently flagged.")
            for student in flagged:
                print(f"\n    {student.name} ({student.student_id}):")
                for line in student.concern_summaries():
                    print(f"      - {line}")

        elif sub_choice == "4":
            day = get_nonempty_string("  Enter day of week: ")
            sessions = system.exercise_sessions_on_day(day)
            print(f"\n  -- Exercise sessions on {day.title()} --")
            if not sessions:
                print("    No sessions recorded for that day.")
            for student, record in sessions:
                print(f"    {student.name}: {record.summary_line()}")

        elif sub_choice == "5":
            print("\n  -- Wellness survey summary per student --")
            report = system.survey_summary_report()
            if not report:
                print("    No surveys recorded yet.")
            for student_id, lines in report.items():
                print(f"\n    {student_id}:")
                for line in lines:
                    print(f"      - {line}")

        elif sub_choice == "6":
            print("\n  -- All wellness concerns --")
            report = system.all_concerns_report()
            if not report:
                print("    No concerns flagged for any student.")
            for student_id, lines in report.items():
                print(f"\n    {student_id}:")
                for line in lines:
                    print(f"      - {line}")

        elif sub_choice == "7":
            faculty = get_faculty()
            matches = system.students_by_faculty(faculty)
            print(f"\n  -- Students in {faculty} --")
            if not matches:
                print("    None found.")
            for student in matches:
                sleep = student.average_sleep_hours()
                sleep_label = f"{sleep} hrs" if sleep is not None else "no sleep data"
                print(f"    {student.name} ({student.student_id}, {student.course}): {sleep_label}")

        elif sub_choice == "8":
            print("\n  -- Faculty summary (pandas) --")
            table = faculty_summary_table(system)
            if table.empty:
                print("    No students registered yet.")
            else:
                print(table.to_string(index=False))

        elif sub_choice == "9":
            if system.student_count() == 0:
                print("  No students registered yet - nothing to chart.")
            else:
                print("\n  Generating charts...")
                results = generate_all_charts(system, CHARTS_DIR)
                for label, path in results.items():
                    if path:
                        print(f"    {label}: saved to {path}")
                    else:
                        print(f"    {label}: skipped (not enough data yet)")

        elif sub_choice == "0":
            viewing_reports = False
            continue

        else:
            print("  ! Invalid choice.")

        pause()


# --------------------------------------------------------------------------- #
# Main program loop
# --------------------------------------------------------------------------- #
def main():
    system = WellnessSystem(repository=CsvStudentRepository(DATA_DIR))

    print("\n  Welcome to CampusTrack - Fitness & Wellness Monitoring System")
    print(f"  Loaded {system.student_count()} student(s) from {DATA_DIR}")

    running = True
    while running:
        print("\n" + SEP)
        print("  MAIN MENU")
        print(SEP)
        print("""
              1. Add new student
              2. Add exercise record
              3. Add sleep pattern
              4. Complete wellness survey
              5. Display exercise records for a student
              6. Display sleep records for a student
              7. Display survey history for a student
              8. Display all students
              9. Reports & analytics
              0. Exit
        """)
        choice = input("  Enter your choice: ").strip()

        try:
            if choice == "1":
                handle_add_student(system)
            elif choice == "2":
                handle_add_exercise(system)
            elif choice == "3":
                handle_add_sleep(system)
            elif choice == "4":
                handle_add_survey(system)
            elif choice == "5":
                handle_display_exercise(system)
            elif choice == "6":
                handle_display_sleep(system)
            elif choice == "7":
                handle_display_surveys(system)
            elif choice == "8":
                handle_display_all(system)
            elif choice == "9":
                handle_reports(system)
            elif choice == "0":
                print("\n  Thanks for using CampusTrack. Goodbye!")
                running = False
                continue
            else:
                print("  ! Invalid choice.")
        except CampusTrackError as exc:
            # Last-resort safety net - every handler above already
            # catches its own expected errors, so reaching this means
            # something unexpected slipped through. Better a friendly
            # message than a stack trace on a student's console.
            print(f"  ! Something went wrong: {exc}")

        if choice != "0":
            pause()


if __name__ == "__main__":
    main()
