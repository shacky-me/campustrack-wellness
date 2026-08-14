"""
Two jobs:
  1. I need to turn the live WellnessSystem state into pandas DataFrames for
     tabular summaries (used by the CLI's text reports and available
     for anyone who wants to inspect the data directly).
  2. I'm also required to generate matplotlib charts from those DataFrames, always saved to
     a PNG file - never plt.show(). The assignment brief explicitly
     bans GUI frameworks and requires console-only interaction, so
     every chart function here uses the non-interactive "Agg" backend
     and writes straight to disk. The CLI just tells the user where the
     file landed.

Nothing in this module calls input() or print() for interactive
prompts - it only returns data and file paths. cli.py decides what to
show the user and how.
"""

import os

import matplotlib
matplotlib.use("Agg")  # non-interactive backend - guarantees no GUI window ever opens
import matplotlib.pyplot as plt
import pandas as pd

# DataFrames

def students_dataframe(system):
    """One row per student: id, name, course, faculty, age, average
    sleep, exercise session count, and whether they're flagged."""
    rows = []
    for s in system.all_students():
        rows.append({
            "student_id": s.student_id,
            "name": s.name,
            "age": s.age,
            "course": s.course,
            "faculty": s.faculty,
            "avg_sleep_hours": s.average_sleep_hours(),
            "exercise_sessions": len(s.exercise_records),
            "survey_count": len(s.surveys),
            "flagged": s.has_concerns(),
        })
    columns = ["student_id", "name", "age", "course", "faculty",
               "avg_sleep_hours", "exercise_sessions", "survey_count", "flagged"]
    return pd.DataFrame(rows, columns=columns)


def exercise_dataframe(system):
    """One row per exercise record across every student - the shape
    charts and day-of-week breakdowns are built from."""
    rows = []
    for s in system.all_students():
        for r in s.exercise_records:
            rows.append({
                "student_id": s.student_id,
                "name": s.name,
                "faculty": s.faculty,
                "exercise_type": r.exercise_type,
                "duration": r.duration,
                "day": r.day,
                "time_of_day": r.time_of_day,
            })
    columns = ["student_id", "name", "faculty", "exercise_type", "duration", "day", "time_of_day"]
    return pd.DataFrame(rows, columns=columns)


def faculty_summary_table(system):
    """One row per faculty: headcount, average sleep across the
    faculty, and how many students in that faculty are flagged."""
    df = students_dataframe(system)
    if df.empty:
        return pd.DataFrame(columns=["faculty", "headcount", "avg_sleep_hours", "flagged_count"])
    grouped = df.groupby("faculty").agg(
        headcount=("student_id", "count"),
        avg_sleep_hours=("avg_sleep_hours", "mean"),
        flagged_count=("flagged", "sum"),
    ).reset_index()
    grouped["avg_sleep_hours"] = grouped["avg_sleep_hours"].round(2)
    return grouped.sort_values("faculty").reset_index(drop=True)


# Charts - every function returns the saved file path, or None if there
# wasn't enough data to draw anything meaningful (an empty chart is
# more confusing than no chart).

DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def chart_average_sleep_bar(system, charts_dir):
    df = students_dataframe(system).dropna(subset=["avg_sleep_hours"])
    if df.empty:
        return None
    output_path = os.path.join(charts_dir, "average_sleep.png")

    plt.figure(figsize=(8, 5))
    plt.bar(df["name"], df["avg_sleep_hours"], color="#4C72B0")
    plt.axhline(y=8, color="red", linestyle="--", label="8hr benchmark")
    plt.ylabel("Average hours slept")
    plt.title("Average Sleep per Student")
    plt.xticks(rotation=30, ha="right")
    plt.legend()
    plt.tight_layout()
    _save(output_path)
    return output_path


def chart_exercise_minutes_by_day(system, charts_dir):
    df = exercise_dataframe(system)
    if df.empty:
        return None
    output_path = os.path.join(charts_dir, "exercise_by_day.png")

    totals = df.groupby("day")["duration"].sum().reindex(DAY_ORDER).fillna(0)

    plt.figure(figsize=(8, 5))
    plt.plot(
        [d.title()[:3] for d in totals.index], totals.values,
        marker="o", color="#55A868",
    )
    plt.ylabel("Total exercise minutes (all students)")
    plt.title("Exercise Minutes by Day of Week")
    plt.tight_layout()
    _save(output_path)
    return output_path


def chart_intervention_pie(system, charts_dir):
    total = system.student_count()
    if total == 0:
        return None
    output_path = os.path.join(charts_dir, "intervention_split.png")

    flagged = len(system.students_needing_intervention())
    ok = total - flagged

    plt.figure(figsize=(5, 5))
    plt.pie(
        [flagged, ok], labels=["Needs intervention", "Within healthy range"],
        colors=["#C44E52", "#55A868"], autopct="%1.0f%%", startangle=90,
    )
    plt.title("Wellness Intervention Split")
    plt.tight_layout()
    _save(output_path)
    return output_path


def chart_faculty_headcount(system, charts_dir):
    counts = system.faculty_counts()
    if not counts:
        return None
    output_path = os.path.join(charts_dir, "faculty_headcount.png")

    plt.figure(figsize=(8, 5))
    plt.bar(list(counts.keys()), list(counts.values()), color="#8172B2")
    plt.ylabel("Students registered")
    plt.title("Students per Faculty")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    _save(output_path)
    return output_path


def chart_dashboard(system, charts_dir):
    """A single 4-panel figure combining all four charts above, for a
    one-slide overview in the presentation. Returns None (rather than a
    half-empty dashboard) if there's no data at all yet."""
    if system.student_count() == 0:
        return None
    output_path = os.path.join(charts_dir, "dashboard.png")

    students_df = students_dataframe(system).dropna(subset=["avg_sleep_hours"])
    exercise_df = exercise_dataframe(system)
    faculty_counts = system.faculty_counts()
    flagged = len(system.students_needing_intervention())
    ok = system.student_count() - flagged

    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    fig.suptitle("CampusTrack Wellness Dashboard", fontsize=14, fontweight="bold")

    ax = axes[0, 0]
    if not students_df.empty:
        ax.bar(students_df["name"], students_df["avg_sleep_hours"], color="#4C72B0")
        ax.axhline(y=8, color="red", linestyle="--")
    ax.set_title("Average Sleep per Student")
    ax.tick_params(axis="x", rotation=30)

    ax = axes[0, 1]
    if not exercise_df.empty:
        totals = exercise_df.groupby("day")["duration"].sum().reindex(DAY_ORDER).fillna(0)
        ax.plot([d.title()[:3] for d in totals.index], totals.values, marker="o", color="#55A868")
    ax.set_title("Exercise Minutes by Day")

    ax = axes[1, 0]
    if faculty_counts:
        ax.bar(list(faculty_counts.keys()), list(faculty_counts.values()), color="#8172B2")
    ax.set_title("Students per Faculty")
    ax.tick_params(axis="x", rotation=30)

    ax = axes[1, 1]
    ax.pie([flagged, ok], labels=["Needs intervention", "Healthy range"],
           colors=["#C44E52", "#55A868"], autopct="%1.0f%%", startangle=90)
    ax.set_title("Intervention Split")

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    _save(output_path)
    return output_path


def generate_all_charts(system, charts_dir):
    """Runs every individual chart plus the combined dashboard. Returns
    a dict of {label: path_or_None} so the CLI can report exactly what
    was and wasn't generated."""
    os.makedirs(charts_dir, exist_ok=True)
    return {
        "Average sleep per student": chart_average_sleep_bar(system, charts_dir),
        "Exercise minutes by day": chart_exercise_minutes_by_day(system, charts_dir),
        "Intervention split": chart_intervention_pie(system, charts_dir),
        "Students per faculty": chart_faculty_headcount(system, charts_dir),
        "Combined dashboard": chart_dashboard(system, charts_dir),
    }


def _save(output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path)
    plt.close()
