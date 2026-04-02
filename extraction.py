import os
import re
import zipfile
import shutil
import fitz  # PyMuPDF
import pandas as pd
from concurrent.futures import ProcessPoolExecutor
from flask import Flask, request, render_template, send_file
import multiprocessing

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

# Email pattern matching
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')

# Phone pattern capturing large digit blocks to be validated later
PHONE_REGEX = re.compile(r'\+?\d[\d\s\-\(\)]{8,20}\d')

# Skill Dictionary mapped to Canonical Names (Resolves Synonym Edge Cases)
SKILL_ALIASES = {
    # Variations of JS
    "javascript": "JavaScript", "js": "JavaScript",
    "typescript": "TypeScript", "ts": "TypeScript",
    "react": "React", "react.js": "React", "reactjs": "React",
    "node.js": "Node.js", "nodejs": "Node.js", "node": "Node.js",
    "vue": "Vue.js", "vue.js": "Vue.js", "vuejs": "Vue.js",
    "angular": "Angular", "angularjs": "Angular",
    "next.js": "Next.js", "nextjs": "Next.js",
    "express": "Express", "express.js": "Express", "expressjs": "Express",
    "jquery": "jQuery",

    # Variations of C and C++
    "c++": "C++", "cpp": "C++", 
    "c#": "C#", "c-sharp": "C#", "csharp": "C#",

    # Machine Learning / AI
    "machine learning": "Machine Learning", "ml": "Machine Learning",
    "deep learning": "Deep Learning", "dl": "Deep Learning",
    "artificial intelligence": "AI", "ai": "AI",
    "nlp": "NLP", "natural language processing": "NLP",
    "computer vision": "Computer Vision", 

    # Clouds & DBs
    "aws": "AWS", "amazon web services": "AWS",
    "gcp": "GCP", "google cloud": "GCP",
    "azure": "Azure", "microsoft azure": "Azure",
    "sql": "SQL", "mysql": "MySQL", "postgresql": "PostgreSQL", "postgres": "PostgreSQL",
    "nosql": "NoSQL", "mongodb": "MongoDB", "mongo": "MongoDB", "sqlite": "SQLite", "redis": "Redis",
    
    # Infra & General
    "docker": "Docker", 
    "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "ci/cd": "CI/CD", "cicd": "CI/CD", "jenkins": "Jenkins", "terraform": "Terraform",
    "git": "Git", "github": "GitHub", "gitlab": "GitLab",
    "linux": "Linux", "unix": "Unix", "bash": "Bash",
    
    # Python & Data
    "python": "Python", 
    "pandas": "Pandas", "numpy": "NumPy", "scikit-learn": "Scikit-Learn", "sklearn": "Scikit-Learn",
    "pytorch": "PyTorch", "tensorflow": "TensorFlow", "keras": "Keras", "matplotlib": "Matplotlib",
    
    # Others
    "java": "Java", "spring": "Spring", "spring boot": "Spring Boot",
    "ruby": "Ruby", "ruby on rails": "Ruby on Rails", "rails": "Ruby on Rails",
    "php": "PHP", "laravel": "Laravel",
    "go": "Go", "golang": "Go",
    "rust": "Rust", "swift": "Swift", "kotlin": "Kotlin", "dart": "Dart",
    "html": "HTML", "css": "CSS", "bootstrap": "Bootstrap", "tailwind": "Tailwind"
}

# Single-letter technical skills (C, R) strictly mapped (Case Sensitive)
STRICT_C_SKILLS = {"C": "C", "R": "R"}

# Sorted by length so "machine learning" matches before "learning"
SORTED_ALIASES = sorted(list(SKILL_ALIASES.keys()), key=len, reverse=True)
SKILL_PATTERN = re.compile(r'\b(' + '|'.join(re.escape(s) for s in SORTED_ALIASES) + r')\b', re.IGNORECASE)

# Distinct Case-Sensitive pattern for single letter attributes (prevents "c"" triggering "C")
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
            if f.lower().endswith(".pdf"):
                files.append(os.path.join(root, f))
    return files


def extract_pdf_data(file_path):
    text = ""
    hidden_emails = []
    try:
        doc = fitz.open(file_path)
        for page in doc:
            # 1. Pull Text Layers
            text += page.get_text()
            
            # 2. Extract Hidden Meta-Links for mailto: scenarios
            for link in page.get_links():
                uri = link.get("uri", "")
                if uri and uri.lower().startswith("mailto:"):
                    hidden_emails.append(uri[7:].strip())
                    
        doc.close()
    except Exception:
        pass
    return text, hidden_emails


def parse_text(text, hidden_emails):
    if not text:
        return {"Name": "", "Email": "", "Phone": "", "Skills": ""}

    # 1. EMail Extraction (Regex first, then hidden Links fallback)
    emails = EMAIL_REGEX.findall(text)
    email = emails[0] if emails else ""
    if not email and hidden_emails:
        email = hidden_emails[0]

    # 2. Phone Extraction (Strict Indian Formats)
    phones = PHONE_REGEX.findall(text)
    phone = ""
    for p in phones:
        digits = re.sub(r'\D', '', p)
        # Indian Mobile Standards: Start with 6, 7, 8, or 9
        if len(digits) == 10 and digits[0] in "6789":
            phone = p.strip(); break
        elif len(digits) == 11 and digits.startswith("0") and digits[1] in "6789":
            phone = p.strip(); break
        elif len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
            phone = p.strip(); break

    # 3. Canonical Target Skill Matching 
    found_skills = set()
    # Case Insensitive standard aliases
    for match in SKILL_PATTERN.finditer(text):
        token = match.group(1).lower()
        if token in SKILL_ALIASES:
            found_skills.add(SKILL_ALIASES[token])
            
    # Strict matching (C, R) - Exact case to prevent list bullet triggers
    for match in STRICT_PATTERN.finditer(text): 
        token = match.group(1)
        if token in STRICT_C_SKILLS:
            found_skills.add(STRICT_C_SKILLS[token])
            
    skills_formatted = ", ".join(sorted(list(found_skills)))

    # 4. Hybrid Name Extraction Logic
    name = ""
    
    # Snip the top 600 characters for high-speed ML processing
    doc_text = "\n".join([line.strip() for line in text.split("\n")][:25])
    doc_text = doc_text[:600]
    
    # Engage SpaCy lightweight NLP block
    try:
        nlp = get_nlp()
        nlp_doc = nlp(doc_text)
        for ent in nlp_doc.ents:
            if ent.label_ == "PERSON":
                # Ensure it looks somewhat correct (reject single char anomalies occasionally flagged)
                if len(ent.text.strip()) > 2 and "\n" not in ent.text:
                    name = ent.text.strip().title()
                    break
    except Exception:
        pass
            
    # Fallback heuristic if SpaCy entirely skips due to abstract fonts/caps lock styling
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

    return {
        "Name": name,
        "Email": email,
        "Phone": phone,
        "Skills": skills_formatted
    }


def process_file(file_path):
    file_name = os.path.basename(file_path)
    try:
        text, hidden_emails = extract_pdf_data(file_path)
        res = parse_text(text, hidden_emails)
        res['File Name'] = file_name
        return res
    except Exception:
        return {"File Name": file_name, "Name": "", "Email": "", "Phone": "", "Skills": "Error Extracting"}


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
                df = pd.DataFrame(results)[['File Name', 'Name', 'Email', 'Phone', 'Skills']]
            else:
                df = pd.DataFrame(columns=['File Name', 'Name', 'Email', 'Phone', 'Skills'])

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