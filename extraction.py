import os
import re
import zipfile
import shutil
import fitz  # PyMuPDF
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, render_template, send_file
from flask_cors import CORS
import multiprocessing
from datetime import datetime

app = Flask(__name__, template_folder='.')
CORS(app)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
TEMP_FOLDER = "temp_resumes"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# No AI Model Needed - Pure Regex for Ultimate Speed
NLP = None
def get_nlp(): return None


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
PHONE_REGEX = re.compile(r'(?:\+?\d[\d\s\-\(\)]{8,20}\d|\(\d{3}\)\s*\d{3}-\d{4})')

EXP_REGEX = re.compile(r'\b(\d{1,2}(?:\.\d{1,2})?)\s*(?:\+?\s*)?(?:years?|yrs?|y)\b.*?(?:of)?\s*(?:exp(?:erience)?)\b', re.IGNORECASE)
DOB_REGEX = re.compile(r'(?:DOB|Date of[ \-]Birth)\s*[:\-]?\s*([\d]{1,2}[/\-\.][\d]{1,2}[/\-\.]([\d]{2,4}))', re.IGNORECASE)

NP_REGEX = re.compile(r'(?:Notice Period|NP)\s*[:\-]?\s*(\d{1,2}\s*(?:days?|months?|weeks?)|Immediate(?:ly)?)', re.IGNORECASE)
CTC_REGEX = re.compile(r'(?:Current CTC|CTC)\s*[:\-]?\s*([\d\.]+\s*(?:LPA|L|lakhs?|Lacs?|k|K))', re.IGNORECASE)
ECTC_REGEX = re.compile(r'(?:Expected CTC|ECTC)\s*[:\-]?\s*([\d\.]+\s*(?:LPA|L|lakhs?|Lacs?|k|K))', re.IGNORECASE)

UG_REGEX = re.compile(r'\b(B\.?E\.?|B\.?Tech|B\.?Sc\.?|B\.?Com\.?|B\.?B\.?A\.?|B\.?C\.?A\.?|B\.?A\.?|Bachelor(?:s|' + r"'" + r's)?\s*(?:of)?\s*(?:Engineering|Technology|Science|Commerce|Arts|Business|Computer))\b', re.IGNORECASE)
PG_REGEX = re.compile(r'\b(M\.?E\.?|M\.?Tech|M\.?Sc\.?|MBA|M\.?C\.?A\.?|M\.?A\.?|Master(?:s|' + r"'" + r's)?\s*(?:of)?\s*(?:Engineering|Technology|Science|Commerce|Arts|Business|Computer|Business Administration))\b', re.IGNORECASE)

# Extended City and Location list for Indian & Global candidates
INDIAN_CITIES = {
    'mumbai': 'Mumbai', 'delhi': 'Delhi', 'bangalore': 'Bangalore', 'bengaluru': 'Bangalore', 'hyderabad': 'Hyderabad', 'ahmedabad': 'Ahmedabad',
    'chennai': 'Chennai', 'kolkata': 'Kolkata', 'surat': 'Surat', 'pune': 'Pune', 'jaipur': 'Jaipur', 'lucknow': 'Lucknow',
    'kanpur': 'Kanpur', 'nagpur': 'Nagpur', 'indore': 'Indore', 'thane': 'Thane', 'bhopal': 'Bhopal', 'visakhapatnam': 'Visakhapatnam',
    'pimpri': 'Pimpri', 'patna': 'Patna', 'vadodara': 'Vadodara', 'ghaziabad': 'Ghaziabad', 'ludhiana': 'Ludhiana', 'agra': 'Agra',
    'nashik': 'Nashik', 'faridabad': 'Faridabad', 'meerut': 'Meerut', 'rajkot': 'Rajkot', 'kalyan': 'Kalyan', 'vasai': 'Vasai',
    'varanasi': 'Varanasi', 'srinagar': 'Srinagar', 'aurangabad': 'Aurangabad', 'dhanbad': 'Dhanbad', 'amritsar': 'Amritsar',
    'navi mumbai': 'Navi Mumbai', 'allahabad': 'Allahabad', 'howrah': 'Howrah', 'gwalior': 'Gwalior', 'jabalpur': 'Jabalpur',
    'coimbatore': 'Coimbatore', 'vijayawada': 'Vijayawada', 'jodhpur': 'Jodhpur', 'madurai': 'Madurai', 'raipur': 'Raipur',
    'kota': 'Kota', 'chandigarh': 'Chandigarh', 'guwahati': 'Guwahati', 'solapur': 'Solapur', 'hubli': 'Hubli', 'bareilly': 'Bareilly',
    'moradabad': 'Moradabad', 'mysore': 'Mysore', 'gurgaon': 'Gurgaon', 'gurugram': 'Gurugram', 'noida': 'Noida', 'kochi': 'Kochi',
    'thiruvananthapuram': 'Thiruvananthapuram', 'bhubaneswar': 'Bhubaneswar', 'salem': 'Salem', 'warangal': 'Warangal', 'guntur': 'Guntur',
    'bhiwandi': 'Bhiwandi', 'saharanpur': 'Saharanpur', 'amravati': 'Amravati', 'bikaner': 'Bikaner', 'nanded': 'Nanded', 'kolhapur': 'Kolhapur',
    'ajmer': 'Ajmer', 'gulbarga': 'Gulbarga', 'jamnagar': 'Jamnagar', 'ujsain': 'Ujjain', 'lonavala': 'Lonavala', 'siliguri': 'Siliguri',
    'erode': 'Erode', 'hosur': 'Hosur', 'tirupur': 'Tirupur', 'vellore': 'Vellore', 'tuticorin': 'Tuticorin', 'nellore': 'Nellore',
    'banaras': 'Varanasi', 'trichy': 'Tiruchirappalli', 'tiruchirappalli': 'Tiruchirappalli', 'prayagraj': 'Allahabad',
    'san francisco': 'San Francisco', 'new york': 'New York', 'london': 'London', 'dubai': 'Dubai', 'singapore': 'Singapore', 'seattle': 'Seattle',
    'austin': 'Austin', 'boston': 'Boston', 'chicago': 'Chicago', 'palo alto': 'Palo Alto', 'mountain view': 'Mountain View',
    'india': 'India', 'usa': 'USA', 'united states': 'USA', 'uk': 'UK', 'united kingdom': 'UK', 'canada': 'Canada', 'australia': 'Australia'
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
    "html": "HTML", "css": "CSS", "bootstrap": "Bootstrap", "tailwind": "Tailwind", "terraform": "Terraform",
    "sap fico": "SAP FICO", "tally": "Tally", "tally erp": "Tally", "gst": "GST", "taxation": "Taxation", 
    "auditing": "Auditing", "financial analysis": "Financial Analysis", "financial modeling": "Financial Modeling",
    "banking": "Banking", "accounting": "Accounting", "ms excel": "MS Excel", "excel": "MS Excel", "advanced excel": "Advanced Excel",
    "autocad": "AutoCAD", "solidworks": "SolidWorks", "catia": "CATIA", "pro-e": "Pro-E", "proe": "Pro-E", 
    "gd&t": "GD&T", "gdt": "GD&T", "lean manufacturing": "Lean Manufacturing", "six sigma": "Six Sigma",
    "staad pro": "STAAD Pro", "revit": "Revit", "primavera p6": "Primavera P6", "primavera": "Primavera P6", 
    "ms project": "MS Project", "estimation": "Estimation", "quantity surveying": "Quantity Surveying", "is codes": "IS Codes",
    "brand management": "Brand Management", "digital marketing": "Digital Marketing", "market research": "Market Research", 
    "trade marketing": "Trade Marketing", "btl": "BTL Activation", "ms powerpoint": "MS PowerPoint", "google analytics": "Google Analytics",
    "photoshop": "Adobe Photoshop", "illustrator": "Adobe Illustrator", "indesign": "Adobe InDesign", "figma": "Figma", 
    "coreldraw": "CorelDRAW", "premiere pro": "Adobe Premiere Pro", "ui/ux": "UI/UX", "social media creatives": "Social Media Creatives",
    "outbound sales": "Sales", "insurance": "Insurance Products", "lead conversion": "Lead Conversion", "leadsquared": "LeadSquared",
    "negotiation": "Negotiation", "siem": "SIEM", "splunk": "Splunk", "qradar": "QRadar", "threat hunting": "Threat Hunting",
    "incident response": "Incident Response", "vulnerability assessment": "Vulnerability Assessment", "ceh": "CEH Certified",
    "security+": "Security+", "owasp": "OWASP Top 10", "firewall": "Firewall Management", "unity": "Unity 3D",
    "c# scripting": "C# Scripting", "shader graph": "Shader Graph", "photon": "Photon Networking", "agile": "Agile", "scrum": "Scrum",
    "recruitment": "Recruitment & Selection", "payroll": "Payroll Processing", "hrms": "HRMS", "darwinbox": "Darwinbox",
    "onboarding": "Onboarding", "statutory compliance": "Statutory Compliance", "compliance": "Statutory Compliance",
    "employee engagement": "Employee Engagement", "sap hr": "SAP HR"
}
STRICT_C_SKILLS = {"C": "C", "R": "R"}
SORTED_ALIASES = sorted(list(SKILL_ALIASES.keys()), key=len, reverse=True)
SKILL_PATTERN = re.compile(r'\b(' + '|'.join(re.escape(s) for s in SORTED_ALIASES) + r')\b', re.IGNORECASE)
STRICT_PATTERN = re.compile(r'\b(C|R)\b')

# Organizations and Descriptions to ignore during Company extraction
IGNORE_ORGS = {
    'school', 'college', 'university', 'institute', 'pvt ltd', 'private limited', 'inc', 'llc', 'corporation',
    'express', 'react', 'python', 'java', 'aws', 'amazon web services',
    'data scientist', 'software engineer', 'developer', 'account executive', 'lead', 'marketing',
    'boston', 'miami', 'columbia', 'duke', 'university of miami', 'boston university', 'duke university',
    'experince', 'experience', 'education', 'skills', 'profile', 'summary', 'about me', 'contact',
    'project', 'responsibilities', 'achievements', 'internship', 'trainee', 'student', 'analyst', 'manager',
    'senior', 'junior', 'associate', 'lead', 'chief', 'head', 'coordinator', 'specialist', 'assistant', 'officer',
    'scientist', 'engineer', 'developer', 'consultant', 'accountant', 'executive', 'nih', 'grant', 'funding', 'investigator',
    # Added "Action Verbs" to prevent job descriptions from being extracted as companies
    'led', 'built', 'developed', 'managed', 'created', 'designed', 'architected', 'improved', 'implemented', 'performed',
    'researched', 'analyzed', 'conducted', 'monitored', 'maintained', 'supported', 'assisted', 'coordinated', 'mentored',
    'increased', 'reduced', 'saved', 'optimized', 'scaled', 'modeled', 'deployed', 'migrated', 'automated', 'integrated',
    'place', 'date', 'declaration', 'signature', 'statement', 'hereby', 'truthful', 'correct', 'best of my knowledge',
    'b.com', 'bcom', 'm.sc', 'msc', 'b.a', 'ba', 'm.a', 'ma', 'b.e', 'm.e', 'b.tech', 'm.tech', 'mba', 'mca', 'bca',
    'implemented', 'attended', 'handled', 'prepared', 'assisted', 'reconciliation', 'management', 'services', 'coloring', 'styling', 'attending', 'executing'
}

# High-Confidence Predefined Organization List (Ensures major names are never missed)
PREDEFINED_ORGS = {
    'Reliance', 'TCS', 'Infosys', 'Wipro', 'HCL', 'Accenture', 'Cognizant', 'Capgemini', 'IBM', 'Google', 'Microsoft', 
    'Amazon', 'Slice', 'Unacademy', 'Byjus', 'Airtel', 'Jio', 'Deloitte', 'PWC', 'EY', 'KPMG', 'HDFC', 'ICICI', 'SBI', 
    'Axis', 'L&T', 'Godrej', 'Tata', 'Tech Mahindra', 'Cognizant', 'Mindtree', 'Oracle', 'Cisco', 'Adobe', 'Swiggy', 
    'Zomato', 'Ola', 'Uber', 'Paytm', 'PhonePe', 'Flipkart', 'Snapdeal', 'Myntra', 'Freshworks', 'Zoho', 'Postman',
    'Tech Mahindra', 'Vistara', 'IndiGo', 'Mahindra', 'Bajaj', 'Adani', 'Vedanta', 'Asian Paints', 'Titan'
}
IGNORE_TITLES = {
    'B.A.', 'B.S.', 'B.B.A.', 'M.A.', 'M.S.', 'MBA', 'B.Tech', 'M.Tech', 'Engineering', 'Economics', 
    'Marketing', 'Design', 'Science', 'Arts', 'Fellow', 'Postdoctoral', 'Computer Science', 'UC Berkeley', 'NYU'
}


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


NAME_REGEX = re.compile(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}$')

def sanitize_filename(filename):
    # Remove extension and clean characters for Excel/Windows safety
    name = os.path.splitext(filename)[0]
    # Replace common resume junk with spaces
    name = re.sub(r'(_| - | -|-|Resume|CV|Curriculum Vitae|Job|Apply)', ' ', name, flags=re.IGNORECASE)
    # Remove digits and extra symbols
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
        # 1. Extract from paragraphs
        for para in doc.paragraphs:
            if para.text.strip():
                text += para.text + "\n"
        # 2. Extract from tables (Crucial for modern resumes like Priya Reddy's)
        for table in doc.tables:
            for row in table.rows:
                row_text = []
                for cell in row.cells:
                    if cell.text.strip():
                        row_text.append(cell.text.strip())
                if row_text:
                    text += " | ".join(row_text) + "\n"
    except Exception as e:
        print(f"DOCX Extraction Error ({os.path.basename(file_path)}): {e}")
    return text, []


def parse_text(text, hidden_emails, file_name="Not Provided"):
    # Common position titles to ignore or split
    # Common position titles to ignore or split
    ROLE_WORDS = {"Manager", "Scientist", "Developer", "Analyst", "Engineer", "Executive", "Associate", "Lead", "Senior", "Junior", "Coordinator", "Nurse", "RN", "Consultant", "Specialist", "Director", "Product", "Early", "Stage", "GTM", "Gtm"}
    
    # Initialize all default empty values with professional placeholder
    data = {k: "Not Provided" for k in FINAL_HEADERS}
    data["File Name"] = file_name
    
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
        if len(digits) >= 10:
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

    # 4. Name (Super-Fast Regex First)
    name = ""
    lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 3][:10]
    for line in lines:
        if NAME_REGEX.match(line):
            temp_name = line.strip().title()
            # Clean salutations (Mr, Ms, Mrs, etc.)
            temp_name = re.sub(r'^(Mr|Ms|Mrs|Miss)\.?\s+', '', temp_name, flags=re.IGNORECASE)
            
            # If the name is just a job title, skip it
            if any(title.lower() in temp_name.lower() for title in ["Manager", "Scientist", "Developer", "Analyst", "Engineer"]):
                continue
            name = temp_name; break

    if not name:
        name = sanitize_filename(data.get('File Name', '')) or "Not Provided"
    
    data["Candidate Name"] = name.strip()

    # 4b. Location (Search entire text)
    text_lower = text.lower()
    for city, _ in INDIAN_CITIES.items():
        if re.search(r'\b' + re.escape(city) + r'\b', text_lower):
            data["Current Location"] = city.title(); break





    # 5. Experience (Direct extraction or total calculation)
    exp_matches = EXP_REGEX.search(text)
    if exp_matches:
        data["Total Years of Experience"] = f"{exp_matches.group(1)} Years"
    else:
        # Fallback: Sum up years from date ranges
        date_ranges = re.findall(r'(\d{4})\s*(?:-|–|to)\s*(\d{4}|Present|Current|Today)', text, re.IGNORECASE)
        total_yrs = 0
        for start, end in date_ranges:
            s_yr = int(start)
            e_yr = datetime.now().year if re.search(r'Present|Current|Today|Till Date', end, re.IGNORECASE) else int(end)
            if 0 < (e_yr - s_yr) < 40: total_yrs += (e_yr - s_yr)
        if total_yrs > 0:
            data["Total Years of Experience"] = f"{total_yrs} Years (Est.)"


    # 6. Location (Redundant search removed)

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
        post_exp_text = text[exp_idx.end():exp_idx.end() + 4000]

        # Calculate Years Worked in Current Company
        # Match year ranges: "Jan 2018 - 2022", "(2021 to Present)", support –, —, -
        date_pattern = r'\(?((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?[a-z]*[\s\,]*\d{4})\s*(?:-|–|—|to)\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?[a-z]*[\s\,]*\d{4}|Present|Current|Till Date|Today)\)?'
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
                    data["Years Worked in Current Company"] = f"{yr_diff}"

        # 9c. Find Current and Previous Companies (Grammar & Length Based Strategy)
        lines = [l.strip() for l in post_exp_text.split("\n") if len(l.strip()) > 3][:40]
        found_orgs_with_dates = []
        found_orgs_fallback = []
        
        # Action verbs that indicate a description, NOT a company name
        ACTION_VERBS = {
            'led', 'built', 'developed', 'managed', 'created', 'designed', 'architected', 'improved', 'implemented', 
            'performed', 'researched', 'analyzed', 'conducted', 'monitored', 'maintained', 'supported', 'assisted', 
            'coordinated', 'mentored', 'increased', 'reduced', 'saved', 'optimized', 'scaled', 'modeled', 'deployed', 
            'migrated', 'automated', 'integrated', 'achieved', 'raised', 'prepared', 'executed', 'grew', 'supervise',
            'implement', 'management', 'handling', 'preparation', 'assisting', 'attending', 'attended', 'managing'
        }
        COMPANY_KW = r'\b(?:Pvt|Ltd|Limited|Corp|Inc|Company|Agency|Solutions|Firm|Bank|Unicorn|Startup|Systems|Research|Aerospace|Financial|XYZ|Co|Intl|Global|Manufacturing|Institution|PDX|Hospital|Medical|Clinic|Center|Health|Services|Tech|Software|Technologies|District|CPA)\b'
        
        # Stricter Date Pattern for individual lines
        STRICT_DATE_RE = re.compile(r'\b(20\d{2}|Present|Current|Till|Today)\b', re.IGNORECASE)
        
        for line in lines:
            # Section Guard: Don't extract companies from the Declaration/Personal section
            if any(term in line.lower() for term in ["declaration", "personal details", "signature", "hobbies", "interest"]):
                break

            # 1. Strip leading bullets/symbols to find the real start of text
            line_clean = re.sub(r'^[•\-\*\d\.\s]+', '', line)
            
            # Hard skip for lines starting with lowercase (likely descriptions)
            if line_clean and line_clean[0].islower():
                continue
                
            words = line_clean.split()
            first_word_clean = re.sub(r'[^A-Za-z]', '', words[0]).lower() if words else ""
            
            # Hard skip for education and junk action lines (Prefix check for verbs)
            if len(words) > 7 or any(first_word_clean.startswith(v) for v in ACTION_VERBS) or first_word_clean in ['bcom', 'msc', 'mba', 'btech', 'mtech', 'account']:
                continue
            
            # 2. Extract potential company part (Simplified Pipe/Comma Splitting)
            temp_part = line
            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
                temp_part = parts[0]
            elif "," in line and re.search(r'\d{4}', line):
                # Handle "Slice (Earlier Slicepay), Bengaluru" - split by first comma if date exists
                temp_part = line.split(",")[0]
            elif " at " in line.lower():
                temp_part = re.split(r'\s+at\s+', line, flags=re.IGNORECASE)[-1]
            
            # 3. Clean and validate company name (Remove positions from name)
            clean_name = re.sub(r'^[•\-\*\d\.\s]+', '', temp_part) 
            # Remove text in parentheses like "(Earlier Slicepay)"
            clean_name = re.sub(r'\(.*?\)', '', clean_name).strip()
            clean_name = re.sub(r'\s*\b(Present|Current|Till Date|Today)\b.*', '', clean_name, flags=re.IGNORECASE)
            
            # STRIKE: Remove actual position words from the name
            for rw in ROLE_WORDS:
                clean_name = re.sub(r'\b' + re.escape(rw) + r'\b', '', clean_name, flags=re.IGNORECASE)
            
            clean_name = re.sub(r'\d{4}', '', clean_name)
            clean_name = re.sub(r'[^A-Za-z\s\.\&\-]', '', clean_name).strip()
            
            # Final validation: check length and non-lower start
            if len(clean_name) < 3 or len(clean_name) > 50 or (clean_name and clean_name[0].islower()): continue
            if any(title.lower() in clean_name.lower() for title in IGNORE_TITLES): continue

            # 4. Score confidence (Look for ANY date on the line)
            is_current = re.search(r'\b(Present|Current|Today|Till Date)\b', line, re.IGNORECASE)
            has_any_date = STRICT_DATE_RE.search(line)
            
            # HIGH CONFIDENCE: Check against our predefined list first
            is_predefined = any(po.lower() in clean_name.lower() for po in PREDEFINED_ORGS)
            
            # If it has a date, a Company keyword, or is a Predefined brand
            if is_predefined or re.search(COMPANY_KW, clean_name, re.IGNORECASE) or has_any_date:
                if not any(w.lower() in clean_name.lower() for w in IGNORE_ORGS):
                    # If it's predefined, use the canonical name from our list
                    if is_predefined:
                        for po in PREDEFINED_ORGS:
                            if po.lower() in clean_name.lower():
                                clean_name = po
                                break
                    
                    if is_current:
                        found_orgs_with_dates.append(clean_name)
                    else:
                        found_orgs_fallback.append(clean_name)

        # 10. Assign based on confidence (Strict History separation)
        current_company = "Not Provided"
        previous_list = []
        
        # 1. Lock in the "Present" company first
        if found_orgs_with_dates:
            current_company = found_orgs_with_dates[0]
            # Any other "Present" or "Fallback" companies go to history
            other_potential = found_orgs_with_dates[1:] + found_orgs_fallback
        else:
            if found_orgs_fallback:
                current_company = found_orgs_fallback[0]
                other_potential = found_orgs_fallback[1:]
            else:
                other_potential = []

        # 2. Collect unique previous companies
        for o in other_potential:
            if o.lower() != current_company.lower() and o.lower() not in [p.lower() for p in previous_list]:
                previous_list.append(o)

        data["Current Company"] = current_company
        if previous_list:
            data["Previous Companies"] = ", ".join(previous_list[:5])

    return data


def process_file(file_path):
    file_name = os.path.basename(file_path)
    try:
        if file_path.lower().endswith(".docx"):
            extracted_text, hidden_emails = extract_docx_data(file_path)
        else:
            extracted_text, hidden_emails = extract_pdf_data(file_path)
            
        res = parse_text(extracted_text, hidden_emails, file_name)

        
        # Last check - if name is still empty, use sanitized file name
        if res.get('Candidate Name') == "Not Provided":
            res['Candidate Name'] = sanitize_filename(file_name)
            
        return res
    except Exception as e:
        print(f"Processing Error ({file_name}): {e}")
        # Return empty data with just the file name
        res = {k: "Not Provided" for k in FINAL_HEADERS}
        res['File Name'] = file_name
        res['Candidate Name'] = f"Error: {str(e)[:30]}"
        return res


def process_all(files):
    if not files: return []
    # Swap to ThreadPool for pure speed and lightweight execution
    workers = min(16, multiprocessing.cpu_count() * 4)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(process_file, files))
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
    # Light start
    print("Resume Extraction Engine Started 🚀")
    app.run(debug=True, port=5000)




