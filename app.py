import streamlit as st
import pypdf
import smtplib
import re
import pandas as pd
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURATION ---
REQUIRED_SKILLS = {"python", "sql", "machine learning", "tableau", "excel", "communication", "java", "aws"}
REQUIRED_EDUCATION = {"b.tech", "computer science", "mca", "bca", "data science", "m.tech"}
CUTOFF_SCORE = 65 

# EMAIL SETTINGS
# ⚠️ Replace these with your actual App Password to send real emails
SENDER_EMAIL = "hirebot.project@gmail.com"
SENDER_PASSWORD = "nfyq ghye qzlw bmcb" 

# --- HELPER FUNCTIONS ---

def extract_text_from_pdf(file):
    try:
        pdf_reader = pypdf.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        return ""

def extract_email_from_text(text):
    # Regex pattern to find email addresses
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    match = re.search(email_pattern, text)
    return match.group(0) if match else None

def calculate_score(text):
    text = text.lower()
    # 1. Education (30%)
    edu_matches = [edu for edu in REQUIRED_EDUCATION if edu in text]
    edu_score = 30 if edu_matches else 0
        
    # 2. Skills (70%)
    skill_matches = [skill for skill in REQUIRED_SKILLS if skill in text]
    if REQUIRED_SKILLS:
        skill_score = (len(skill_matches) / len(REQUIRED_SKILLS)) * 70
    else:
        skill_score = 0
        
    return round(edu_score + skill_score, 2)

def send_email(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        return False

# --- STREAMLIT UI ---
st.set_page_config(page_title="Bulk Resume Screener", layout="wide")
st.title("🚀 Bulk Resume Screening & Automation System")

col1, col2 = st.columns(2)
col1.metric("Cutoff Score", f"{CUTOFF_SCORE}%")
col2.metric("Required Skills", len(REQUIRED_SKILLS))

# Sidebar Controls
with st.sidebar:
    st.header("Settings")
    enable_email = st.checkbox("Enable Email Sending", value=False, help="Uncheck this to test without sending real emails")
    st.info("Upload multiple PDFs to start processing.")

# Bulk File Uploader
uploaded_files = st.file_uploader("Upload Resumes (PDF)", type="pdf", accept_multiple_files=True)

if uploaded_files and st.button(f"Process {len(uploaded_files)} Resumes"):
    
    results_data = []
    progress_bar = st.progress(0)
    
    for i, file in enumerate(uploaded_files):
        # 1. Extraction
        text = extract_text_from_pdf(file)
        candidate_email = extract_email_from_text(text)
        score = calculate_score(text)
        file_name = file.name
        
        # 2. Decision
        status = "SELECTED" if score >= CUTOFF_SCORE else "REJECTED"
        
        # 3. Email Automation
        email_sent = "Skipped"
        if enable_email and candidate_email:
            
            # --- OPTION A: IF SELECTED ---
            if status == "SELECTED":
                subj = "Interview Invitation: Data Analyst Role"
                body = f"""
Dear Candidate,

We are pleased to inform you that your resume has been shortlisted for the position. 
Your profile scored {score}%, which aligns well with our requirements.

Our HR team will send you a calendar invitation for the first round of interviews shortly.

Best regards,
The Recruitment Team
"""
                if send_email(candidate_email, subj, body):
                    email_sent = "Sent (Invite)"
                else:
                    email_sent = "Failed"

            # --- OPTION B: IF REJECTED ---
            else:
                subj = "Update on your Job Application"
                body = f"""
Dear Candidate,

Thank you for your interest in our company. 

After carefully reviewing your application, we have decided to move forward with other candidates whose skills more closely match our current needs (Your Score: {score}%).

We will keep your resume in our database for future opportunities.

Best regards,
The Recruitment Team
"""
                if send_email(candidate_email, subj, body):
                    email_sent = "Sent (Reject)"
                else:
                    email_sent = "Failed"
        elif enable_email and not candidate_email:
             email_sent = "No Email Found in PDF"

        # 4. Store Data
        results_data.append({
            "Filename": file_name,
            "Email Extracted": candidate_email,
            "Score": score,
            "Status": status,
            "Email Status": email_sent
        })
        
        # Update progress bar
        progress_bar.progress((i + 1) / len(uploaded_files))

    # --- RESULTS DASHBOARD ---
    st.success("Processing Complete!")
    
    # Create DataFrame
    df = pd.DataFrame(results_data)
    
    # 1. Visuals
    st.subheader("📊 Analysis Dashboard")
    colA, colB = st.columns(2)
    
    with colA:
        st.caption("Selection Ratio")
        # FIXED: Removed the 'color' argument to prevent the crash
        status_counts = df['Status'].value_counts()
        st.bar_chart(status_counts)

    with colB:
        st.caption("Score Distribution")
        # FIXED: Indentation is now correct
        st.bar_chart(df.set_index('Filename')['Score'])

    # 2. Detailed Data Table
    st.subheader("📋 Candidate Details")
    
    # Highlight logic for the table
    def color_status(val):
        color = 'green' if val == 'SELECTED' else 'red'
        return f'color: {color}; font-weight: bold'

    st.dataframe(df.style.map(color_status, subset=['Status']), use_container_width=True)
    
    # Option to download results
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download Report (CSV)", csv, "hiring_report.csv", "text/csv")

elif not uploaded_files:
    st.info("Waiting for PDF uploads...")