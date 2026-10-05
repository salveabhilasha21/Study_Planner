import sqlite3
from pathlib import Path

import pandas as pd


DATABASE_FILE = Path(__file__).with_name("study_planner.db")


def get_connection():
    return sqlite3.connect(DATABASE_FILE)


def create_tables():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            topic TEXT,
            hours REAL NOT NULL,
            priority INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            study_date TEXT NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT,
            hours REAL NOT NULL,
            done INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            score REAL NOT NULL,
            total_marks REAL NOT NULL,
            quiz_date TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()


def add_subject(name, topic, hours, priority):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO subjects (name, topic, hours, priority)
        VALUES (?, ?, ?, ?)
    """, (name, topic, hours, priority))

    connection.commit()
    connection.close()


def get_subjects():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT name, topic, hours, priority
        FROM subjects
        ORDER BY priority DESC
    """)

    rows = cursor.fetchall()
    connection.close()

    subjects = []

    for row in rows:
        subjects.append(
            {
                "name": row[0],
                "topic": row[1],
                "hours": row[2],
                "priority": row[3]
            }
        )

    return subjects


def delete_all_subjects():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("DELETE FROM subjects")

    connection.commit()
    connection.close()


def save_timetable(schedule):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("DELETE FROM timetable")

    for _, row in schedule.iterrows():
        cursor.execute("""
            INSERT INTO timetable (
                study_date,
                subject,
                topic,
                hours,
                done
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            str(row["Date"]),
            row["Subject"],
            row["Topic"],
            float(row["Hours"]),
            int(bool(row["Done"]))
        ))

    connection.commit()
    connection.close()


def get_timetable():
    connection = get_connection()

    schedule = pd.read_sql_query("""
        SELECT
            study_date AS Date,
            subject AS Subject,
            topic AS Topic,
            hours AS Hours,
            done AS Done
        FROM timetable
        ORDER BY study_date
    """, connection)

    connection.close()

    if not schedule.empty:
        schedule["Date"] = pd.to_datetime(schedule["Date"]).dt.date
        schedule["Done"] = schedule["Done"].astype(bool)

    return schedule


def clear_timetable():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("DELETE FROM timetable")

    connection.commit()
    connection.close()


def save_quiz_result(subject, topic, score, total_marks):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO quiz_results (
            subject,
            topic,
            score,
            total_marks,
            quiz_date
        )
        VALUES (?, ?, ?, ?, DATE('now'))
    """, (
        subject,
        topic,
        score,
        total_marks
    ))

    connection.commit()
    connection.close()


def get_quiz_results():
    connection = get_connection()

    results = pd.read_sql_query("""
        SELECT
            quiz_date AS Date,
            subject AS Subject,
            topic AS Topic,
            score AS Score,
            total_marks AS TotalMarks
        FROM quiz_results
        ORDER BY id DESC
    """, connection)

    connection.close()

    return results