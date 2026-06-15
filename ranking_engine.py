"""
Resume ranking engine for local pre-processing and analysis
"""
import re
from datetime import datetime
from collections import defaultdict

class RankingEngine:
    """Analyze resumes for ranking purposes"""
    
    @staticmethod
    def extract_keywords(job_description):
        """Extract important keywords from job description"""
        # Remove common words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'is', 'are', 'was', 'were', 'be', 'have', 'has', 'do',
            'does', 'did', 'will', 'would', 'should', 'could', 'can', 'may',
            'must', 'that', 'this', 'as', 'from', 'by', 'it', 'its', 'you',
            'your', 'we', 'our', 'they', 'them', 'required', 'preferred'
        }
        
        # Extract technical terms and key phrases
        words = re.findall(r'\b[a-zA-Z+#\-]+\b', job_description.lower())
        keywords = [w for w in words if len(w) > 3 and w not in stop_words]
        
        # Extract skill patterns (e.g., Java, Python, SQL)
        skill_pattern = r'\b(?:Python|Java|JavaScript|C\+\+|C#|Ruby|PHP|Go|Rust|Kotlin|' \
                       r'SQL|NoSQL|MongoDB|PostgreSQL|MySQL|AWS|Azure|GCP|Docker|Kubernetes|' \
                       r'React|Vue|Angular|Node|Express|Django|Flask|Spring|Hibernate|' \
                       r'Git|Linux|Windows|REST|GraphQL|Microservices|DevOps|CI/CD|' \
                       r'Machine Learning|AI|TensorFlow|PyTorch|Agile|Scrum|Jira)\b'
        
        skills = re.findall(skill_pattern, job_description, re.IGNORECASE)
        
        return {
            'keywords': list(set(keywords)),
            'skills': list(set(skills)),
            'all_terms': list(set(keywords + skills))
        }
    
    @staticmethod
    def calculate_keyword_match(resume_text, keywords_dict):
        """Calculate keyword match percentage"""
        resume_lower = resume_text.lower()
        matched_count = 0
        
        for keyword in keywords_dict['all_terms']:
            if keyword.lower() in resume_lower:
                matched_count += 1
        
        if not keywords_dict['all_terms']:
            return 0
        
        match_percentage = (matched_count / len(keywords_dict['all_terms'])) * 100
        return min(100, match_percentage)
    
    @staticmethod
    def extract_employment_history(resume_text):
        """Extract employment history and calculate metrics"""
        # Simple pattern matching for employment durations
        duration_pattern = r'(\d{1,2})\s*(?:years?|yrs?|months?|mos?)'
        company_pattern = r'(?:at|@|with|worked at|employed by)\s+([A-Za-z0-9\s\-\.]+?)(?:\n|,|;|from|to)'
        
        durations = re.findall(duration_pattern, resume_text, re.IGNORECASE)
        companies = re.findall(company_pattern, resume_text, re.IGNORECASE)
        
        # Calculate total experience
        total_experience_years = 0
        for duration in durations:
            try:
                years = float(duration)
                if years <= 50:  # Sanity check
                    total_experience_years += years
            except:
                pass
        
        # Count employer changes (approximate)
        unique_companies = len(set([c.strip() for c in companies if c.strip()]))
        
        return {
            'total_experience_years': total_experience_years,
            'employer_count': max(1, unique_companies),
            'employment_changes': max(0, unique_companies - 1),
            'longest_duration': max([float(d) for d in durations if d.isdigit()], default=0)
        }
    
    @staticmethod
    def extract_location(resume_text):
        """Extract candidate location"""
        location_keywords = [
            'location:', 'based in', 'located in', 'living in',
            'city:', 'address:', 'from', 'address :'
        ]
        
        for keyword in location_keywords:
            pattern = keyword + r'\s*([A-Za-z\s,]+?)(?:\n|,|;)'
            match = re.search(pattern, resume_text, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                if location and len(location) < 100:
                    return location
        
        return None
    
    @staticmethod
    def extract_employment_gaps(resume_text):
        """Identify employment gaps"""
        # Look for date patterns
        date_pattern = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*\d{4}'
        dates = re.findall(date_pattern, resume_text, re.IGNORECASE)
        
        # Simple gap detection - more than 6 months between entries
        gaps = []
        if len(dates) >= 2:
            gaps.append({
                'detected': True,
                'note': 'Potential employment gaps detected in resume'
            })
        
        return gaps
    
    @staticmethod
    def extract_recent_experience(resume_text, months_back=24):
        """Extract recent experience (last 24 months by default)"""
        # Look for "Currently" or "Present" markers
        current_job_pattern = r'(?:Currently|Present|Ongoing|Now)[^.]*(?:\n|.)*?(?:\n\n|$)'
        recent_matches = re.findall(current_job_pattern, resume_text, re.IGNORECASE)
        
        return {
            'has_current_position': len(recent_matches) > 0,
            'recent_entries': recent_matches
        }
    
    @staticmethod
    def calculate_stability_score(employment_history):
        """Calculate job stability score (0-100)"""
        if employment_history['total_experience_years'] == 0:
            return 0
        
        # Fewer employer changes = better score
        # More years of experience = better score
        changes = employment_history['employment_changes']
        years = employment_history['total_experience_years']
        
        # Base score on years
        base_score = min(100, (years / 20) * 100)  # 20 years = 100 points
        
        # Penalty for job changes
        change_penalty = min(50, changes * 5)  # Each change = 5 points penalty
        
        stability_score = base_score - change_penalty
        return max(0, stability_score)
    
    @staticmethod
    def prepare_analysis_data(candidate_name, resume_text, job_keywords):
        """Prepare comprehensive analysis data for a candidate"""
        employment_history = RankingEngine.extract_employment_history(resume_text)
        location = RankingEngine.extract_location(resume_text)
        gaps = RankingEngine.extract_employment_gaps(resume_text)
        recent = RankingEngine.extract_recent_experience(resume_text)
        keyword_score = RankingEngine.calculate_keyword_match(resume_text, job_keywords)
        stability_score = RankingEngine.calculate_stability_score(employment_history)
        
        return {
            'candidate_name': candidate_name,
            'keyword_match_score': keyword_score,
            'employment_history': employment_history,
            'stability_score': stability_score,
            'location': location,
            'employment_gaps': gaps,
            'recent_experience': recent,
            'resume_preview': resume_text[:500] + '...' if len(resume_text) > 500 else resume_text
        }
