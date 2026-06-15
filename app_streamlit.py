"""
MatchMuse - Intelligent Resume Matching Tool
Streamlit Frontend
Supports multilingual job descriptions and resumes with automatic translation
"""

import streamlit as st
import os
from pathlib import Path
from fpdf import FPDF
from resume_processor import ResumeProcessor
from ranking_engine import RankingEngine
from nexus_client import NexusClient
from language_handler import LanguageHandler


def generate_pdf(candidate_name: str, resume_text: str) -> bytes:
    """
    Convert a plain-text resume to a well-formatted, downloadable PDF.
    Handles wrapping, consistent spacing, section headings, and bullet points.
    """

    def _safe(text: str) -> str:
        """Strip / replace characters that built-in Latin-1 fonts can't render."""
        return text.encode('latin-1', 'replace').decode('latin-1')

    MARGIN   = 15    # mm  – left / right / top / bottom
    BODY_H   = 5.5   # mm  – body text line height
    HEAD_H   = 7.0   # mm  – section heading line height
    NAME_H   = 9.0   # mm  – name line height
    PARA_GAP = 3.0   # mm  – space for blank lines

    pdf = FPDF()
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=MARGIN)
    eff_w = pdf.epw   # effective page width (= 210 - 2×MARGIN = 180 mm)

    lines = resume_text.split('\n')
    first_content_printed = False   # track whether we've rendered the name yet

    for raw_line in lines:
        line     = raw_line.rstrip()
        stripped = line.strip()

        # ── blank line → small paragraph gap ────────────────────────────────
        if not stripped:
            pdf.ln(PARA_GAP)
            continue

        safe_line = _safe(stripped)

        # ── first non-empty line = candidate name header ─────────────────────
        if not first_content_printed:
            first_content_printed = True
            pdf.set_font("Helvetica", "B", 14)
            pdf.multi_cell(eff_w, NAME_H, safe_line, align="C")
            pdf.ln(1)
            pdf.set_font("Helvetica", "", 10)
            continue

        # ── UPPERCASE lines (≥3 chars) = section headings ────────────────────
        if stripped.isupper() and len(stripped) >= 3:
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 11)
            pdf.multi_cell(eff_w, HEAD_H, safe_line)
            # thin rule under the heading
            y = pdf.get_y()
            pdf.set_line_width(0.3)
            pdf.line(MARGIN, y, pdf.w - MARGIN, y)
            pdf.ln(2)
            pdf.set_font("Helvetica", "", 10)
            continue

        # ── bullet-like lines ────────────────────────────────────────────────
        if stripped[:2] in ('- ', '• ', '* '):
            INDENT = 5
            pdf.set_x(MARGIN + INDENT)
            pdf.multi_cell(eff_w - INDENT, BODY_H, safe_line)
            continue

        # ── ordinary body text ───────────────────────────────────────────────
        pdf.set_x(MARGIN)
        pdf.multi_cell(eff_w, BODY_H, safe_line)

    return bytes(pdf.output())

# Configure Streamlit page
st.set_page_config(
    page_title="MatchMuse",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Authentication ────────────────────────────────────────────────────────────

def _check_credentials(username: str, password: str) -> bool:
    """Validate credentials against environment variables."""
    expected_user = os.getenv("MATCHMUSE_USERNAME", "")
    expected_pass = os.getenv("MATCHMUSE_PASSWORD", "")
    if not expected_user or not expected_pass:
        st.error("⚠️ Server misconfiguration: MATCHMUSE_USERNAME / MATCHMUSE_PASSWORD not set.")
        return False
    return username == expected_user and password == expected_pass


def _render_login() -> None:
    """Render a centred login form and block until authenticated."""
    st.markdown("""
        <style>
        .login-box {
            max-width: 380px;
            margin: 6rem auto 0 auto;
            padding: 2.5rem;
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.10);
        }
        .login-title {
            font-size: 1.9rem;
            font-weight: 700;
            color: #1e40af;
            text-align: center;
            margin-bottom: 0.3rem;
        }
        .login-sub {
            font-size: 0.9rem;
            color: #64748b;
            text-align: center;
            margin-bottom: 1.8rem;
        }
        </style>
    """, unsafe_allow_html=True)

    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.markdown('<div class="login-title">🎯 MatchMuse</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Intelligent Resume Matching Tool<br>Please sign in to continue</div>', unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="Enter username")
            password = st.text_input("Password", type="password", placeholder="Enter password")
            submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

        if submitted:
            if _check_credentials(username, password):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Invalid username or password.")


# Guard: stop here and show login if not authenticated
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    _render_login()
    st.stop()

# Logout button in sidebar (only shown when authenticated)
with st.sidebar:
    st.markdown("### MatchMuse")
    if st.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.rerun()

# ── End Authentication ────────────────────────────────────────────────────────

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1e40af;
        margin-bottom: 0.5rem;
        font-weight: 700;
    }
    .subtitle {
        font-size: 1rem;
        color: #64748b;
        margin-bottom: 2rem;
    }
    .score-badge {
        display: inline-block;
        background-color: #2563eb;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        font-weight: 600;
        margin: 0.5rem 0;
    }
    .rank-1 { border-left: 4px solid #fbbf24; background-color: rgba(251, 191, 36, 0.05); }
    .rank-2 { border-left: 4px solid #a78bfa; }
    .rank-3 { border-left: 4px solid #f87171; }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'results' not in st.session_state:
    st.session_state.results = None
if 'updated_resume_data' not in st.session_state:
    st.session_state.updated_resume_data = None
if 'report_language' not in st.session_state:
    st.session_state.report_language = 'English'
if 'translated_content' not in st.session_state:
    st.session_state.translated_content = None
if 'nexus_client' not in st.session_state:
    try:
        st.session_state.nexus_client = NexusClient()
        st.session_state.api_configured = True
        st.session_state.language_handler = LanguageHandler(st.session_state.nexus_client)
    except ValueError as e:
        st.session_state.api_configured = False
        st.session_state.api_error = str(e)

# Header
st.markdown('<div class="main-header">🎯 MatchMuse</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Intelligent Resume Matching | Created by Chaitanya Priya</div>', unsafe_allow_html=True)

# Check API configuration
if not st.session_state.api_configured:
    st.error(f"⚠️ Configuration Error: {st.session_state.api_error}")
    st.info("Please ensure your configuration file is properly set up.")
    st.stop()

# Main interface
if not st.session_state.analyzed:
    st.markdown("---")
    
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.subheader("📝 Job Description")
        job_description = st.text_area(
            "Paste the job description here:",
            height=250,
            placeholder="Enter the complete job description...",
            key="job_desc"
        )
    
    with col2:
        st.subheader("📄 Upload Resumes")
        uploaded_files = st.file_uploader(
            "Upload resume files (PDF, DOCX, DOC, TXT):",
            type=["pdf", "docx", "doc", "txt"],
            accept_multiple_files=True,
            key="resumes"
        )
        
        if uploaded_files:
            st.info(f"✅ {len(uploaded_files)} file(s) selected")
    
    st.markdown("---")
    
    # Language detection (optional)
    show_language_info = st.checkbox("🌐 Show Language Detection", value=False)
    
    if show_language_info and (job_description or uploaded_files):
        st.info("🔍 Detecting language in provided content...")
        
        lang_col1, lang_col2 = st.columns([1, 1])
        
        with lang_col1:
            if job_description and len(job_description.strip()) > 10:
                lang_code, lang_name = st.session_state.language_handler.detect_language(job_description)
                st.write(f"**Job Description Language:** {lang_name} ({lang_code})")
        
        with lang_col2:
            if uploaded_files:
                for uploaded_file in uploaded_files:
                    try:
                        # Read file content temporarily
                        temp_dir = Path("/tmp/lang_detect")
                        temp_dir.mkdir(exist_ok=True)
                        file_path = temp_dir / uploaded_file.name
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        success, content, _ = ResumeProcessor.extract_text(
                            str(file_path), uploaded_file.name
                        )
                        if success and len(content) > 10:
                            lang_code, lang_name = st.session_state.language_handler.detect_language(content)
                            st.write(f"**{uploaded_file.name}:** {lang_name} ({lang_code})")
                        
                        if file_path.exists():
                            file_path.unlink()
                    except:
                        pass
    
    st.markdown("---")
    
    # Analyze button
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🚀 Analyze Resumes", use_container_width=True, type="primary"):
            # Validate inputs
            if not job_description or len(job_description.strip()) < 50:
                st.error("❌ Job description must be at least 50 characters long")
                st.stop()
            
            if not uploaded_files:
                st.error("❌ Please upload at least one resume file")
                st.stop()
            
            if len(uploaded_files) > 10:
                st.error("❌ Maximum 10 resumes allowed")
                st.stop()
            
            # Process resumes
            with st.spinner("📂 Processing resumes..."):
                resumes_data = []
                temp_dir = Path("/tmp/resume_upload")
                temp_dir.mkdir(exist_ok=True)
                
                for uploaded_file in uploaded_files:
                    try:
                        # Save temporarily
                        file_path = temp_dir / uploaded_file.name
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        # Extract text
                        success, content, error = ResumeProcessor.extract_text(
                            str(file_path), uploaded_file.name
                        )
                        
                        if not success:
                            st.warning(f"⚠️ {uploaded_file.name}: {error}")
                            continue
                        
                        candidate_name = ResumeProcessor.get_candidate_name(
                            str(file_path), uploaded_file.name
                        )
                        resumes_data.append({
                            'name': candidate_name,
                            'content': content,
                            'filename': uploaded_file.name
                        })
                        
                    except Exception as e:
                        st.warning(f"⚠️ Error processing {uploaded_file.name}: {str(e)}")
                    finally:
                        # Cleanup
                        if file_path.exists():
                            file_path.unlink()
                
                if not resumes_data:
                    st.error("❌ No valid resumes could be processed")
                    st.stop()
            
            # Detect and translate if needed
            with st.spinner("🌐 Detecting and translating languages..."):
                language_handler = st.session_state.language_handler
                
                # Detect job description language
                job_lang_code, job_lang_name = language_handler.detect_language(job_description)
                translated_job_description = job_description
                job_was_translated = False
                
                # Translate job description if needed
                if job_lang_code != 'en':
                    st.info(f"🔄 Job description detected as {job_lang_name}. Translating to English...")
                    try:
                        translated_job_description = st.session_state.nexus_client.translate_text(
                            job_description, job_lang_code, job_lang_name
                        )
                        job_was_translated = True
                        st.success(f"✅ Job description translated from {job_lang_name} to English")
                    except Exception as e:
                        st.warning(f"⚠️ Translation failed, using original: {str(e)}")
                        translated_job_description = job_description
                
                # Detect and translate resumes if needed
                resume_translations = {}
                for resume_data in resumes_data:
                    resume_lang_code, resume_lang_name = language_handler.detect_language(resume_data['content'])
                    resume_translations[resume_data['name']] = {
                        'lang_code': resume_lang_code,
                        'lang_name': resume_lang_name,
                        'was_translated': False,
                        'original_content': resume_data['content']
                    }
                    
                    # Translate resume if not in English
                    if resume_lang_code != 'en':
                        st.info(f"🔄 {resume_data['name']}'s resume detected as {resume_lang_name}. Translating...")
                        try:
                            translated_content = st.session_state.nexus_client.translate_text(
                                resume_data['content'], resume_lang_code, resume_lang_name
                            )
                            resume_data['content'] = translated_content
                            resume_translations[resume_data['name']]['was_translated'] = True
                            st.success(f"✅ {resume_data['name']}'s resume translated from {resume_lang_name}")
                        except Exception as e:
                            st.warning(f"⚠️ Translation failed for {resume_data['name']}, using original: {str(e)}")
            
            # Perform analysis
            with st.spinner("🤖 Analyzing resumes..."):
                try:
                    # Extract keywords
                    job_keywords = RankingEngine.extract_keywords(translated_job_description)
                    st.info(f"✅ Extracted {len(job_keywords.get('keywords', []))} keywords from job description")
                    
                    # Get rankings from API
                    nexus_client = st.session_state.nexus_client
                    st.info("📊 Requesting resume rankings...")
                    ranking_result = nexus_client.rank_resumes(translated_job_description, resumes_data)
                    
                    # Debug: Show what we got from API
                    if not ranking_result:
                        st.warning("⚠️ API returned empty response")
                    elif 'error' in ranking_result:
                        st.error(f"❌ API Error: {ranking_result['error']}")
                    elif 'response' in ranking_result and not 'rankings' in ranking_result:
                        with st.expander("🔍 API Response (Debug)", expanded=False):
                            st.write("Response received but not in expected format:")
                            st.code(str(ranking_result), language="python")
                    
                    # Generate questions for top candidates
                    questions_for_candidates = {}
                    
                    if 'rankings' in ranking_result and ranking_result['rankings']:
                        st.success(f"✅ Generated rankings for {len(ranking_result['rankings'])} candidates")
                        top_candidates = ranking_result['rankings'][:2]
                        
                        for idx, ranking in enumerate(top_candidates, 1):
                            candidate_name = ranking.get('candidate_name', 'Unknown')
                            st.info(f"Generating interview questions for Candidate {idx}: {candidate_name}...")
                            
                            resume_content = next(
                                (r['content'] for r in resumes_data if r['name'] == candidate_name),
                                None
                            )
                            
                            if resume_content:
                                try:
                                    questions = nexus_client.generate_questions(
                                        resume_content, candidate_name
                                    )
                                    questions_for_candidates[candidate_name] = questions
                                    st.success(f"✅ Generated questions for {candidate_name}")
                                except Exception as e:
                                    st.warning(f"⚠️ Failed to generate questions for {candidate_name}: {str(e)}")
                                    questions_for_candidates[candidate_name] = {
                                        'error': f'Could not generate questions: {str(e)}'
                                    }
                    else:
                        st.warning("⚠️ No rankings received from API")
                        with st.expander("🔍 API Response (Debug)", expanded=True):
                            st.code(f"Response: {str(ranking_result)}", language="python")
                    
                    # Store results
                    st.session_state.results = {
                        'job_analysis': {
                            'keywords': job_keywords.get('keywords', [])[:20],
                            'skills': job_keywords.get('skills', []),
                            'total_candidates': len(resumes_data),
                            'job_language': job_lang_name,
                            'job_was_translated': job_was_translated
                        },
                        'rankings': ranking_result.get('rankings', []),
                        'overall_analysis': ranking_result.get('analysis', ''),
                        'questions': questions_for_candidates,
                        'language_info': resume_translations,
                        'api_response_debug': str(ranking_result) if 'rankings' not in ranking_result else None,
                        'resumes_data': resumes_data,
                        'job_description': translated_job_description,
                        'job_keywords': job_keywords,
                    }
                    st.session_state.analyzed = True
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Analysis failed: {str(e)}")
                    st.error(f"Error type: {type(e).__name__}")
                    with st.expander("🔍 Full Error Details", expanded=True):
                        import traceback
                        st.code(traceback.format_exc(), language="python")
                    st.stop()

else:
    # ── Label dictionaries ────────────────────────────────────────────────────
    L = {
        'English': {
            'summary_header':     '📊 Analysis Summary',
            'total_candidates':   'Total Candidates',
            'key_skills':         'Key Skills Found',
            'keywords':           'Keywords Extracted',
            'lang_info':          '🌐 Language Information',
            'job_desc_lang':      '**Job Description Language:**',
            'resume_langs':       '**Resume Languages:**',
            'translated_status':  '✅ Status: Translated to English',
            'original_status':    '✅ Status: Already in English',
            'rankings_header':    '🏆 Candidate Rankings',
            'rank_label':         'Rank',
            'score_label':        'Score',
            'overall':            'Overall',
            'kw_match':           'Keyword Match',
            'emp_duration':       'Employment Duration',
            'job_stability':      'Job Stability',
            'recent_exp':         'Recent Experience',
            'analysis_prefix':    '**Analysis:**',
            'no_rankings':        'No rankings available',
            'questions_header':   '❓ Interview Questions',
            'questions_for':      'Questions for',
            'q_prefix':           'Q',
            'no_questions':       'No questions generated',
            'overall_header':     '📈 Overall Analysis',
            'no_overall':         'No overall analysis available',
            'optimise_label':     'Select resume to optimise:',
        },
        'Deutsch': {
            'summary_header':     '📊 Analyseübersicht',
            'total_candidates':   'Kandidaten gesamt',
            'key_skills':         'Schlüsselqualifikationen',
            'keywords':           'Schlüsselwörter',
            'lang_info':          '🌐 Sprachinformationen',
            'job_desc_lang':      '**Stellenbeschreibung – Sprache:**',
            'resume_langs':       '**Lebenslauf-Sprachen:**',
            'translated_status':  '✅ Status: Ins Englische übersetzt',
            'original_status':    '✅ Status: Bereits auf Englisch',
            'rankings_header':    '🏆 Kandidatenranking',
            'rank_label':         'Rang',
            'score_label':        'Punkte',
            'overall':            'Gesamt',
            'kw_match':           'Keyword-Übereinstimmung',
            'emp_duration':       'Beschäftigungsdauer',
            'job_stability':      'Jobstabilität',
            'recent_exp':         'Aktuelle Erfahrung',
            'analysis_prefix':    '**Analyse:**',
            'no_rankings':        'Keine Rankings verfügbar',
            'questions_header':   '❓ Interviewfragen',
            'questions_for':      'Fragen für',
            'q_prefix':           'F',
            'no_questions':       'Keine Fragen generiert',
            'overall_header':     '📈 Gesamtanalyse',
            'no_overall':         'Keine Gesamtanalyse verfügbar',
            'optimise_label':     'Lebenslauf zum Optimieren auswählen:',
        },
    }

    # Display results
    results = st.session_state.results
    resumes_data = results.get('resumes_data', [])
    candidate_options = [r['name'] for r in resumes_data]

    # ── Top toolbar: Back | Candidate dropdown | Update Resume button ─────────
    tb_col1, tb_col2, tb_col3 = st.columns([1, 2, 1])

    with tb_col1:
        if st.button("← Back to Analysis", use_container_width=True):
            st.session_state.analyzed = False
            st.session_state.results = None
            st.session_state.updated_resume_data = None
            st.session_state.translated_content = None
            st.session_state.report_language = 'English'
            st.rerun()

    with tb_col2:
        if candidate_options:
            selected_candidate = st.selectbox(
                "Select resume to optimise:",
                options=candidate_options,
                key="resume_optimizer_select",
                label_visibility="collapsed"
            )
        else:
            selected_candidate = None
            st.empty()

    with tb_col3:
        update_clicked = st.button(
            "✍️ Update Resume",
            type="primary",
            use_container_width=True,
            key="update_resume_btn",
            disabled=(selected_candidate is None)
        )

    # ── Language selector (just below toolbar) ────────────────────────────────
    lang_col1, lang_col2 = st.columns([1, 3])
    with lang_col1:
        chosen_lang = st.radio(
            "Report language:",
            options=['English', 'Deutsch'],
            index=0 if st.session_state.report_language == 'English' else 1,
            horizontal=True,
            key="lang_radio"
        )
    # If language changed, clear cached translation so it regenerates
    if chosen_lang != st.session_state.report_language:
        st.session_state.report_language = chosen_lang
        if chosen_lang == 'English':
            st.session_state.translated_content = None
        st.rerun()

    lbl = L[st.session_state.report_language]

    # ── Translate dynamic content when German is selected ─────────────────────
    if st.session_state.report_language == 'Deutsch' and st.session_state.translated_content is None:
        # Build payload with only translatable dynamic text
        translatable = {
            'rankings': [
                {'candidate_name': r.get('candidate_name', ''), 'summary': r.get('summary', '')}
                for r in results.get('rankings', [])
            ],
            'questions': {
                cname: [
                    (q.get('question', q) if isinstance(q, dict) else q)
                    for q in (qs if isinstance(qs, list) else [])
                ]
                for cname, qs in results.get('questions', {}).items()
                if isinstance(qs, list)
            },
            'overall_analysis': results.get('overall_analysis', ''),
        }
        with st.spinner("🌐 Translating report to German…"):
            try:
                st.session_state.translated_content = st.session_state.nexus_client.translate_report_content(translatable)
            except Exception as e:
                st.warning(f"⚠️ Translation failed, showing English: {e}")
                st.session_state.translated_content = translatable

    # Helpers to pull translated or original content
    def _ranking_summary(ranking):
        if st.session_state.report_language == 'Deutsch' and st.session_state.translated_content:
            tc_rankings = st.session_state.translated_content.get('rankings', [])
            match = next((r for r in tc_rankings if r.get('candidate_name') == ranking.get('candidate_name')), None)
            return match.get('summary', ranking.get('summary', '')) if match else ranking.get('summary', '')
        return ranking.get('summary', '')

    def _questions(candidate_name):
        if st.session_state.report_language == 'Deutsch' and st.session_state.translated_content:
            return st.session_state.translated_content.get('questions', {}).get(candidate_name,
                   results['questions'].get(candidate_name, []))
        return results['questions'].get(candidate_name, [])

    def _overall_analysis():
        if st.session_state.report_language == 'Deutsch' and st.session_state.translated_content:
            return st.session_state.translated_content.get('overall_analysis', results.get('overall_analysis', ''))
        return results.get('overall_analysis', '')

    # ── Run optimiser when button clicked ────────────────────────────────────
    if update_clicked and selected_candidate:
        resume_entry = next((r for r in resumes_data if r['name'] == selected_candidate), None)
        if resume_entry:
            job_kw = results.get('job_keywords', {})
            all_terms = job_kw.get('all_terms', [])
            resume_lower = resume_entry['content'].lower()
            missing_keywords = [kw for kw in all_terms if kw.lower() not in resume_lower]

            with st.spinner(f"✍️ Rewriting {selected_candidate}'s resume in European standard..."):
                try:
                    updated_text = st.session_state.nexus_client.update_resume(
                        resume_entry['content'],
                        selected_candidate,
                        results.get('job_description', ''),
                        missing_keywords
                    )
                    st.session_state.updated_resume_data = {
                        'name': selected_candidate,
                        'content': updated_text
                    }
                    st.success(f"✅ Resume updated for {selected_candidate}!")
                except Exception as e:
                    st.error(f"❌ Failed to update resume: {str(e)}")

    # ── Show updated resume + PDF download ───────────────────────────────────
    upd = st.session_state.updated_resume_data
    if upd and selected_candidate and upd.get('name') == selected_candidate:
        with st.expander(f"📄 Updated Resume — {upd['name']}", expanded=True):
            st.text(upd['content'])
        pdf_bytes = generate_pdf(upd['name'], upd['content'])
        safe_name = upd['name'].replace(' ', '_')
        st.download_button(
            label="⬇️ Download Updated Resume (PDF)",
            data=pdf_bytes,
            file_name=f"{safe_name}_updated_resume.pdf",
            mime="application/pdf",
            key="download_updated_resume"
        )

    st.markdown("---")

    # ── Summary section ───────────────────────────────────────────────────────
    st.subheader(lbl['summary_header'])
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(lbl['total_candidates'], results['job_analysis']['total_candidates'])
    with col2:
        st.metric(lbl['key_skills'], len(results['job_analysis']['skills']))
    with col3:
        st.metric(lbl['keywords'], len(results['job_analysis']['keywords']))

    st.markdown("---")

    # ── Language information section ──────────────────────────────────────────
    if results.get('language_info') or results.get('job_analysis', {}).get('job_was_translated'):
        with st.expander(lbl['lang_info'], expanded=False):
            col1, col2 = st.columns([1, 1])
            with col1:
                st.write(lbl['job_desc_lang'])
                if results.get('job_analysis', {}).get('job_was_translated'):
                    st.write(f"📝 Original: {results['job_analysis']['job_language']}")
                    st.write(lbl['translated_status'])
                else:
                    st.write(f"📝 {results['job_analysis']['job_language']}")
                    st.write(lbl['original_status'])
            with col2:
                st.write(lbl['resume_langs'])
                for cand_name, lang_info in results.get('language_info', {}).items():
                    lang = lang_info['lang_name']
                    status = "✅ Translated" if lang_info['was_translated'] else "✅ Original"
                    st.write(f"{cand_name}: {lang} ({status})")

    # ── Rankings section ──────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader(lbl['rankings_header'])

    rankings = results['rankings']
    if rankings:
        for idx, ranking in enumerate(rankings, 1):
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"### {lbl['rank_label']} #{ranking.get('rank', idx)}: {ranking['candidate_name']}")
                    st.markdown(f"**{lbl['score_label']}:** `{ranking.get('score', 'N/A')}%`")
                with col2:
                    st.metric(lbl['overall'], f"{ranking.get('score', 'N/A')}%")

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric(lbl['kw_match'], f"{ranking.get('keyword_match_score', 'N/A')}%")
                with col2:
                    st.metric(lbl['emp_duration'], f"{ranking.get('employment_duration_score', 'N/A')}%")
                with col3:
                    st.metric(lbl['job_stability'], f"{ranking.get('job_stability_score', 'N/A')}%")
                with col4:
                    st.metric(lbl['recent_exp'], f"{ranking.get('recent_experience_score', 'N/A')}%")

                summary = _ranking_summary(ranking)
                if summary:
                    st.markdown(f"{lbl['analysis_prefix']} {summary}")
    else:
        st.info(lbl['no_rankings'])

    # ── Questions section ─────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader(lbl['questions_header'])

    questions = results['questions']
    if questions:
        for candidate_name in questions:
            with st.expander(f"📋 {lbl['questions_for']} {candidate_name}", expanded=True):
                raw_qs = questions[candidate_name]
                if isinstance(raw_qs, dict) and 'error' in raw_qs:
                    st.warning(raw_qs['error'])
                elif isinstance(raw_qs, list):
                    display_qs = _questions(candidate_name)
                    if not isinstance(display_qs, list):
                        display_qs = raw_qs
                    for i, q in enumerate(display_qs, 1):
                        q_text = q if isinstance(q, str) else q.get('question', str(q))
                        st.markdown(f"**{lbl['q_prefix']}{i}:** {q_text}")
                else:
                    st.info(str(raw_qs))
    else:
        st.info(lbl['no_questions'])

    # ── Overall analysis ──────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader(lbl['overall_header'])
    overall = _overall_analysis()
    if overall:
        st.write(overall)
    else:
        st.info(lbl['no_overall'])

    # Debug section if API had issues
    st.markdown("---")
    if results.get('api_response_debug'):
        with st.expander("🔍 API Response Debug Info", expanded=False):
            st.warning("⚠️ API Response had issues. Here's what was returned:")
            st.code(results['api_response_debug'], language="python")
