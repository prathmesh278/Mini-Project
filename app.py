import streamlit as st
import pypdf
import smtplib
import re
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- HELPER FUNCTIONS ---

def extract_text_from_pdf(file):
    try:
        pdf_reader = pypdf.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception:
        return ""

def extract_email_from_text(text):
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    match = re.search(email_pattern, text)
    return match.group(0) if match else None

def calculate_score(text, req_skills, req_edu):
    text = text.lower()
    
    # 1. Education Scoring (30%)
    # Uses word boundaries \b to ensure exact matches
    edu_matches = [edu for edu in req_edu if re.search(rf'\b{re.escape(edu.lower())}\b', text)]
    edu_score = 30 if edu_matches else 0
        
    # 2. Skills Scoring (70%)
    skill_matches = [skill for skill in req_skills if re.search(rf'\b{re.escape(skill.lower())}\b', text)]
    
    if req_skills:
        skill_score = (len(skill_matches) / len(req_skills)) * 70
    else:
        skill_score = 70 # Default to max if no skills are specified
        
    total_score = round(edu_score + skill_score, 2)
    return total_score, skill_matches, edu_matches

def send_email(to_email, subject, body, sender_mail, sender_pw):
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_mail
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_mail, sender_pw)
        server.sendmail(sender_mail, to_email, msg.as_string())
        server.quit()
        return True
    except Exception:
        return False

# --- STREAMLIT UI ---
st.set_page_config(page_title="AI Resume Screener Pro", layout="wide")
st.title("🚀 Smart Resume Screening & Automation")

# --- SIDEBAR CONFIGURATION ---
with st.sidebar:
    st.header("⚙️ Recruitment Settings")
    
    # Dynamic Filtering Setup
    REQUIRED_SKILLS = st.multiselect(
        "Required Skills", 
        ["Python", "SQL", "Machine Learning", "Tableau", "Excel", "Java", "AWS", "Communication", "React", "Docker"],
        default=["Python", "SQL", "Machine Learning"]
    )
    
    REQUIRED_EDUCATION = st.multiselect(
        "Required Education/Degrees",
        ["B.Tech", "M.Tech", "Computer Science", "MCA", "BCA", "Data Science", "MBA"],
        default=["B.Tech", "Computer Science"]
    )
    
    CUTOFF_SCORE = st.slider("Pass Cutoff Score (%)", 0, 100, 65)
    
    st.divider()
    
    st.header("📧 Email Settings")
    enable_email = st.checkbox("Enable Email Automation", value=False)
    SENDER_EMAIL = st.text_input("Sender Email", value="hirebot.project@gmail.com")
    SENDER_PASSWORD = st.text_input("App Password", type="password", value="nfyq ghye qzlw bmcb")

# --- MAIN INTERFACE ---
col1, col2 = st.columns(2)
col1.metric("Current Cutoff", f"{CUTOFF_SCORE}%")
col2.metric("Skill Weight", "70%")

uploaded_files = st.file_uploader("Upload Candidate Resumes (PDF)", type="pdf", accept_multiple_files=True)

if uploaded_files and st.button(f"Analyze {len(uploaded_files)} Resumes"):
    
    results_data = []
    progress_bar = st.progress(0)
    
    for i, file in enumerate(uploaded_files):
        # 1. Processing
        raw_text = extract_text_from_pdf(file)
        candidate_email = extract_email_from_text(raw_text)
        
        # 2. Scoring with dynamic inputs
        score, found_skills, found_edu = calculate_score(raw_text, REQUIRED_SKILLS, REQUIRED_EDUCATION)
        
        # 3. Decision
        status = "SELECTED" if score >= CUTOFF_SCORE else "REJECTED"
        
        # 4. Email Logic
        email_sent = "Disabled"
        if enable_email and candidate_email:
            subj = "Update: Application Status" if status == "REJECTED" else "Interview Invitation"
            body = f"Hello,\n\nYour profile scored {score}%. Status: {status}.\n\nBest regards,\nHR Team"
            
            if send_email(candidate_email, subj, body, SENDER_EMAIL, SENDER_PASSWORD):
                email_sent = "Sent ✅"
            else:
                email_sent = "Failed ❌"
        elif enable_email and not candidate_email:
            email_sent = "Missing Email ⚠️"

        # 5. Data Storage
        results_data.append({
            "Candidate": file.name,
            "Score": score,
            "Status": status,
            "Email": candidate_email,
            "Email Status": email_sent,
            "Matched Skills": ", ".join(found_skills)
        })
        
        progress_bar.progress((i + 1) / len(uploaded_files))

    # --- DASHBOARD ---
    st.divider()
    df = pd.DataFrame(results_data)
    
    c1, c2 = st.columns([1, 2])
    with c1:
        st.write("### Selection Summary")
        st.dataframe(df['Status'].value_counts())
    
    with c2:
        st.write("### Skill Distribution")
        st.bar_chart(df.set_index('Candidate')['Score'])

    st.write("### Detailed Candidate Log")
    def style_status(val):
        color = '#2ecc71' if val == 'SELECTED' else '#e74c3c'
        return f'background-color: {color}; color: white; font-weight: bold'

    st.dataframe(df.style.applymap(style_status, subset=['Status']), use_container_width=True)
    
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Recruitment Report", csv, "screening_report.csv", "text/csv")
