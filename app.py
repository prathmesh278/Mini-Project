import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import pypdf
import smtplib
import re
import pandas as pd
import sqlite3
from datetime import datetime
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="AI Resume Screener Pro", layout="wide")

st.markdown("""
    <style>
        [data-testid="stHeader"] { opacity: 0; }
        footer { visibility: hidden; }
        .block-container { padding-top: 2rem; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('resume_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS candidates
                 (date TEXT, filename TEXT, email TEXT, score REAL, status TEXT, missing_skills TEXT)''')
    conn.commit()
    conn.close()

def save_to_db(data_list):
    conn = sqlite3.connect('resume_history.db')
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for row in data_list:
        c.execute("INSERT INTO candidates VALUES (?,?,?,?,?,?)", 
                  (timestamp, row['Filename'], row['Email'], row['Score'], row['Status'], row['Missing Skills']))
    conn.commit()
    conn.close()

def fetch_history():
    conn = sqlite3.connect('resume_history.db')
    df = pd.read_sql_query("SELECT * FROM candidates ORDER BY date DESC", conn)
    conn.close()
    return df

init_db()

# --- 3. HELPER FUNCTIONS ---
def extract_text_from_pdf(file):
    try:
        pdf_reader = pypdf.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
        return text.lower()
    except: return ""

def extract_email_from_text(text):
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    match = re.search(email_pattern, text)
    return match.group(0) if match else None

def calculate_score_nlp(resume_text, required_skills, required_edu):
    job_description = " ".join(required_skills) + " " + " ".join(required_edu)
    documents = [resume_text, job_description]
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words='english')
    try:
        tfidf_matrix = vectorizer.fit_transform(documents)
        similarity_matrix = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
        score = round(similarity_matrix[0][0] * 100, 2)
    except: score = 0.0
    missing_skills = [skill for skill in required_skills if skill not in resume_text]
    return score, missing_skills

def send_email(to_email, subject, body_html, sender_email, sender_password):
    try:
        msg = MIMEMultipart()
        msg['From'] = f"Hire Bot <{sender_email}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body_html, 'html'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Email Error: {e}")
        return False

def style_status(val):
    color = '#d4edda' if val == 'SELECTED' else '#f8d7da'
    return f'background-color: {color}'

# --- 4. AUTH & CONFIG ---
try:
    with open('config.yaml') as file:
        config = yaml.load(file, Loader=SafeLoader)
    authenticator = stauth.Authenticate(
        config['credentials'], config['cookie']['name'],
        config['cookie']['key'], config['cookie']['expiry_days']
    )
    name, auth_status, username = authenticator.login('Login', 'main')
except:
    st.error("Config file missing!")
    st.stop()

if auth_status:
    authenticator.logout('Logout', 'sidebar')
    st.title("🚀 AI Resume Screener (NLP + Hire Bot)")
    
    tab1, tab2 = st.tabs(["📄 Analysis Board", "🗄️ Database"])

    with st.sidebar:
        st.header("1. Job Criteria")
        req_skills = st.text_area("Required Skills", "python, sql, machine learning, power bi")
        req_edu = st.text_area("Required Education", "bca, mca, b.tech")
        cutoff = st.slider("Cutoff Score (%)", 0, 100, 40)
        
        REQUIRED_SKILLS = [s.strip().lower() for s in req_skills.split(",") if s.strip()]
        REQUIRED_EDUCATION = [e.strip().lower() for e in req_edu.split(",") if e.strip()]
        
        st.divider()
        st.header("2. Email Settings")
        enable_email = st.checkbox("Enable Email Automation")
        ui_sender_email = st.text_input("Sender Email", placeholder="hirebot@gmail.com")
        ui_app_password = st.text_input("App Password", type="password")

    with tab1:
        uploaded_files = st.file_uploader("Upload Resumes (PDF)", type="pdf", accept_multiple_files=True)

        if uploaded_files and st.button("Start AI Analysis"):
            results_data = []
            progress = st.progress(0)
            
            for i, file in enumerate(uploaded_files):
                text = extract_text_from_pdf(file)
                email = extract_email_from_text(text)
                score, missing = calculate_score_nlp(text, REQUIRED_SKILLS, REQUIRED_EDUCATION)
                
                status = "SELECTED" if score >= cutoff else "REJECTED"
                email_sent_status = "Skipped"

                if enable_email and email and ui_sender_email and ui_app_password:
                    if status == "SELECTED":
                        subj = "Shortlisted for Interview"
                        body = f"<h3>Congrats!</h3><p>Your match score: {score}%.</p>"
                    else:
                        subj = "Application Update"
                        body = f"<h3>Status</h3><p>We need more experience in: {', '.join(missing[:2])}.</p>"
                    
                    if send_email(email, subj, body, ui_sender_email, ui_app_password):
                        email_sent_status = "Sent ✅"
                    else:
                        email_sent_status = "Failed ❌"

                results_data.append({
                    "Filename": file.name, "Email": email, "Score": score,
                    "Status": status, "Missing Skills": ", ".join(missing),
                    "Email Status": email_sent_status, "Raw Text": text
                })
                progress.progress((i + 1) / len(uploaded_files))
            
            st.session_state['results'] = pd.DataFrame(results_data)
            save_to_db(results_data)

        if 'results' in st.session_state:
            df = st.session_state['results']
            st.subheader("Detailed Candidate Log")
            # Pandas map fix for Line 158
            st.dataframe(df.style.map(style_status, subset=['Status']), use_container_width=True)

    with tab2:
        st.dataframe(fetch_history(), use_container_width=True)

elif auth_status is False: st.error('Invalid Credentials')
