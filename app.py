from datetime import date, timedelta
import json
import os
import re

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google import genai

from database import (
    add_subject,
    clear_timetable,
    create_tables,
    delete_all_subjects,
    get_quiz_results,
    get_subjects,
    get_timetable,
    save_quiz_result,
    save_timetable
)


create_tables()

load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")

st.set_page_config(
    page_title="AI Study Planner",
    page_icon="📚",
    layout="wide"
)


if "subjects" not in st.session_state:
    st.session_state.subjects = get_subjects()

if "schedule" not in st.session_state:
    st.session_state.schedule = get_timetable()

if "ai_advice" not in st.session_state:
    st.session_state.ai_advice = ""

if "mcq_questions" not in st.session_state:
    st.session_state.mcq_questions = []

if "mcq_subject" not in st.session_state:
    st.session_state.mcq_subject = ""

if "mcq_topic" not in st.session_state:
    st.session_state.mcq_topic = ""

if "mcq_result" not in st.session_state:
    st.session_state.mcq_result = None

if "test_number" not in st.session_state:
    st.session_state.test_number = 0


def create_timetable(subjects, start_date, days, daily_hours):
    remaining_hours = {
        subject["name"]: subject["hours"]
        for subject in subjects
    }

    priority = {
        subject["name"]: subject["priority"]
        for subject in subjects
    }

    topics = {
        subject["name"]: subject["topic"]
        for subject in subjects
    }

    timetable = []

    for day_number in range(days):
        current_date = start_date + timedelta(days=day_number)
        available_hours = daily_hours

        ordered_subjects = sorted(
            remaining_hours.keys(),
            key=lambda name: (
                priority[name],
                remaining_hours[name]
            ),
            reverse=True
        )

        for subject_name in ordered_subjects:
            if available_hours <= 0:
                break

            if remaining_hours[subject_name] <= 0:
                continue

            study_hours = min(
                1.0,
                available_hours,
                remaining_hours[subject_name]
            )

            timetable.append(
                {
                    "Date": current_date,
                    "Subject": subject_name,
                    "Topic": topics[subject_name] or "Revision",
                    "Hours": study_hours,
                    "Done": False
                }
            )

            remaining_hours[subject_name] -= study_hours
            available_hours -= study_hours

    return pd.DataFrame(timetable)


def get_ai_study_advice(subjects, plan_days, daily_hours):
    if not gemini_api_key:
        return "Gemini API key was not found. Check your .env file."

    subject_details = "\n".join(
        [
            f"- Subject: {subject['name']}, "
            f"Topic: {subject['topic']}, "
            f"Required hours: {subject['hours']}, "
            f"Priority: {subject['priority']}/5"
            for subject in subjects
        ]
    )

    prompt = f"""
You are an expert AI study planner.

Create personalized study advice for a student.

Plan duration: {plan_days} days
Available hours per day: {daily_hours}

Subjects:
{subject_details}

Give the answer in clear English.

Include:
1. Best study strategy for every subject.
2. Revision tips.
3. Time-management tips.
4. Break and productivity tips.
5. A short motivation message.

Keep the answer concise and useful.
"""

    client = genai.Client(api_key=gemini_api_key)

    interaction = client.interactions.create(
        model="gemini-3.6-flash",
        input=prompt
    )

    return interaction.output_text


def extract_json(text):
    clean_text = text.strip()
    clean_text = clean_text.replace("```json", "")
    clean_text = clean_text.replace("```", "")
    clean_text = clean_text.strip()

    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean_text, re.DOTALL)

        if match:
            return json.loads(match.group())

        raise ValueError("Gemini did not return valid quiz data.")


def generate_mcq_test(subject, topic):
    if not gemini_api_key:
        raise ValueError("Gemini API key was not found. Check your .env file.")

    prompt = f"""
You are an expert teacher.

Create exactly 20 multiple-choice questions.

Subject: {subject}
Topic: {topic}

Return ONLY valid JSON.

Use exactly this format:

{{
  "questions": [
    {{
      "question": "Question text",
      "options": {{
        "A": "Option one",
        "B": "Option two",
        "C": "Option three",
        "D": "Option four"
      }},
      "answer": "A"
    }}
  ]
}}

Rules:
- Return exactly 20 questions.
- Every question has A, B, C, and D options.
- Answer must be A, B, C, or D.
"""

    client = genai.Client(api_key=gemini_api_key)

    interaction = client.interactions.create(
        model="gemini-3.6-flash",
        input=prompt
    )

    quiz_data = extract_json(interaction.output_text)
    questions = quiz_data.get("questions", [])

    if len(questions) != 20:
        raise ValueError("AI did not generate exactly 20 questions.")

    return questions


# Sidebar menu
with st.sidebar:
    st.header("📚 Study Planner")

    selected_page = st.radio(
        "Menu",
        [
            "Dashboard",
            "1. Add Subjects",
            "2. Timetable and AI Advice",
            "3. Progress",
            "4. AI MCQ Test",
            "5. Quiz Results"
        ]
    )


# Main page title and settings
st.title("📚 AI Study Planner")
st.write("Create a timetable, get AI advice, and take AI MCQ tests.")

st.subheader("Study Planner Settings")

setting_col1, setting_col2, setting_col3 = st.columns(3)

with setting_col1:
    start_date = st.date_input(
        "Start Date",
        value=date.today()
    )

with setting_col2:
    plan_days = st.slider(
        "Number of Days",
        min_value=1,
        max_value=30,
        value=7
    )

with setting_col3:
    daily_hours = st.slider(
        "Available Hours Per Day",
        min_value=1.0,
        max_value=12.0,
        value=3.0,
        step=0.5
    )

st.divider()


if selected_page == "Dashboard":
    st.subheader("📊 Learning Dashboard")

    schedule = st.session_state.schedule
    quiz_results = get_quiz_results()

    total_subjects = len(st.session_state.subjects)
    planned_hours = float(schedule["Hours"].sum()) if not schedule.empty else 0
    completed_hours = (
        float(schedule.loc[schedule["Done"], "Hours"].sum())
        if not schedule.empty
        else 0
    )
    study_progress = (
        (completed_hours / planned_hours) * 100
        if planned_hours > 0
        else 0
    )
    average_quiz_score = 0.0

    if not quiz_results.empty:
        quiz_results["Percentage"] = (
            quiz_results["Score"]
            / quiz_results["TotalMarks"]
            * 100
        )
        average_quiz_score = float(quiz_results["Percentage"].mean())

    tests_taken = len(quiz_results)

    metric_one, metric_two, metric_three, metric_four, metric_five = st.columns(5)
    metric_one.metric("Subjects", total_subjects)
    metric_two.metric("Study Progress", f"{study_progress:.0f}%")
    metric_three.metric("Completed Hours", f"{completed_hours:.1f} h")
    metric_four.metric("Average Quiz Score", f"{average_quiz_score:.0f}%")
    metric_five.metric("Tests Taken", tests_taken)

    if planned_hours > 0:
        st.progress(study_progress / 100)

    chart_left, chart_right = st.columns(2)

    with chart_left:
        st.subheader("Study Hours by Subject")

        if schedule.empty:
            st.info("Generate a timetable to view study-hour data.")
        else:
            subject_progress = schedule.copy()
            subject_progress["Completed Hours"] = subject_progress.apply(
                lambda row: row["Hours"] if row["Done"] else 0,
                axis=1
            )
            subject_progress["Remaining Hours"] = subject_progress.apply(
                lambda row: 0 if row["Done"] else row["Hours"],
                axis=1
            )

            subject_progress = subject_progress.groupby("Subject")[
                ["Completed Hours", "Remaining Hours"]
            ].sum()

            st.bar_chart(subject_progress)

    with chart_right:
        st.subheader("Quiz Performance by Subject")

        if quiz_results.empty:
            st.info("Complete an AI MCQ test to view quiz performance.")
        else:
            subject_scores = quiz_results.groupby("Subject")[
                "Percentage"
            ].mean().sort_values()

            st.bar_chart(subject_scores)

    if not quiz_results.empty:
        st.subheader("Recent Quiz Scores")

        recent_scores = quiz_results.copy()
        recent_scores["Test"] = [
            f"Test {number}"
            for number in range(len(recent_scores), 0, -1)
        ]
        recent_scores = recent_scores.iloc[::-1].set_index("Test")

        st.line_chart(recent_scores["Percentage"])

        weak_subject = subject_scores.index[0]
        weak_score = float(subject_scores.iloc[0])

        if weak_score < 60:
            st.warning(
                f"Focus area: {weak_subject} has the lowest average quiz score "
                f"({weak_score:.0f}%). Try another AI MCQ test after revision."
            )
        else:
            st.success("Great work! Your recorded quiz scores are at 60% or above.")


elif selected_page == "1. Add Subjects":
    st.subheader("Add Study Subjects")

    with st.form("subject_form", clear_on_submit=True):
        subject_name = st.text_input(
            "Subject Name",
            placeholder="Mathematics"
        )

        topic = st.text_input(
            "Topic",
            placeholder="Algebra"
        )

        hours = st.number_input(
            "Required Study Hours",
            min_value=1.0,
            max_value=100.0,
            value=4.0,
            step=0.5
        )

        priority = st.slider(
            "Priority (1 = Low, 5 = High)",
            min_value=1,
            max_value=5,
            value=3
        )

        add_subject_button = st.form_submit_button("Add Subject")

    if add_subject_button:
        if subject_name.strip() == "":
            st.error("Please enter a subject name.")
        else:
            add_subject(
                subject_name.strip(),
                topic.strip(),
                hours,
                priority
            )

            st.session_state.subjects = get_subjects()
            st.success("Subject saved successfully.")

    if st.session_state.subjects:
        st.dataframe(
            pd.DataFrame(st.session_state.subjects),
            use_container_width=True,
            hide_index=True
        )

        if st.button("Delete All Subjects"):
            delete_all_subjects()
            clear_timetable()

            st.session_state.subjects = []
            st.session_state.schedule = pd.DataFrame(
                columns=["Date", "Subject", "Topic", "Hours", "Done"]
            )

            st.rerun()
    else:
        st.info("Add your first subject to begin.")


elif selected_page == "2. Timetable and AI Advice":
    st.subheader("Your Study Timetable")

    if st.button("Generate Timetable"):
        if len(st.session_state.subjects) == 0:
            st.warning("Please add subjects first.")
        else:
            st.session_state.schedule = create_timetable(
                st.session_state.subjects,
                start_date,
                plan_days,
                daily_hours
            )

            save_timetable(st.session_state.schedule)
            st.success("Timetable created and saved.")

    if not st.session_state.schedule.empty:
        st.dataframe(
            st.session_state.schedule,
            use_container_width=True,
            hide_index=True
        )

        csv_data = st.session_state.schedule.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "Download Timetable as CSV",
            data=csv_data,
            file_name="study_timetable.csv",
            mime="text/csv"
        )
    else:
        st.info("Generate a timetable to see your study plan.")

    st.divider()
    st.subheader("✨ Gemini AI Study Advice")

    if st.button("Get AI Study Advice"):
        if len(st.session_state.subjects) == 0:
            st.warning("Please add subjects first.")
        elif not gemini_api_key:
            st.error("Gemini API key was not found. Check the .env file.")
        else:
            with st.spinner("Gemini AI is creating your study advice..."):
                try:
                    st.session_state.ai_advice = get_ai_study_advice(
                        st.session_state.subjects,
                        plan_days,
                        daily_hours
                    )
                except Exception as error:
                    st.error(f"Gemini API error: {error}")

    if st.session_state.ai_advice:
        st.write(st.session_state.ai_advice)


elif selected_page == "3. Progress":
    st.subheader("Study Progress")

    if not st.session_state.schedule.empty:
        updated_schedule = st.data_editor(
            st.session_state.schedule,
            use_container_width=True,
            hide_index=True,
            disabled=["Date", "Subject", "Topic", "Hours"]
        )

        st.session_state.schedule = updated_schedule
        save_timetable(updated_schedule)

        completed_hours = updated_schedule[
            updated_schedule["Done"] == True
        ]["Hours"].sum()

        total_hours = updated_schedule["Hours"].sum()

        progress = (
            completed_hours / total_hours
            if total_hours > 0
            else 0
        )

        first_column, second_column = st.columns(2)

        first_column.metric(
            "Completed Hours",
            f"{completed_hours:.1f} hours"
        )

        second_column.metric(
            "Progress",
            f"{progress * 100:.0f}%"
        )

        st.progress(progress)
    else:
        st.info("Your progress will appear after you generate a timetable.")


elif selected_page == "4. AI MCQ Test":
    st.subheader("🤖 20 Marks AI MCQ Test")
    st.write("Every question is worth 1 mark. Total marks: 20.")

    if st.session_state.subjects:
        subject_names = [
            subject["name"]
            for subject in st.session_state.subjects
        ]

        selected_subject = st.selectbox(
            "Select Subject",
            subject_names
        )

        selected_topic = st.text_input(
            "Enter Test Topic",
            placeholder="For example: Algebra"
        )

        if st.button("Generate 20 Marks MCQ Test"):
            if selected_topic.strip() == "":
                st.warning("Please enter a topic.")
            elif not gemini_api_key:
                st.error("Gemini API key was not found. Check the .env file.")
            else:
                with st.spinner("Gemini AI is creating your test..."):
                    try:
                        st.session_state.mcq_questions = generate_mcq_test(
                            selected_subject,
                            selected_topic.strip()
                        )

                        st.session_state.mcq_subject = selected_subject
                        st.session_state.mcq_topic = selected_topic.strip()
                        st.session_state.mcq_result = None
                        st.session_state.test_number += 1

                        st.success("Your 20-mark MCQ test is ready.")
                    except Exception as error:
                        st.error(f"Gemini API error: {error}")

        if st.session_state.mcq_questions:
            st.divider()

            with st.form("mcq_test_form"):
                selected_answers = {}

                for index, question in enumerate(
                    st.session_state.mcq_questions
                ):
                    options = question["options"]

                    selected_answers[index] = st.radio(
                        f"Q{index + 1}. {question['question']}",
                        options=["A", "B", "C", "D"],
                        format_func=lambda option, values=options:
                            f"{option}. {values[option]}",
                        index=None,
                        key=f"test_{st.session_state.test_number}_{index}"
                    )

                submit_test = st.form_submit_button(
                    "Submit Test and Get Score"
                )

            if submit_test:
                unanswered = [
                    number + 1
                    for number, answer in selected_answers.items()
                    if answer is None
                ]

                if unanswered:
                    st.warning(
                        f"Please answer all questions. Unanswered: {unanswered}"
                    )
                else:
                    score = 0
                    correct_answers = []

                    for index, question in enumerate(
                        st.session_state.mcq_questions
                    ):
                        correct_answer = question["answer"].upper()
                        correct_answers.append(correct_answer)

                        if selected_answers[index] == correct_answer:
                            score += 1

                    save_quiz_result(
                        st.session_state.mcq_subject,
                        st.session_state.mcq_topic,
                        score,
                        20
                    )

                    st.session_state.mcq_result = {
                        "score": score,
                        "correct_answers": correct_answers
                    }

            if st.session_state.mcq_result:
                score = st.session_state.mcq_result["score"]
                percentage = (score / 20) * 100

                st.subheader("🎉 Test Result")

                result_col1, result_col2 = st.columns(2)

                result_col1.metric("Your Score", f"{score} / 20")
                result_col2.metric("Percentage", f"{percentage:.0f}%")

                if score >= 16:
                    st.success("Excellent work!")
                elif score >= 10:
                    st.info("Good work. Revise once more to improve.")
                else:
                    st.warning("More practice is needed.")

                with st.expander("Show Correct Answers"):
                    for index, answer in enumerate(
                        st.session_state.mcq_result["correct_answers"]
                    ):
                        st.write(f"Question {index + 1}: {answer}")
    else:
        st.info("Add at least one subject before generating a test.")


elif selected_page == "5. Quiz Results":
    st.subheader("📊 Saved Quiz Results")

    quiz_results = get_quiz_results()

    if not quiz_results.empty:
        quiz_results["Percentage"] = (
            quiz_results["Score"]
            / quiz_results["TotalMarks"]
            * 100
        ).round(2)

        st.dataframe(
            quiz_results,
            use_container_width=True,
            hide_index=True
        )

        average_score = quiz_results["Percentage"].mean()

        st.metric(
            "Average Quiz Score",
            f"{average_score:.1f}%"
        )
    else:
        st.info("No quiz scores saved yet.")
