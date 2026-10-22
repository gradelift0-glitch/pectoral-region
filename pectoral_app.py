import random
import re
from collections import Counter

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Gradelift Pectoral Region Quiz", page_icon="🫀", layout="centered")

LOCAL_FILE = "question_bank.xlsx"   # only used when no SHEET_URL secret is set
LETTERS = ["A", "B", "C", "D"]
CORRECT_COL = "Correct (letter)"
REQUIRED = ["ID", "Tag", "Question", "Option A", "Option B", "Option C", "Option D",
            CORRECT_COL, "Explanation"]


def secret(key, default=""):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


# ---------- Data ----------
@st.cache_data(ttl=300, show_spinner="Loading questions...")
def load_questions(sheet_url: str) -> pd.DataFrame:
    if sheet_url:
        m = re.search(r"/d/([a-zA-Z0-9_-]+)", sheet_url)
        if m:
            csv_url = f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv"
            g = re.search(r"gid=(\d+)", sheet_url)
            if g:
                csv_url += f"&gid={g.group(1)}"
        else:
            csv_url = sheet_url
        df = pd.read_csv(csv_url)
    else:
        df = pd.read_excel(LOCAL_FILE, sheet_name="Questions")

    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in the question bank: {', '.join(missing)}")

    for c in df.columns:
        df[c] = df[c].fillna("").astype(str).str.strip()
    if "Source note" not in df.columns:
        df["Source note"] = ""
    df[CORRECT_COL] = df[CORRECT_COL].str.upper()
    df = df[(df["Question"] != "") & (df[CORRECT_COL].isin(LETTERS)) & (df["Tag"] != "")]
    df = df[df.apply(lambda r: r[f"Option {r[CORRECT_COL]}"] != "", axis=1)]
    return df.reset_index(drop=True)


def build_quiz(df: pd.DataFrame):
    """All questions, in random order, with shuffled options."""
    quiz = []
    for _, row in df.iterrows():
        opts = [row[f"Option {l}"] for l in LETTERS if row[f"Option {l}"]]
        correct_text = row[f"Option {row[CORRECT_COL]}"]
        random.shuffle(opts)
        quiz.append({
            "q": row["Question"], "options": opts, "correct": correct_text,
            "explanation": row["Explanation"], "tag": row["Tag"],
            "note": row["Source note"],
        })
    random.shuffle(quiz)
    return quiz


# ---------- State ----------
def init_state():
    defaults = {"stage": "login", "name": "", "quiz": [], "idx": 0,
                "answers": {}, "confirm": False}
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


def go_intro():
    st.session_state.update({"stage": "intro", "quiz": [], "idx": 0,
                             "answers": {}, "confirm": False})


# ---------- Pages ----------
def page_login():
    st.title("🫀 Pectoral Region & Breast Quiz")
    st.write("A free diagnostic quiz from Gradelift. Find out what you know and what to revise.")
    code_needed = secret("ACCESS_CODE")
    name = st.text_input("Your first name")
    code = st.text_input("Access code", type="password") if code_needed else ""
    if st.button("Continue", type="primary"):
        if code_needed and code.strip().lower() != str(code_needed).strip().lower():
            st.error("That access code is not correct.")
            return
        st.session_state.name = name.strip()
        st.session_state.stage = "intro"
        st.rerun()


def page_intro(df):
    total = len(df)
    st.title("Before you start")
    st.markdown(f"""
This quiz has **{total} questions** on the pectoral region and the breast.

⏱️ **Set aside at least 1 hour.** Find a quiet place and sit down to do it in one go.

📝 You will see your answers and explanations **after you submit**, together with a breakdown of **where you are strong and where you need to revise**.

📵 For an honest result, answer without your notes.
""")
    ready = st.checkbox("I have at least 1 hour free and I'm ready to start")
    if st.button(f"Start the {total} questions", type="primary", disabled=not ready):
        st.session_state.quiz = build_quiz(df)
        st.session_state.idx = 0
        st.session_state.answers = {}
        st.session_state.confirm = False
        st.session_state.stage = "quiz"
        st.rerun()


def page_quiz():
    quiz = st.session_state.quiz
    answers = st.session_state.answers
    idx = st.session_state.idx
    n = len(quiz)
    q = quiz[idx]

    st.progress((idx + 1) / n)
    st.caption(f"Question {idx + 1} of {n}  •  {len(answers)} answered")
    st.markdown(f"**{q['q']}**")

    prev = answers.get(idx)
    start_index = q["options"].index(prev) if prev in q["options"] else None
    choice = st.radio("Choose one", q["options"], index=start_index,
                      key=f"choice_{idx}", label_visibility="collapsed")
    if choice is not None:
        answers[idx] = choice

    c1, c2 = st.columns(2)
    with c1:
        if idx > 0 and st.button("← Previous", use_container_width=True):
            st.session_state.idx -= 1
            st.session_state.confirm = False
            st.rerun()
    with c2:
        if idx < n - 1:
            if st.button("Next →", type="primary", use_container_width=True):
                st.session_state.idx += 1
                st.session_state.confirm = False
                st.rerun()
        else:
            if st.button("Submit quiz", type="primary", use_container_width=True):
                if len(answers) < n:
                    st.session_state.confirm = True
                else:
                    st.session_state.stage = "result"
                st.rerun()

    if st.session_state.confirm:
        missing = [i + 1 for i in range(n) if i not in answers]
        st.warning(f"You have {len(missing)} unanswered question(s): "
                   + ", ".join(map(str, missing[:15])) + ("..." if len(missing) > 15 else "")
                   + ". Unanswered questions count as wrong.")
        d1, d2 = st.columns(2)
        with d1:
            if st.button("Go back and answer", use_container_width=True):
                st.session_state.idx = missing[0] - 1
                st.session_state.confirm = False
                st.rerun()
        with d2:
            if st.button("Submit anyway", use_container_width=True):
                st.session_state.stage = "result"
                st.rerun()


def status_of(pct):
    if pct >= 75:
        return "🟢", "strong"
    if pct >= 50:
        return "🟡", "revise"
    return "🔴", "weak"


def page_result():
    quiz = st.session_state.quiz
    answers = st.session_state.answers
    name = st.session_state.name
    total = len(quiz)

    tags = {}
    missed = []
    correct = 0
    for i, q in enumerate(quiz):
        chosen = answers.get(i)
        right = chosen == q["correct"]
        correct += int(right)
        t = tags.setdefault(q["tag"], {"right": 0, "total": 0, "notes": Counter()})
        t["total"] += 1
        t["right"] += int(right)
        if q["note"]:
            t["notes"][q["note"]] += 1
        if not right:
            missed.append((q, chosen))

    st.title("Your results")
    pct_all = round(100 * correct / total)
    st.subheader(f"{name + ', you' if name else 'You'} scored {correct}/{total} ({pct_all}%)")
    st.caption("Your results are not saved. Take a screenshot if you want to keep them.")

    scored = sorted(((tag, t, 100 * t["right"] / t["total"]) for tag, t in tags.items()),
                    key=lambda x: x[2])

    st.markdown("### Score by topic")
    for tag, t, pct in scored:
        icon, _ = status_of(pct)
        st.write(f"{icon} **{tag}**: {t['right']}/{t['total']} ({round(pct)}%)")

    strong = [tag for tag, _, p in scored if p >= 75]
    needs = [(tag, t, p) for tag, t, p in scored if p < 75]

    st.markdown("### What to do next")
    if strong:
        st.write("✅ **You are strong in:** " + "; ".join(strong) + ".")
    if not needs:
        st.write("Excellent. You are solid across every topic. Keep revising to stay sharp.")
    for tag, t, p in needs:
        icon, label = status_of(p)
        note = t["notes"].most_common(1)[0][0] if t["notes"] else ""
        if label == "weak":
            line = f"{icon} **{tag}**: go back and study this again ({t['right']}/{t['total']} correct)."
        else:
            line = f"{icon} **{tag}**: revise this a bit more ({t['right']}/{t['total']} correct)."
        if note:
            line += f" Revise from: *{note}*."
        st.write(line)

    if missed:
        with st.expander(f"Review the {len(missed)} question(s) you missed"):
            for q, chosen in missed:
                st.markdown(f"**{q['q']}**")
                st.write(f"Topic: {q['tag']}")
                st.write(f"You chose: {chosen if chosen else 'Not answered'}")
                st.write(f"Correct answer: {q['correct']}")
                if q["explanation"]:
                    st.caption(q["explanation"])
                st.divider()

    st.divider()
    if st.button("Retake the quiz"):
        go_intro()
        st.rerun()


# ---------- Main ----------
init_state()
if st.session_state.stage == "login":
    page_login()
else:
    try:
        data = load_questions(secret("SHEET_URL"))
    except Exception as e:
        st.error("Could not load the questions.")
        st.caption(str(e))
        st.stop()
    if data.empty:
        st.error("No valid questions were found in the question bank.")
        st.stop()
    stage = st.session_state.stage
    if stage == "intro":
        page_intro(data)
    elif stage == "quiz" and st.session_state.quiz:
        page_quiz()
    elif stage == "result" and st.session_state.quiz:
        page_result()
    else:
        go_intro()
        st.rerun()
