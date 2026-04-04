import os
import re
import zipfile
import shutil
import fitz  # PyMuPDF
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
from flask import Flask, request, render_template, send_file
import multiprocessing
from datetime import datetime

app = Flask(__name__, template_folder='.')

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
TEMP_FOLDER = "temp_resumes"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# lazily loaded SpaCy NLP pipeline for Name extraction to prevent heavy OS overhead per worker
NLP = None

def get_nlp():
    global NLP
    if NLP is None:
        import spacy
        NLP = spacy.load("en_core_web_sm")
    return NLP


# ==========================================
# PRE-COMPILED REGEX PIPELINE for HIGH SPEED
# ==========================================

FINAL_HEADERS = [
    "S.No", "Date", "Recruiter Name", "JD ID", "Client Name", "Job Role ", "IT/Non IT", 
    "Source", "Candidate Name", "Mr./Ms./Mrs", "Gender", "Candidate Contact Number", "Email", 
    "Calls Handled By", "Candidate Response", "Total Year Of Experience", "Relevant Year Of Experience", 
    "Current_CTC", "Expected CTC", "Notice Period", "Current_Location", "State", "Preferred Location ", 
    "Willing to Relocate", "Job Type", "Languages Known", "Current Company", "Years Worked in Current Company", 
    "Undergraduate Degree", "Postgraduate Degree", "Skills", "Birth Year", "Age", "System Age", "Level", 
    "Communication Rating", "Remarks", "Recruiter Remarks"
]

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
PHONE_REGEX = re.compile(r'\+?\d[\d\s\-\(\)]{8,20}\d')

EXP_REGEX = re.compile(r'\b(\d{1,2}(?:\.\d{1,2})?)\s*(?:\+?\s*)?(?:years?|yrs?|y)\b.*?(?:of)?\s*(?:exp(?:erience)?)\b', re.IGNORECASE)
DOB_REGEX = re.compile(r'(?:DOB|Date of[ \-]Birth)\s*[:\-]?\s*([\d]{1,2}[/\-\.][\d]{1,2}[/\-\.]([\d]{2,4}))', re.IGNORECASE)

NP_REGEX = re.compile(r'(?:Notice Period|NP)\s*[:\-]?\s*(\d{1,2}\s*(?:days?|months?|weeks?)|Immediate(?:ly)?)', re.IGNORECASE)
CTC_REGEX = re.compile(r'(?:Current CTC|CTC)\s*[:\-]?\s*([\d\.]+\s*(?:LPA|L|lakhs?|Lacs?|k|K))', re.IGNORECASE)
ECTC_REGEX = re.compile(r'(?:Expected CTC|ECTC)\s*[:\-]?\s*([\d\.]+\s*(?:LPA|L|lakhs?|Lacs?|k|K))', re.IGNORECASE)

UG_REGEX = re.compile(r'\b(B\.?E\.?|B\.?Tech|B\.?Sc\.?|B\.?Com\.?|B\.?B\.?A\.?|B\.?C\.?A\.?|B\.?A\.?|Bachelor(?:s|' + r"'" + r's)?\s*(?:of)?\s*(?:Engineering|Technology|Science|Commerce|Arts|Business|Computer))\b', re.IGNORECASE)
PG_REGEX = re.compile(r'\b(M\.?E\.?|M\.?Tech|M\.?Sc\.?|MBA|M\.?C\.?A\.?|M\.?A\.?|Master(?:s|' + r"'" + r's)?\s*(?:of)?\s*(?:Engineering|Technology|Science|Commerce|Arts|Business|Computer|Business Administration))\b', re.IGNORECASE)

INDIAN_CITIES = {
    "mumbai": "Maharashtra", "pune": "Maharashtra", "nagpur": "Maharashtra", "nashik": "Maharashtra",
    "delhi": "Delhi", "new delhi": "Delhi",
    "bangalore": "Karnataka", "bengaluru": "Karnataka", "mysore": "Karnataka",
    "hyderabad": "Telangana", "secunderabad": "Telangana",
    "chennai": "Tamil Nadu", "coimbatore": "Tamil Nadu", "madurai": "Tamil Nadu",
    "kolkata": "West Bengal",
    "ahmedabad": "Gujarat", "surat": "Gujarat", "vadodara": "Gujarat",
    "noida": "Uttar Pradesh", "lucknow": "Uttar Pradesh", "kanpur": "Uttar Pradesh",
    "gurgaon": "Haryana", "gurugram": "Haryana",
    "jaipur": "Rajasthan",
    "bhubaneswar": "Odisha",
    "kochi": "Kerala", "trivandrum": "Kerala", "thiruvananthapuram": "Kerala"
}

LANGUAGES = ["English", "Hindi", "Tamil", "Telugu", "Marathi", "Kannada", "Malayalam", "Gujarati", "Bengali", "Punjabi", "Urdu", "French", "German", "Spanish"]
LANG_REGEX = re.compile(r'\b(' + '|'.join(LANGUAGES) + r')\b', re.IGNORECASE)

# Skill Dictionary mapped to Canonical Names (Resolves Synonym Edge Cases)
SKILL_ALIASES = {
    "javascript": "JavaScript", "js": "JavaScript",
    "typescript": "TypeScript", "ts": "TypeScript",
    "react": "React", "react.js": "React", "reactjs": "React",
    "node.js": "Node.js", "nodejs": "Node.js", "node": "Node.js",
    "vue": "Vue.js", "vue.js": "Vue.js", "vuejs": "Vue.js",
    "angular": "Angular", "angularjs": "Angular",
    "next.js": "Next.js", "nextjs": "Next.js",
    "express": "Express", "express.js": "Express", "expressjs": "Express",
    "jquery": "jQuery",
    "c++": "C++", "cpp": "C++", 
    "c#": "C#", "c-sharp": "C#", "csharp": "C#",
    "machine learning": "Machine Learning", "ml": "Machine Learning",
    "deep learning": "Deep Learning", "dl": "Deep Learning",
    "artificial intelligence": "AI", "ai": "AI",
    "nlp": "NLP", "natural language processing": "NLP",
    "computer vision": "Computer Vision", 
    "aws": "AWS", "amazon web services": "AWS",
    "gcp": "GCP", "google cloud": "GCP",
    "azure": "Azure", "microsoft azure": "Azure",
    "sql": "SQL", "mysql": "MySQL", "postgresql": "PostgreSQL", "postgres": "PostgreSQL",
    "nosql": "NoSQL", "mongodb": "MongoDB", "mongo": "MongoDB", "sqlite": "SQLite", "redis": "Redis",
    "docker": "Docker", 
    "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "ci/cd": "CI/CD", "cicd": "CI/CD", "jenkins": "Jenkins", "terraform": "Terraform",
    "git": "Git", "github": "GitHub", "gitlab": "GitLab",
    "linux": "Linux", "unix": "Unix", "bash": "Bash",
    "python": "Python", 
    "pandas": "Pandas", "numpy": "NumPy", "scikit-learn": "Scikit-Learn", "sklearn": "Scikit-Learn",
    "pytorch": "PyTorch", "tensorflow": "TensorFlow", "keras": "Keras", "matplotlib": "Matplotlib",
    "java": "Java", "spring": "Spring", "spring boot": "Spring Boot",
    "ruby": "Ruby", "ruby on rails": "Ruby on Rails", "rails": "Ruby on Rails",
    "php": "PHP", "laravel": "Laravel",
    "go": "Go", "golang": "Go",
    "rust": "Rust", "swift": "Swift", "kotlin": "Kotlin", "dart": "Dart",
    "html": "HTML", "css": "CSS", "bootstrap": "Bootstrap", "tailwind": "Tailwind"
}
STRICT_C_SKILLS = {"C": "C", "R": "R"}
SORTED_ALIASES = sorted(list(SKILL_ALIASES.keys()), key=len, reverse=True)
SKILL_PATTERN = re.compile(r'\b(' + '|'.join(re.escape(s) for s in SORTED_ALIASES) + r')\b', re.IGNORECASE)
STRICT_PATTERN = re.compile(r'\b(C|R)\b')


def unzip_file(zip_path, extract_to=TEMP_FOLDER):
    if os.path.exists(extract_to):
        shutil.rmtree(extract_to)
    os.makedirs(extract_to, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
    except zipfile.BadZipFile:
        return None
    return extract_to


def get_files(folder):
    files = []
    for root, _, filenames in os.walk(folder):
        for f in filenames:
            f_lower = f.lower()
            if f_lower.endswith(".pdf") or f_lower.endswith(".docx"):
                files.append(os.path.join(root, f))
    return files


def extract_pdf_data(file_path):
    text = ""
    hidden_emails = []
    try:
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
            for link in page.get_links():
                uri = link.get("uri", "")
                if uri and uri.lower().startswith("mailto:"):
                    hidden_emails.append(uri[7:].strip())
        doc.close()
    except Exception:
        pass
    return text, hidden_emails


def extract_docx_data(file_path):
    text = ""
    try:
        import docx
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    except Exception:
        pass
    return text, []


def parse_text(text, hidden_emails):
    # Initialize all default empty values
    data = {k: "" for k in FINAL_HEADERS}
    
    if not text:
        return data

    # 1. EMail
    emails = EMAIL_REGEX.findall(text)
    if emails:
        data["Email"] = emails[0]
    elif hidden_emails:
        data["Email"] = hidden_emails[0]

    # 2. Phone
    phones = PHONE_REGEX.findall(text)
    for p in phones:
        digits = re.sub(r'\D', '', p)
        if len(digits) == 10 and digits[0] in "6789":
            data["Candidate Contact Number"] = p.strip(); break
        elif len(digits) == 11 and digits.startswith("0") and digits[1] in "6789":
            data["Candidate Contact Number"] = p.strip(); break
        elif len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
            data["Candidate Contact Number"] = p.strip(); break

    # 3. Skills
    found_skills = set()
    for match in SKILL_PATTERN.finditer(text):
        token = match.group(1).lower()
        if token in SKILL_ALIASES:
            found_skills.add(SKILL_ALIASES[token])
    for match in STRICT_PATTERN.finditer(text): 
        token = match.group(1)
        if token in STRICT_C_SKILLS:
            found_skills.add(STRICT_C_SKILLS[token])
    data["Skills"] = ", ".join(sorted(list(found_skills)))

    # 4. Name
    name = ""
    doc_text = "\n".join([line.strip() for line in text.split("\n")][:25])
    doc_text = doc_text[:600]
    try:
        nlp = get_nlp()
        nlp_doc = nlp(doc_text)
        for ent in nlp_doc.ents:
            if ent.label_ == "PERSON":
                if len(ent.text.strip()) > 2 and "\n" not in ent.text:
                    name = ent.text.strip().title()
                    break
    except Exception:
        pass
    if not name:
        ignore_words = {"resume", "curriculum vitae", "cv", "page", "email", "phone", "profile", "summary"}
        for line in doc_text.split("\n"):
            line_lower = line.lower()
            if any(w in line_lower for w in ignore_words) or "@" in line or len(line) < 3 or len(line) > 60:
                continue
            if re.match(r"^[A-Za-z\s\.\-']+$", line):
                if line.isupper() or line.istitle() or len(line.split()) >= 2:
                    name = line.title()
                    break
    data["Candidate Name"] = name

    # 5. Experience
    exp_matches = EXP_REGEX.search(text)
    if exp_matches:
        data["Total Year Of Experience"] = exp_matches.group(1)

    # 6. Location and State
    text_lower_head = doc_text.lower() # search in top part
    for city, state in INDIAN_CITIES.items():
        if re.search(r'\b' + re.escape(city) + r'\b', text_lower_head):
            data["Current_Location"] = city.title()
            data["State"] = state
            break

    # 7. Known Languages
    found_langs = set()
    for match in LANG_REGEX.finditer(text):
        found_langs.add(match.group(1).title())
    if found_langs:
        data["Languages Known"] = ", ".join(sorted(list(found_langs)))

    # 8. Degrees
    ug_match = UG_REGEX.search(text)
    if ug_match:
        data["Undergraduate Degree"] = ug_match.group(1).strip()
    
    pg_match = PG_REGEX.search(text)
    if pg_match:
        data["Postgraduate Degree"] = pg_match.group(1).strip()

    # 9. Notice Period & CTC
    np_match = NP_REGEX.search(text)
    if np_match:
        data["Notice Period"] = np_match.group(1).strip()
    
    ctc_match = CTC_REGEX.search(text)
    if ctc_match:
        data["Current_CTC"] = ctc_match.group(1).strip()
    
    ectc_match = ECTC_REGEX.search(text)
    if ectc_match:
        data["Expected CTC"] = ectc_match.group(1).strip()

    # 10. Birth Year and Age
    dob_match = DOB_REGEX.search(text)
    if dob_match:
        year_str = dob_match.group(2)
        if len(year_str) == 2:
            year = int("19" + year_str) if int(year_str) > 30 else int("20" + year_str)
        else:
            year = int(year_str)
        data["Birth Year"] = str(year)
        data["Age"] = str(datetime.now().year - year)

    # 11. Gender
    if re.search(r'\b(?:Male|Female)\b', text, re.IGNORECASE):
        m = re.search(r'\b(Male|Female)\b', text, re.IGNORECASE)
        data["Gender"] = m.group(1).title()

    # 12. Current Company Heuristic
    # Look for "Experience" or "Work Experience" section
    exp_idx = re.search(r'\b(?:Experience|Employment History|Work Experience)\b', text, re.IGNORECASE)
    if exp_idx:
        # Check text right after it
        post_exp_text = text[exp_idx.end():exp_idx.end() + 1000]
        try:
            nlp = get_nlp()
            nlp_doc = nlp(post_exp_text)
            for ent in nlp_doc.ents:
                if ent.label_ == "ORG":
                    # Avoid common false positives
                    if ent.text.lower() not in ['school', 'college', 'university', 'institute']:
                        org_name = ent.text.strip().replace("\n", " ")
                        if len(org_name) > 3:
                            data["Current Company"] = org_name
                            break
        except Exception:
            pass

    return data


def process_file(file_path):
    file_name = os.path.basename(file_path)
    try:
        if file_path.lower().endswith(".docx"):
            text, hidden_emails = extract_docx_data(file_path)
        else:
            text, hidden_emails = extract_pdf_data(file_path)
            
        res = parse_text(text, hidden_emails)
        res['File Name'] = file_name
        return res
    except Exception:
        # Return empty data with just the file name
        res = {k: "" for k in FINAL_HEADERS}
        res['File Name'] = file_name
        res['Candidate Name'] = "Error Extracting"
        return res


def process_all(files):
    if not files:
        return []

    workers = min(32, multiprocessing.cpu_count() * 2)
    chunk_sz = max(1, len(files) // workers)
    
    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(process_file, files, chunksize=chunk_sz))
        
    return results


# ==========================================
# WEB UI & ROUTES
# ==========================================

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "zipfile" not in request.files:
            return "No file uploaded", 400
            
        file = request.files["zipfile"]
        if file.filename == "":
            return "No file selected", 400

        zip_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(zip_path)

        try:
            folder = unzip_file(zip_path)
            if not folder:
                return "Invalid ZIP file format.", 400

            files = get_files(folder)
            results = process_all(files)

            if results:
                df = pd.DataFrame(results)[FINAL_HEADERS]
            else:
                df = pd.DataFrame(columns=FINAL_HEADERS)

            output_file = os.path.join(OUTPUT_FOLDER, "processed_resumes.xlsx")
            df.to_excel(output_file, index=False)

            shutil.rmtree(folder, ignore_errors=True)
            if os.path.exists(zip_path):
                os.remove(zip_path)

            return send_file(output_file, as_attachment=True)
            
        except Exception as e:
            return f"An error occurred during processing: {str(e)}", 500

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)