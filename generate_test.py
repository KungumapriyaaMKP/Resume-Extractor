import fitz
import os
import zipfile
import shutil

TEST_DIR = 'temp_test_resumes'
os.makedirs(TEST_DIR, exist_ok=True)

resumes = [
    {
        "filename": "1_standard_good.pdf",
        "text": "Ananya Sharma\nContact: 9876543210  |  ananya.sharma@example.com\n\nProfile\nSoftware Engineer with experience in Python and Machine Learning.\n\nSkills\n- Python\n- React\n- Node.js\n- Docker"
    },
    {
        "filename": "2_spacing_phone_hidden_email.pdf",
        "text": "Profile Summary\nSeeking a challenging role in backend development.\n\nSuresh Patel\nEmail: Click here to contact me\nMobile: 98765 43210\n\nExperience\nExpert in C++, Java, and SQL Database optimization.\n\nSkills: C++, Java, SQL",
        "mailto": "suresh.p@hidden-email.com"
    },
    {
        "filename": "3_dates_and_false_positives.pdf",
        "text": "Rohan Kumar\nrohan@domain.com\n\nWork Experience: 2018 - 2024\nGithub Repo ID: 2024823924\nPhone: +91 88888 88888\n\nSkills: \nA. Backend\nB. Frontend\nC. Infrastructure\n\nTools: AWS, kubernetes, c++\nWe use machine learning heavily."
    },
    {
        "filename": "4_complex_name_alias.pdf",
        "text": "Venkata Sai Krishna\nvenkata.sai@email.net\nMobile: 09876543211\n\nSkills Summary\nProficiency in JS, reactjs, and K8s.\nMachine learning models deployed via Azure."
    },
    {
        "filename": "5_missing_data.pdf",
        "text": "Secret Developer\nI do not share my phone or email due to privacy.\n\nSkills: Ruby on Rails, HTML, CSS"
    }
]

pdf_files = []

for r in resumes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(fitz.Point(50, 72), r["text"], fontsize=12)
    
    # Inject hidden mailto if exists
    if "mailto" in r:
        rect = fitz.Rect(50, 90, 200, 110)
        link = {"kind": fitz.LINK_URI, "from": rect, "uri": "mailto:" + r["mailto"]}
        page.insert_link(link)
        
    filepath = os.path.join(TEST_DIR, r["filename"])
    doc.save(filepath)
    doc.close()
    pdf_files.append(filepath)

# Zip them up
zip_filepath = "test_resumes.zip"
with zipfile.ZipFile(zip_filepath, 'w') as zipf:
    for f in pdf_files:
        zipf.write(f, os.path.basename(f))
        
shutil.rmtree(TEST_DIR)
print(f"Successfully generated {zip_filepath}!")
