"""
OpenAI client for resume analysis.
Keeps the same public methods used by the Streamlit app.
"""
import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

from ranking_engine import RankingEngine

load_dotenv()


class NexusClient:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o')

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self.client = OpenAI(api_key=self.api_key)
    
    def rank_resumes(self, job_description, resumes_data):
        """
        Rank resumes against the job description using OpenAI with JSON mode.
        resumes_data: list of dicts with {name: str, content: str}
        """
        prompt = self._create_ranking_prompt(job_description, resumes_data)
        result = self._call_api(prompt, json_mode=True)
        if self._is_rankings_payload(result):
            result['analysis'] = self._ensure_grounded_analysis(
                result.get('analysis', ''),
                job_description,
                resumes_data,
                result.get('rankings', []),
            )
            return result

        retry_prompt = self._build_ranking_prompt(job_description, resumes_data, stricter=True)
        retry_result = self._call_api(retry_prompt)
        if self._is_rankings_payload(retry_result):
            retry_result['analysis'] = self._ensure_grounded_analysis(
                retry_result.get('analysis', ''),
                job_description,
                resumes_data,
                retry_result.get('rankings', []),
            )
            return retry_result

        return self._build_rankings_fallback(job_description, resumes_data, result or retry_result)
    
    def generate_questions(self, resume_content, resume_name, job_description=None):
        """
        Generate 5 interview questions based on resume content.
        Uses JSON mode to guarantee parseable output; falls back to
        deterministic questions when the API returns unusable data.
        """
        # Use whatever content is available; empty string is acceptable
        safe_content = (resume_content or '').strip()
        prompt = self._create_questions_prompt(safe_content, resume_name, job_description)
        result = self._call_api(prompt, json_mode=True)

        # JSON-mode returns {"questions": [...]}
        questions = self._extract_questions_list(result)
        if self._is_question_payload(questions):
            return questions

        # Single retry without JSON mode for compatibility
        retry_result = self._call_api(
            self._create_questions_prompt(safe_content, resume_name, job_description, stricter=True)
        )
        retry_questions = self._extract_questions_list(retry_result)
        if self._is_question_payload(retry_questions):
            return retry_questions

        return self._build_question_fallback(safe_content, resume_name, job_description, result or retry_result)
    
    def translate_text(self, text: str, source_language: str, language_name: str) -> str:
        """
        Translate text from source language to English
        """
        prompt = f"""Translate the following {language_name} text to English. 
        
Maintain all technical terms, names, and specific details. 
Return ONLY the translated text, no explanations.

{language_name} TEXT:
{text}"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.2,
            )
            translated = response.choices[0].message.content or ''
            return translated.strip()
        except Exception as e:
            raise Exception(f"Translation failed: {str(e)}")
    
    def translate_report_content(self, content: dict) -> dict:
        """
        Translate all dynamic report text (summaries, questions, overall analysis)
        from English to German in a single API call.
        `content` keys: rankings (list of {summary}), questions (dict), overall_analysis (str)
        Returns the same structure with text values translated.
        """
        import copy
        payload = json.dumps(content, ensure_ascii=False)

        prompt = f"""Translate the following JSON report content from English to German.
Translate ONLY the text values — do NOT change keys, numbers, percentages, or candidate names.
Return ONLY valid JSON with the same structure.

JSON TO TRANSLATE:
{payload}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.2,
            )
            raw = (response.choices[0].message.content or '').strip()
            raw = self._strip_code_fences(raw)
            return json.loads(raw)
        except Exception as e:
            raise Exception(f"Report translation failed: {str(e)}")

    def update_resume(self, resume_content: str, resume_name: str, job_description: str, missing_keywords: list) -> str:
        """
        Rewrite resume in European CV standard, incorporating missing keywords
        to improve skill matching with the job description.
        """
        missing_kw_text = ', '.join(missing_keywords[:30]) if missing_keywords else 'None identified'

        prompt = f"""You are an expert CV writer specializing in European-standard resumes (Europass format).

Rewrite the candidate's resume following these rules:
1. Use European CV format with clearly labelled sections in UPPERCASE:
   PERSONAL INFORMATION, PROFESSIONAL SUMMARY, WORK EXPERIENCE, EDUCATION, SKILLS, LANGUAGES, CERTIFICATIONS
2. Naturally incorporate the MISSING KEYWORDS below into relevant sections where they genuinely reflect the candidate's experience — do NOT fabricate any jobs, dates, or qualifications
3. Use strong action verbs and quantify existing achievements where possible
4. Improve keyword density to increase matching with the job description
5. Maintain every factual detail — same employers, same dates, same responsibilities

CANDIDATE NAME: {resume_name}

ORIGINAL RESUME:
{resume_content}

JOB DESCRIPTION (for keyword context):
{job_description}

MISSING KEYWORDS TO INCORPORATE (only where genuinely applicable):
{missing_kw_text}

Return ONLY the complete rewritten resume as plain text. Start directly with the candidate's name — no preamble or explanation."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.2,
            )
            return (response.choices[0].message.content or '').strip()
        except Exception as e:
            raise Exception(f"Resume update failed: {str(e)}")

    def _create_ranking_prompt(self, job_description, resumes_data):
        return self._build_ranking_prompt(job_description, resumes_data, stricter=False)

    def _build_ranking_prompt(self, job_description, resumes_data, stricter=False):
        """Create prompt for resume ranking."""
        resumes_text = "\n\n".join([
            f"Resume #{i+1} - Candidate: {r['name']}\n{r['content']}" 
            for i, r in enumerate(resumes_data)
        ])

        guardrails = """
HALLUCINATION SAFEGUARDS:
1. Use only facts explicitly present in the job description or resumes.
2. Do not invent employers, dates, degrees, skills, locations, or achievements.
3. If evidence is missing, use conservative wording such as 'not clearly stated'.
4. Every ranking summary must reference at least one concrete resume detail and one job requirement.
5. The overall analysis must mention specific candidates and concrete evidence from the provided resumes.
""".strip()

        strict_note = """
STRICT MODE:
Return a concise, evidence-based JSON only. If the response is still too generic, the app will replace it with a grounded fallback.
""".strip() if stricter else ""
        
        prompt = f"""You are an expert HR recruiter. Analyze and rank the following resumes based on the job description.

RANKING CRITERIA:
1. Keyword match: How well does the resume match keywords from the job description
2. Employment duration: Longest employment period at a single company
3. Job stability: Least number of employer changes with maximum years of experience
4. Recent experience: How well recent experience aligns with job requirements

{guardrails}

{strict_note}

JOB DESCRIPTION:
{job_description}

RESUMES TO ANALYZE:
{resumes_text}

Provide a JSON response with the following structure:
{{
    "rankings": [
        {{
            "candidate_name": "name",
            "rank": 1,
            "score": 85,
            "keyword_match_score": 80,
            "employment_duration_score": 75,
            "job_stability_score": 90,
            "recent_experience_score": 85,
            "summary": "brief analysis of why this ranking"
        }}
    ],
    "analysis": "overall analysis of candidate pool"
}}

Return ONLY valid JSON, no additional text."""
        
        return prompt
    
    def _create_questions_prompt(self, resume_content, resume_name, job_description=None, stricter=False):
        """Create prompt for generating grounded interview questions.
        Returns a JSON *object* {"questions": [...]} so JSON mode can be used.
        """
        job_context = f"JOB DESCRIPTION CONTEXT:\n{job_description}".strip() if job_description else ""

        resume_block = (
            f"RESUME:\nCandidate Name: {resume_name}\n{resume_content}"
            if resume_content
            else f"CANDIDATE NAME: {resume_name}\n(Full resume not available — base questions on the job description and the candidate name.)"
        )

        guardrails = (
            "RULES:\n"
            "1. Ask only about information explicitly visible in the resume or job description.\n"
            "2. Do not invent employers, projects, dates, or qualifications.\n"
            "3. Each question must reference a concrete signal from the resume (gap, skill, role, progression).\n"
            "4. Return exactly 5 unique, specific questions as a JSON object."
        )

        strict_note = (
            "STRICT MODE: If the resume lacks evidence for a topic, pick a different grounded topic."
            if stricter else ""
        )

        prompt = (
            f"You are a professional HR interviewer. Generate exactly 5 insightful interview questions "
            f"for the candidate based on the information below.\n\n"
            f"{resume_block}\n\n"
            f"{job_context}\n\n"
            f"{guardrails}\n\n"
            f"{strict_note}\n\n"
            f"Return a JSON object in this exact format:\n"
            f"{{\"questions\": ["
            f"{{\"question\": \"...\", \"topic\": \"...\"}}, ..."
            f"]}}"
        )
        return prompt

    def _is_rankings_payload(self, result):
        if not isinstance(result, dict):
            return False
        rankings = result.get('rankings')
        if not isinstance(rankings, list) or not rankings:
            return False
        for item in rankings:
            if not isinstance(item, dict):
                return False
            if not item.get('candidate_name'):
                return False
        return True

    def _is_question_payload(self, result):
        """Accept any list of 1-7 non-empty question dicts."""
        if not isinstance(result, list):
            return False
        if not (1 <= len(result) <= 7):
            return False
        seen = set()
        for item in result:
            if not isinstance(item, dict):
                return False
            question = str(item.get('question', '')).strip()
            if len(question) < 10:
                return False
            seen.add(question.lower()[:60])
        # All items must be distinct
        return len(seen) == len(result)

    def _extract_questions_list(self, result):
        """Normalise API result to a plain list of question dicts.
        Handles both raw list and JSON-mode {"questions": [...]} wrapper.
        """
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            # JSON-mode wrapper
            for key in ('questions', 'Questions', 'items'):
                if isinstance(result.get(key), list):
                    return result[key]
        return []

    def _ensure_grounded_analysis(self, analysis, job_description, resumes_data, rankings):
        analysis_text = (analysis or '').strip()
        if analysis_text and not self._looks_generic(analysis_text):
            return analysis_text

        if not rankings:
            return self._build_local_analysis(job_description, resumes_data, [])

        return self._build_local_analysis(job_description, resumes_data, rankings)

    def _looks_generic(self, text):
        """Return True only when the analysis is clearly a boilerplate placeholder."""
        lowered = text.lower()
        # Too short to be meaningful
        if len(lowered.split()) < 12:
            return True
        # Pure boilerplate with no specifics
        boilerplate_phrases = [
            'overall analysis of candidate pool',
            'the candidate pool was reviewed',
        ]
        return any(phrase in lowered for phrase in boilerplate_phrases)

    def _build_local_analysis(self, job_description, resumes_data, rankings):
        if rankings:
            top = rankings[0]
            top_name = top.get('candidate_name', 'the top-ranked candidate')
            top_score = top.get('score', 'N/A')
            kw_score = top.get('keyword_match_score', 'N/A')
            stability_score = top.get('job_stability_score', 'N/A')
            recent_score = top.get('recent_experience_score', 'N/A')
            return (
                f"{top_name} ranks highest with an overall score of {top_score}%, driven by a keyword match score of {kw_score}% "
                f"and job stability of {stability_score}%. Recent experience is scored at {recent_score}%, so the ranking is tied to the strongest "
                f"observable match against the supplied job description rather than inferred details."
            )

        return (
            f"The candidate pool was reviewed against the job description, but the model output did not provide a reliable analysis. "
            f"The app will surface the ranking data and question set instead of inventing missing conclusions."
        )

    def _build_rankings_fallback(self, job_description, resumes_data, model_result):
        job_keywords = RankingEngine.extract_keywords(job_description)
        rankings = []

        for index, resume in enumerate(resumes_data, 1):
            analysis_data = RankingEngine.prepare_analysis_data(
                resume['name'],
                resume['content'],
                job_keywords,
            )
            ranking = {
                'candidate_name': resume['name'],
                'rank': index,
                'score': round((analysis_data['keyword_match_score'] + analysis_data['stability_score']) / 2, 1),
                'keyword_match_score': round(analysis_data['keyword_match_score'], 1),
                'employment_duration_score': round(min(100, analysis_data['employment_history']['longest_duration'] * 10), 1),
                'job_stability_score': round(analysis_data['stability_score'], 1),
                'recent_experience_score': 80 if analysis_data['recent_experience']['has_current_position'] else 50,
                'summary': self._build_candidate_summary(resume['name'], analysis_data, job_keywords),
            }
            rankings.append(ranking)

        rankings.sort(key=lambda item: item.get('score', 0), reverse=True)
        for index, ranking in enumerate(rankings, 1):
            ranking['rank'] = index

        return {
            'rankings': rankings,
            'analysis': self._build_local_analysis(job_description, resumes_data, rankings),
            'fallback_used': True,
            'model_response': model_result,
        }

    def _build_candidate_summary(self, candidate_name, analysis_data, job_keywords):
        employment = analysis_data['employment_history']
        matched_keywords = [
            keyword for keyword in job_keywords['all_terms']
            if keyword.lower() in analysis_data['resume_preview'].lower()
        ][:5]
        keyword_text = ', '.join(matched_keywords) if matched_keywords else 'few explicit job keywords'
        return (
            f"{candidate_name} shows a keyword match of {analysis_data['keyword_match_score']:.1f}% and a stability score of {analysis_data['stability_score']:.1f}%. "
            f"The resume suggests {employment['employment_changes']} employer changes and a longest stated duration of {employment['longest_duration']} years. "
            f"Grounded keywords observed in the resume include: {keyword_text}."
        )

    def _build_question_fallback(self, resume_content, resume_name, job_description, model_result):
        fallback_questions = []
        facts = self._extract_resume_signals(resume_content, job_description)

        if facts['employment_changes'] > 0:
            fallback_questions.append({
                'question': f"What prompted the transitions between employers in your resume, and what did you learn from each move, {resume_name}?",
                'topic': 'career_transitions',
            })
        else:
            fallback_questions.append({
                'question': f"Can you walk me through the most important progression in your career and how it prepared you for this role, {resume_name}?",
                'topic': 'career_progression',
            })

        if facts['has_gap_signal']:
            fallback_questions.append({
                'question': f"Your resume appears to include a possible gap or pause in employment. How would you explain that period, {resume_name}?",
                'topic': 'employment_gap',
            })
        else:
            fallback_questions.append({
                'question': f"Which part of your recent experience best matches the responsibilities in this job description?",
                'topic': 'role_alignment',
            })

        if facts['location']:
            fallback_questions.append({
                'question': f"You listed {facts['location']} as a location signal. How flexible are you about relocation or hybrid work if the role requires it?",
                'topic': 'relocation',
            })
        else:
            fallback_questions.append({
                'question': f"What work arrangement or location constraints should we keep in mind for this role?",
                'topic': 'work_location',
            })

        if facts['matched_keywords']:
            focus_skill = facts['matched_keywords'][0]
            fallback_questions.append({
                'question': f"Can you describe a concrete example where you used {focus_skill} to deliver measurable impact?",
                'topic': 'skill_depth',
            })
        else:
            fallback_questions.append({
                'question': f"What is the strongest technical or functional skill in your background that would help you succeed here?",
                'topic': 'skill_depth',
            })

        fallback_questions.append({
            'question': f"What achievement from your resume are you most proud of, and how would you measure its impact today?",
            'topic': 'achievements',
        })

        unique_questions = []
        seen = set()
        for item in fallback_questions:
            question = item['question']
            if question not in seen:
                unique_questions.append(item)
                seen.add(question)
        while len(unique_questions) < 5:
            unique_questions.append({
                'question': f"What additional context would help us understand your fit for this role beyond the resume alone?",
                'topic': 'general_fit',
            })

        return unique_questions[:5]

    def _extract_resume_signals(self, resume_content, job_description=None):
        employment_history = RankingEngine.extract_employment_history(resume_content)
        gaps = RankingEngine.extract_employment_gaps(resume_content)
        location = RankingEngine.extract_location(resume_content)
        keywords = RankingEngine.extract_keywords(job_description or '') if job_description else {'all_terms': []}

        matched_keywords = []
        resume_lower = resume_content.lower()
        for keyword in keywords.get('all_terms', []):
            if keyword.lower() in resume_lower:
                matched_keywords.append(keyword)

        return {
            'employment_changes': employment_history.get('employment_changes', 0),
            'has_gap_signal': bool(gaps),
            'location': location,
            'matched_keywords': matched_keywords[:5],
        }
    
    def _call_api(self, prompt, json_mode=False):
        """Call OpenAI with the prompt and parse JSON responses.
        When json_mode=True, uses response_format={"type":"json_object"} which
        guarantees the response is always valid JSON (requires JSON in the prompt).
        """
        try:
            kwargs = dict(
                model=self.model,
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.2,
            )
            if json_mode:
                kwargs['response_format'] = {'type': 'json_object'}

            response = self.client.chat.completions.create(**kwargs)
            content = (response.choices[0].message.content or '').strip()

            try:
                json_content = self._strip_code_fences(content)
                result = json.loads(json_content)
                return result
                
            except json.JSONDecodeError as je:
                print(f"JSON Parse Error: {str(je)}")
                print(f"Response content:\n{content[:500]}")
                
                return {
                    'error': f'JSON parsing failed: {str(je)}',
                    'raw_response': content[:1000],
                    'response': content
                }
                
        except Exception as e:
            print(f"API call exception: {str(e)}")
            return {
                'error': f'API call failed: {str(e)}',
                'error_type': type(e).__name__
            }

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove markdown code fences from model output when present."""
        if text.startswith("```"):
            lines = text.split('\n')
            lines = [line for line in lines if not line.startswith("```")]
            return '\n'.join(lines).strip()
        return text
