"""apply_helper.py — Generate cover letter + open the application page."""
import webbrowser
import pyperclip


def generate_cover_letter(profile, job: dict) -> str:
    name = "Hiring Manager"
    skills = ", ".join(sorted(profile.skills)[:6]) or "relevant skills"
    years = f"{profile.years} years of " if profile.years else ""
    return (
        f"Dear {name},\n\n"
        f"I am excited to apply for the {job['title']} position at "
        f"{job['company']}. With {years}hands-on experience including "
        f"{skills}, I believe my background makes me a strong fit.\n\n"
        f"I would welcome the opportunity to discuss how I can contribute "
        f"to your team.\n\nBest regards,\n[Your Name]"
    )


def apply_to_job(profile, job: dict):
    """Copy cover letter to clipboard and open the job page."""
    letter = generate_cover_letter(profile, job)
    try:
        pyperclip.copy(letter)
    except Exception:
        pass
    webbrowser.open(job["link"])
    return letter
