"""cv_parser.py — Extract skills & experience from PDF/DOCX CVs."""
import re
from pathlib import Path

SKILLS_DB = [
    "python", "java", "c++", "c#", "javascript", "typescript", "sql",
    "html", "css", "react", "angular", "vue", "node.js", "django",
    "flask", "fastapi", "spring", ".net", "php", "laravel", "ruby",
    "swift", "kotlin", "flutter", "android", "ios",
    "excel", "word", "powerpoint", "outlook", "access", "vba",
    "quickbooks", "sap", "oracle", "peachtree", "odoo", "erp",
    "accounting", "bookkeeping", "auditing", "taxation", "payroll",
    "financial analysis", "budgeting", "forecasting", "reconciliation",
    "ifrs", "gaap", "cost accounting", "accounts payable", "accounts receivable",
    "photoshop", "illustrator", "figma", "canva", "premiere pro",
    "autocad", "solidworks", "revit", "matlab",
    "power bi", "tableau", "looker", "data analysis", "machine learning",
    "pandas", "numpy", "tensorflow", "pytorch", "scikit-learn",
    "docker", "kubernetes", "git", "jenkins", "aws", "azure", "gcp",
    "linux", "bash", "rest api", "graphql", "microservices", "ci/cd",
    "project management", "agile", "scrum", "jira", "trello", "asana",
    "customer service", "salesforce", "crm", "marketing", "seo",
    "copywriting", "content creation", "social media", "google analytics",
]

YEARS_PATTERNS = [
    r"(\d{1,2})\+?\s*years?\s+(?:of\s+)?experience",
    r"experience\s*:?\s*(\d{1,2})\+?\s*years?",
    r"(\d{1,2})\s*yrs?\s+(?:of\s+)?exp",
]


def _extract_text(path: str) -> str:
    ext = Path(path).suffix.lower()
    text = ""
    if ext == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception as e:
            print(f"PDF parse error: {e}")
    elif ext in (".docx", ".doc"):
        try:
            import docx
            d = docx.Document(path)
            text = "\n".join(p.text for p in d.paragraphs)
        except Exception as e:
            print(f"DOCX parse error: {e}")
    return text


def extract_skills(text: str) -> set[str]:
    low = text.lower()
    return {s for s in SKILLS_DB if s.lower() in low}


def extract_years(text: str) -> int | None:
    for pat in YEARS_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None


class CVProfile:
    """Parsed CV ready for matching."""

    def __init__(self, path: str):
        self.path = path
        self.text = _extract_text(path)
        self.skills = extract_skills(self.text)
        self.years = extract_years(self.text)

    def summary(self) -> str:
        yrs = f"{self.years} yrs exp" if self.years else "exp n/a"
        top = ", ".join(sorted(self.skills)[:15])
        return f"{yrs} | Skills: {top or 'none detected'}"
