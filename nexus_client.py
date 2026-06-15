"""
Nexus API client for resume analysis using Claude Opus 4.6
Uses AWS Bedrock API interface via GenAI-Nexus
"""
import json
import os
import boto3
from dotenv import load_dotenv

load_dotenv()

class NexusClient:
    def __init__(self):
        self.api_key = os.getenv('NEXUS_API_KEY')
        self.endpoint_url = os.getenv('NEXUS_API_URL', 'https://genai-nexus.api.corpinter.net/')
        self.api_version = '2024-10-21'
        self.model = 'claude-opus-4.6'
        
        if not self.api_key:
            raise ValueError("NEXUS_API_KEY environment variable not set")
        
        # Set AWS bearer token for Bedrock
        os.environ['AWS_BEARER_TOKEN_BEDROCK'] = self.api_key
        
        # Initialize boto3 client
        self.client = boto3.client(
            service_name="bedrock-runtime",
            endpoint_url=self.endpoint_url,
            region_name="nexus"
        )
    
    def rank_resumes(self, job_description, resumes_data):
        """
        Use Claude to rank resumes based on job description
        resumes_data: list of dicts with {name: str, content: str}
        """
        prompt = self._create_ranking_prompt(job_description, resumes_data)
        return self._call_api(prompt)
    
    def generate_questions(self, resume_content, resume_name):
        """
        Generate 5 questions based on resume content
        """
        prompt = self._create_questions_prompt(resume_content, resume_name)
        return self._call_api(prompt)
    
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
            response = self.client.converse(
                modelId=self.model,
                messages=[
                    {
                        'role': 'user',
                        'content': [{'text': prompt}]
                    }
                ]
            )
            
            translated = response['output']['message']['content'][0]['text']
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
            response = self.client.converse(
                modelId=self.model,
                messages=[{'role': 'user', 'content': [{'text': prompt}]}]
            )
            raw = response['output']['message']['content'][0]['text'].strip()
            if raw.startswith("```"):
                raw = '\n'.join(l for l in raw.split('\n') if not l.startswith("```"))
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
            response = self.client.converse(
                modelId=self.model,
                messages=[{'role': 'user', 'content': [{'text': prompt}]}]
            )
            return response['output']['message']['content'][0]['text'].strip()
        except Exception as e:
            raise Exception(f"Resume update failed: {str(e)}")

    def _create_ranking_prompt(self, job_description, resumes_data):
        """Create prompt for resume ranking"""
        resumes_text = "\n\n".join([
            f"Resume #{i+1} - Candidate: {r['name']}\n{r['content']}" 
            for i, r in enumerate(resumes_data)
        ])
        
        prompt = f"""You are an expert HR recruiter. Analyze and rank the following resumes based on the job description.

RANKING CRITERIA:
1. Keyword match: How well does the resume match keywords from the job description
2. Employment duration: Longest employment period at a single company
3. Job stability: Least number of employer changes with maximum years of experience
4. Recent experience: How well recent experience aligns with job requirements

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
    
    def _create_questions_prompt(self, resume_content, resume_name):
        """Create prompt for generating questions"""
        prompt = f"""Based on the following resume, generate exactly 5 insightful questions that demonstrate deep understanding of the candidate's background. 

RESUME:
Candidate Name: {resume_name}
{resume_content}

Generate questions that:
1. Address employment gaps if they exist
2. Explain short employment periods (if any)
3. Clarify relocation willingness if needed
4. Highlight specific achievements or skills
5. Address career progression or transitions

Format the response as a JSON array:
[
    {{
        "question": "question text here",
        "topic": "topic_category"
    }}
]

Return ONLY valid JSON array, no additional text."""
        
        return prompt
    
    def _call_api(self, prompt):
        """Call Nexus API (AWS Bedrock) with the prompt"""
        try:
            response = self.client.converse(
                modelId=self.model,
                messages=[
                    {
                        'role': 'user',
                        'content': [{'text': prompt}]
                    }
                ]
            )
            
            # Extract content from response
            content = response['output']['message']['content'][0]['text']
            
            # Try to parse JSON from response
            try:
                # First, try to extract JSON if it's embedded in text
                json_content = content.strip()
                
                # If the response starts with markdown code block, extract it
                if json_content.startswith("```"):
                    lines = json_content.split('\n')
                    json_content = '\n'.join([l for l in lines if not l.startswith("```")])
                
                result = json.loads(json_content)
                return result
                
            except json.JSONDecodeError as je:
                # Return error info for debugging
                print(f"JSON Parse Error: {str(je)}")
                print(f"Response content:\n{content[:500]}")
                
                return {
                    'error': f'JSON parsing failed: {str(je)}',
                    'raw_response': content[:1000],  # First 1000 chars for debugging
                    'response': content
                }
                
        except Exception as e:
            print(f"API call exception: {str(e)}")
            return {
                'error': f'API call failed: {str(e)}',
                'error_type': type(e).__name__
            }
