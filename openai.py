import streamlit as st
import google.generativeai as genai
import os
import requests
from dotenv import load_dotenv
from docx import Document
import pdfplumber
from io import BytesIO
from streamlit_mic_recorder import speech_to_text

# --- Load Environment Variables ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST")

# --- Configure Gemini ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# --- Page Setup ---
st.set_page_config(page_title="Career Counsellor Bot", layout="centered")
st.title("🎓 Pathfinder – Career Counsellor")
st.markdown("Upload your resume or ask career/job/college-related questions. Avoid using for emergencies.")

# --- System Prompt ---
DOMAIN_PROMPT = (
    "You are a helpful and knowledgeable career/job/college counselling specialist. "
    "Only respond to career/job/college questions. If a question is outside this domain, politely refuse to answer."
)

# --- Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "resume_text" not in st.session_state:
    st.session_state.resume_text = ""

# --- Enhanced Resume Extractors ---
def extract_text_from_docx(file):
    try:
        file_buffer = BytesIO(file.read())
        doc = Document(file_buffer)
        text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
        if not text.strip():
            return "❌ No text found in DOCX."
        return text
    except Exception as e:
        return f"❌ Error reading DOCX: {e}"

def extract_text_from_pdf(file):
    try:
        pdf_file = BytesIO(file.read())
        with pdfplumber.open(pdf_file) as pdf:
            all_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text += text + "\n"
        if not all_text.strip():
            return "❌ No text found in PDF (might be scanned image)."
        return all_text
    except Exception as e:
        return f"❌ Error reading PDF: {e}"

# --- Job Search Function ---
def search_jobs(query, location="India"):
    url = f"https://{RAPIDAPI_HOST}/search"
    params = {"query": query, "location": location, "page": "1", "num_pages": "1"}
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        jobs = response.json().get("data", [])
        if not jobs:
            return "🔍 No jobs found for this query."
        job_list = "\n\n".join(
            [f"**{job['job_title']}** at {job['employer_name']}\n📍 {job['job_city']}, {job['job_country']}\n🔗 [Apply Here]({job['job_apply_link']})"
             for job in jobs[:5]]
        )
        return f"Here are some job openings:\n\n{job_list}"
    except Exception as e:
        return f"⚠ Failed to fetch jobs: {e}"

# --- Show Chat History ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Chat Form with Mic + Resume Upload ---
with st.form("chat_form", clear_on_submit=True):
    col1, col2, col3 = st.columns([7, 1, 2])

    with col1:
        user_text = st.text_input("Ask your career-related question...", label_visibility="collapsed")

    with col2:
        mic_text = speech_to_text(start_prompt="🎤", stop_prompt="⏹", just_once=True, use_container_width=True)

    with col3:
        uploaded_file = st.file_uploader("📎", label_visibility="collapsed", type=["pdf", "docx"])

    submitted = st.form_submit_button("Send")

# --- Resume Upload Handling ---
if uploaded_file:
    st.write("✅ File uploaded:", uploaded_file.name)
    st.write("📄 File type:", uploaded_file.type)

    if uploaded_file.type == "application/pdf":
        st.session_state.resume_text = extract_text_from_pdf(uploaded_file)
    elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        st.session_state.resume_text = extract_text_from_docx(uploaded_file)
    else:
        st.error("❌ Unsupported file type.")

    st.write("🧪 Extracted resume text (first 500 characters):")
    st.code(st.session_state.resume_text[:500])

    if st.session_state.resume_text and "❌" not in st.session_state.resume_text:
        with st.expander("📄 Full Extracted Resume"):
            st.text_area("Resume Content", st.session_state.resume_text, height=300)

        analysis_prompt = f"""
You are a professional career counsellor. Analyze the following resume and provide:
1. Summary of candidate profile
2. Strengths and skills
3. Suggested job roles or industries
4. Areas of improvement

Resume Content:
{st.session_state.resume_text}
"""
        with st.spinner("🔍 Analyzing resume..."):
            try:
                res = model.generate_content(analysis_prompt)
                st.chat_message("assistant").markdown(res.text)
                st.session_state.messages.append({"role": "assistant", "content": res.text})
            except Exception as e:
                st.error(f"Gemini error: {e}")
    else:
        st.error("❌ Failed to extract usable text from resume.")

# --- Handle Chat Submission ---
user_input = user_text or mic_text
if submitted and user_input:
    st.chat_message("user").markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    chat_history = "\n".join(
        [f"{msg['role'].capitalize()}: {msg['content']}" for msg in st.session_state.messages]
    )
    full_prompt = f"{DOMAIN_PROMPT}\n\n{chat_history}\nUser: {user_input}"

    job_keywords = ["job", "jobs", "openings", "opportunity", "vacancy"]
    search_keywords = ["find", "search", "looking", "get", "apply"]

    if any(jk in user_input.lower() for jk in job_keywords) and any(sk in user_input.lower() for sk in search_keywords):
        bot_reply = search_jobs(user_input)
    else:
        try:
            response = model.generate_content(full_prompt)
            bot_reply = response.text
        except Exception as e:
            bot_reply = f"⚠ Error: {e}"

    st.chat_message("assistant", Avatar="OIP.webp").markdown(bot_reply)
    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
