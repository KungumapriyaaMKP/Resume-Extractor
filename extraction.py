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
        # Disable unused components for much faster initialization and inference
        NLP = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer", "tagger", "attribute_ruler"])
    return NLP


# ==========================================
# PRE-COMPILED REGEX PIPELINE for HIGH SPEED
# ==========================================

FINAL_HEADERS = [
    "File Name",
    "Candidate Name",
    "Candidate Contact Number",
    "Email",
    "Total Years of Experience",
    "Skills",
    "Current Company",
    "Previous Companies",
    "Current Location",
    "Education (UG / PG Degree)",
    "Languages Known",
    "Years Worked in Current Company"
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
    # Top Cities
    "mumbai": "Maharashtra", "delhi": "Delhi", "bengaluru": "Karnataka", "ahmedabad": "Gujarat", "hyderabad": "Telangana", "chennai": "Tamil Nadu", "kolkata": "West Bengal", "pune": "Maharashtra", "jaipur": "Rajasthan", "surat": "Gujarat", "lucknow": "Uttar Pradesh", "kanpur": "Uttar Pradesh", "nagpur": "Maharashtra", "patna": "Bihar", "indore": "Madhya Pradesh", "thane": "Maharashtra", "bhopal": "Madhya Pradesh", "visakhapatnam": "Andhra Pradesh", "vadodara": "Gujarat", "firozabad": "Uttar Pradesh", "ludhiana": "Punjab", "rajkot": "Gujarat", "agra": "Uttar Pradesh", "siliguri": "West Bengal", "nashik": "Maharashtra", "faridabad": "Haryana", "patiala": "Punjab", "meerut": "Uttar Pradesh", "kalyan": "Maharashtra", "dombivali": "Maharashtra", "vasai": "Maharashtra", "virar": "Maharashtra", "varanasi": "Uttar Pradesh", "srinagar": "Jammu and Kashmir", "dhanbad": "Jharkhand", "jodhpur": "Rajasthan", "amritsar": "Punjab", "raipur": "Chhattisgarh", "allahabad": "Uttar Pradesh", "coimbatore": "Tamil Nadu", "jabalpur": "Madhya Pradesh", "gwalior": "Madhya Pradesh", "vijayawada": "Andhra Pradesh", "madurai": "Tamil Nadu", "guwahati": "Assam", "chandigarh": "Chandigarh", "hubli": "Karnataka", "dharwad": "Karnataka", "amroha": "Uttar Pradesh", "moradabad": "Uttar Pradesh", "gurgaon": "Haryana", "gurugram": "Haryana", "aligarh": "Uttar Pradesh", "solapur": "Maharashtra", "ranchi": "Jharkhand", "jalandhar": "Punjab", "tiruchirappalli": "Tamil Nadu", "bhubaneswar": "Odisha", "salem": "Tamil Nadu", "warangal": "Telangana", "thiruvananthapuram": "Kerala", "bhiwandi": "Maharashtra", "saharanpur": "Uttar Pradesh", "guntur": "Andhra Pradesh", "amravati": "Maharashtra", "bikaner": "Rajasthan", "noida": "Uttar Pradesh", "jamshedpur": "Jharkhand", "bhilai": "Chhattisgarh", "cuttack": "Odisha", "kochi": "Kerala", "udaipur": "Rajasthan", "bhavnagar": "Gujarat", "dehradun": "Uttarakhand", "asansol": "West Bengal", "nanded": "Maharashtra", "ajmer": "Rajasthan", "jamnagar": "Gujarat", "ujjain": "Madhya Pradesh", "sangli": "Maharashtra", "loni": "Uttar Pradesh", "jhansi": "Uttar Pradesh", "pondicherry": "Puducherry", "puducherry": "Puducherry", "nellore": "Andhra Pradesh", "jammu": "Jammu and Kashmir", "belagavi": "Karnataka", "belgaum": "Karnataka", "raurkela": "Odisha", "mangaluru": "Karnataka", "mangalore": "Karnataka", "tirunelveli": "Tamil Nadu", "malegaon": "Maharashtra", "gaya": "Bihar", "tiruppur": "Tamil Nadu", "davanagere": "Karnataka", "kozhikode": "Kerala", "akola": "Maharashtra", "kurnool": "Andhra Pradesh", "bokaro": "Jharkhand", "rajahmundry": "Andhra Pradesh", "ballari": "Karnataka", "bellary": "Karnataka", "agartala": "Tripura", "bhagalpur": "Bihar", "latur": "Maharashtra", "dhule": "Maharashtra", "korba": "Chhattisgarh", "bhilwara": "Rajasthan", "brahmapur": "Odisha", "mysore": "Karnataka", "mysuru": "Karnataka", "muzaffarpur": "Bihar", "ahmednagar": "Maharashtra", "kollam": "Kerala", "raghunathganj": "West Bengal", "bilaspur": "Chhattisgarh", "shahjahanpur": "Uttar Pradesh", "thrissur": "Kerala", "alwar": "Rajasthan", "kakinada": "Andhra Pradesh", "nizamabad": "Telangana", "sagar": "Madhya Pradesh", "tumkur": "Karnataka", "hisar": "Haryana", "rohtak": "Haryana", "panipat": "Haryana", "darbhanga": "Bihar", "kharagpur": "West Bengal", "aizawl": "Mizoram", "ichalkaranji": "Maharashtra", "tirupati": "Andhra Pradesh", "karnal": "Haryana", "bathinda": "Punjab", "rampur": "Uttar Pradesh", "shivamogga": "Karnataka", "ratlam": "Madhya Pradesh", "modinagar": "Uttar Pradesh", "durg": "Chhattisgarh", "shillong": "Meghalaya", "imphal": "Manipur", "hapur": "Uttar Pradesh", "ranipet": "Tamil Nadu", "anantapur": "Andhra Pradesh", "arrah": "Bihar", "karimnagar": "Telangana", "parbhani": "Maharashtra", "etawah": "Uttar Pradesh", "bharatpur": "Rajasthan", "begusarai": "Bihar", "new delhi": "Delhi", "chhapra": "Bihar", "kadapa": "Andhra Pradesh", "ramagundam": "Telangana", "pali": "Rajasthan", "satna": "Madhya Pradesh", "vizianagaram": "Andhra Pradesh", "katihar": "Bihar", "hardwar": "Uttarakhand", "haridwar": "Uttarakhand", "sonipat": "Haryana", "nagercoil": "Tamil Nadu", "thanjavur": "Tamil Nadu", "katni": "Madhya Pradesh", "naihati": "West Bengal", "sambhal": "Uttar Pradesh", "nadiad": "Gujarat", "yamunanagar": "Haryana", "secunderabad": "Telangana"
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


def sanitize_filename(filename):
    # Remove extension and clean characters for Excel/Windows safety
    name = os.path.splitext(filename)[0]
    # Replace common resume junk with spaces
    name = re.sub(r'(_| - | -|-|Resume|CV|Curriculum Vitae)', ' ', name, flags=re.IGNORECASE)
    # Remove any extra characters that match regex, keeping letters and spaces
    name = re.sub(r'[^A-Za-z\s\.]', '', name)
    return ' '.join(name.split()).title()

def get_files(folder):
    files = []
    valid_extensions = (".pdf", ".docx")
    for root, _, filenames in os.walk(folder):
        for f in filenames:
            if f.lower().endswith(valid_extensions) and not f.startswith("~$"):
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
    # Initialize all default empty values with a professional placeholder
    data = {k: "Not Provided" for k in FINAL_HEADERS}
    
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
        # Fallback to filename if no name found in text
        name = sanitize_filename(data.get('File Name', ''))
        if not name or len(name) < 2:
            name = "Not Provided"
    
    data["Candidate Name"] = name.strip().title() if name != "Not Provided" else "Not Provided"

    # 5. Experience
    exp_matches = EXP_REGEX.search(text)
    if exp_matches:
        data["Total Years of Experience"] = exp_matches.group(1)

    # 6. Location
    text_lower_head = doc_text.lower()
    for city, state in INDIAN_CITIES.items():
        if re.search(r'\b' + re.escape(city) + r'\b', text_lower_head):
            data["Current Location"] = city.title()
            break

    # 7. Known Languages
    found_langs = set()
    for match in LANG_REGEX.finditer(text):
        found_langs.add(match.group(1).title())
    if found_langs:
        data["Languages Known"] = ", ".join(sorted(list(found_langs)))

    # 8. Degrees
    degrees = []
    ug_match = UG_REGEX.search(text)
    if ug_match:
        degrees.append(ug_match.group(1).strip())
    pg_match = PG_REGEX.search(text)
    if pg_match:
        degrees.append(pg_match.group(1).strip())
    if degrees:
        data["Education (UG / PG Degree)"] = " / ".join(degrees)

    # 9. Companies & Years Worked in Current Company
    exp_idx = re.search(r'\b(?:Experience|Employment History|Work Experience)\b', text, re.IGNORECASE)
    if exp_idx:
        post_exp_text = text[exp_idx.end():exp_idx.end() + 1500]

        # Calculate Years Worked in Current Company
        # Match year ranges: "Jan 2018 - 2022", "2021 to Present"
        date_pattern = r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?[a-z]*[\s\,]*\d{4})\s*(?:-|–|to)\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?[a-z]*[\s\,]*\d{4}|Present|Current|Till Date|Today)'
        first_date_range = re.search(date_pattern, post_exp_text, re.IGNORECASE)
        if first_date_range:
            start_str, end_str = first_date_range.groups()
            start_yr_match = re.search(r'(\d{4})', start_str)
            end_yr_match = re.search(r'(\d{4})', end_str)

            if start_yr_match:
                start_yr = int(start_yr_match.group(1))
                if re.search(r'Present|Current|Till|Today', end_str, re.IGNORECASE):
                    end_yr = datetime.now().year
                elif end_yr_match:
                    end_yr = int(end_yr_match.group(1))
                else:
                    end_yr = start_yr
                
                yr_diff = end_yr - start_yr
                if yr_diff == 0:
                    data["Years Worked in Current Company"] = "< 1 Year"
                elif 0 < yr_diff < 40:
                    data["Years Worked in Current Company"] = f"{yr_diff} Years"

        # Find Current and Previous Companies
        try:
            nlp = get_nlp()
            nlp_doc = nlp(post_exp_text)
            orgs = []
            
            ignore_orgs = {'school', 'college', 'university', 'institute', 'pvt ltd', 'private limited', 'inc', 'llc'}
            for ent in nlp_doc.ents:
                if ent.label_ == "ORG":
                    org_name = ent.text.strip().replace("\n", " ")
                    if len(org_name) > 3 and org_name.lower() not in ignore_orgs:
                        if org_name not in orgs:
                            orgs.append(org_name)
            
            if orgs:
                data["Current Company"] = orgs[0]
            if len(orgs) > 1:
                data["Previous Companies"] = ", ".join(orgs[1:4])
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
        
        # Last check - if name is still empty, use sanitized file name
        if res.get('Candidate Name') == "Not Provided":
            res['Candidate Name'] = sanitize_filename(file_name)
            
        return res
    except Exception:
        # Return empty data with just the file name
        res = {k: "Not Provided" for k in FINAL_HEADERS}
        res['File Name'] = file_name
        res['Candidate Name'] = "Error Extracting"
        return res


def process_all(files):
    if not files:
        return []

    # Limit workers to physical cores to avoid thrashing RAM/CPU with too many SpaCy instances
    workers = min(4, multiprocessing.cpu_count())
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

            # Apply neat styling to match requested layout
            from openpyxl import load_workbook
            from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
            from openpyxl.utils import get_column_letter

            wb = load_workbook(output_file)
            ws = wb.active

            header_fill = PatternFill(start_color="1B5586", end_color="1B5586", fill_type="solid")
            header_font = Font(color="FFFFFF", bold=True)
            center_align = Alignment(horizontal="center", vertical="center")
            
            thin_border = Border(
                left=Side(style='thin', color='000000'),
                right=Side(style='thin', color='000000'),
                top=Side(style='thin', color='000000'),
                bottom=Side(style='thin', color='000000')
            )

            # Format Headers
            for col_num, cell in enumerate(ws[1], 1):
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = center_align
                cell.border = thin_border
                
                # Auto-adjust width (roughly)
                col_letter = get_column_letter(col_num)
                ws.column_dimensions[col_letter].width = 26

            # Format Data rows (borders & alternating colors)
            stripe_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=ws.max_column), 2):
                for cell in row:
                    cell.border = thin_border
                    cell.alignment = Alignment(vertical="center", wrap_text=True)
                    if row_idx % 2 == 0:
                        cell.fill = stripe_fill

            wb.save(output_file)

            shutil.rmtree(folder, ignore_errors=True)
            if os.path.exists(zip_path):
                os.remove(zip_path)

            return send_file(output_file, as_attachment=True)
            
        except Exception as e:
            return f"An error occurred during processing: {str(e)}", 500

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)