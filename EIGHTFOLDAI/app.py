"""
SignalScope — Premium Talent Intelligence Dashboard
EightfoldAI Hackathon: Impact Area 01
"""

import streamlit as st
import os
import json
import PyPDF2
from streamlit_tags import st_tags

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Talent Intelligence Dashboard",
    page_icon="🔷",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Load CSS ─────────────────────────────────────────────────────────────────
css_path = os.path.join(os.path.dirname(__file__), "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ── Imports ──────────────────────────────────────────────────────────────────
from github_parser import build_candidate_signal
from jd_parser import extract_skills_from_jd, extract_skills_from_resume
from scoring_engine import compute_skill_match, compute_github_signal_score, compute_overall_score
from explainability import generate_candidate_summary, generate_bias_check, generate_gap_analysis

# ══════════════════════════════════════════════════════════════════════════════
# TOP NAVBAR
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="nav-container">', unsafe_allow_html=True)
col_logo, col_reset, col_export = st.columns([8, 1, 1.5])
with col_logo:
    st.markdown("<div class='nav-title'>🔷 Talent Intelligence Dashboard</div>", unsafe_allow_html=True)
with col_reset:
    if st.button("↺ Reset", use_container_width=True):
         st.session_state.clear()
         st.rerun()
with col_export:
    report_data = st.session_state.get("report_json", "{}")
    st.download_button(label="📥 Export Report", data=report_data, file_name="candidate_report.json", mime="application/json", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN GRID LAYOUT
# ══════════════════════════════════════════════════════════════════════════════
col_left, col_space, col_right = st.columns([12, 1, 12])

# Initialize session state for analysis results
if "analyzed" not in st.session_state:
    st.session_state.analyzed = False

# ─── LEFT PANEL (INPUT SECTION) ───────────────────────────────────────────────
with col_left:
    # 📌 Section 1: Job Description Card
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 📝 Job Description")
    
    jd_text = st.text_area(
        "",
        height=180,
        placeholder="Paste or write job description...",
        label_visibility="collapsed"
    )
    
    # JD Parsing logic triggered via button
    if "parsed_req" not in st.session_state:
        st.session_state.parsed_req = []
    if "parsed_pref" not in st.session_state:
        st.session_state.parsed_pref = []
        
    col_btn, _ = st.columns([1, 2])
    with col_btn:
        st.markdown('<div class="btn-secondary">', unsafe_allow_html=True)
        if st.button("Extract Skills from JD", use_container_width=True):
            if jd_text.strip():
                parsed = extract_skills_from_jd(jd_text)
                st.session_state.parsed_req = parsed.get("required_skills", [])
                st.session_state.parsed_pref = parsed.get("preferred_skills", [])
            else:
                st.warning("Please enter a JD first.")
        st.markdown('</div>', unsafe_allow_html=True)

    # Skills Editor using st_tags
    req_skills = st_tags(
        label="Required Skills",
        text="Press enter to add more",
        value=st.session_state.parsed_req,
        suggestions=["Python", "React", "SQL", "Docker", "AWS", "Kubernetes"],
        maxtags=50,
        key="tag_req"
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # 📌 Section 2: Candidate Input Card
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 👤 Candidate Input")
    
    github_url = st.text_input("🔗 GitHub Profile", placeholder="e.g., torvalds (username) or https://github.com/torvalds")
    
    st.markdown("<br/>", unsafe_allow_html=True)
    st.markdown("📄 **Resume Upload:**")
    resume_file = st.file_uploader("Upload PDF (Optional)", type=["pdf"], label_visibility="collapsed")
    st.markdown("<small style='color: #64748b;'>💡 <i>Resume upload is optional. Real-world signals (GitHub/projects) are preferred.</i></small>", unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

    # 📌 Section 3: Action Button
    st.markdown('<div class="btn-analyze">', unsafe_allow_html=True)
    analyze_clicked = st.button("🚀 Analyze Candidate", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)


# ─── RIGHT PANEL (RESULTS SECTION) ────────────────────────────────────────────
with col_right:
    if analyze_clicked:
        if not req_skills:
            st.error("Please provide/extract at least one required skill.")
        elif not github_url.strip():
            st.error("Please enter a GitHub profile.")
        else:
            with st.spinner("⏳ Analyzing candidate… extracting signals…"):
                # 1. Parse Candidate Username
                username = github_url.strip().split('/')[-1]
                
                # 2. Fetch GitHub Signal
                try:
                    candidate = build_candidate_signal(username)
                except Exception as e:
                    st.error(f"Error fetching GitHub data: {e}")
                    st.stop()
                    
                # 3. Parse Resume (if provided)
                resume_text = ""
                if resume_file:
                    try:
                        reader = PyPDF2.PdfReader(resume_file)
                        for page in reader.pages:
                            resume_text += page.extract_text() + "\n"
                    except Exception as e:
                        st.warning("Failed to parse PDF resume.")
                
                resume_parsed = extract_skills_from_resume(resume_text)
                
                # Combine Skills
                combined_skills = list(set(candidate["skill_keywords"] + resume_parsed.get("skills", [])))
                all_jd_skills = list(set(req_skills + st.session_state.get("parsed_pref", [])))
                
                # Compute Matches
                skill_match = compute_skill_match(combined_skills, all_jd_skills)
                github_score = compute_github_signal_score(candidate)
                overall = compute_overall_score(skill_match["overall_score"], github_score["overall_score"])
                overall_score = overall["overall_score"]
                
                # Gap Analytics
                gap_analysis = generate_gap_analysis(combined_skills, all_jd_skills, skill_match, overall, "")
                summary = generate_candidate_summary(username, skill_match, github_score, overall, "")
                bias = generate_bias_check(username, skill_match, github_score, overall)
                
                # Save to sessions state to persist results view
                st.session_state.result = {
                    "score": overall_score,
                    "matched": gap_analysis.get("matched_skills", []),
                    "missing": gap_analysis.get("missing_skills", []),
                    "summary": summary,
                    "bias": bias
                }
                st.session_state.report_json = json.dumps(st.session_state.result, indent=2)
                st.session_state.analyzed = True

    # ── Display Results if Analyzed ──
    if st.session_state.analyzed:
        res = st.session_state.result
        score = res["score"]
        
        # Color Logic
        if score >= 70:
            color_class = "green"
            score_status = "✔ Strong Match"
        elif score >= 40:
            color_class = "yellow"
            score_status = "⚠️ Moderate Match"
        else:
            color_class = "red"
            score_status = "❌ Weak Match"

        st.markdown('<div class="fade-in">', unsafe_allow_html=True)

        # 🟦 Section 1: Match Score Card
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("<h4 style='margin-top:0;'>Match Score</h4>", unsafe_allow_html=True)
        st.markdown(f"<span class='score-badge score-{color_class}'>{score}%</span>", unsafe_allow_html=True)
        st.markdown(f"""
            <div class="progress-bg">
                <div class="progress-fill bg-{color_class}" style="width: {score}%;"></div>
            </div>
            <div style="font-weight:600; margin-top:4px;" class="score-{color_class}">{score_status}</div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # 🟩 Section 2: Skills Analysis
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("<h4 style='margin-top:0;'>Skills Analysis</h4>", unsafe_allow_html=True)
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.markdown("✅ **Matched Skills**")
            if res["matched"]:
                st.markdown("<ul class='skill-list'>", unsafe_allow_html=True)
                for s in res["matched"][:5]: # show top 5
                    st.markdown(f"<li><span class='matched-skill'>✔</span> {s}</li>", unsafe_allow_html=True)
                st.markdown("</ul>", unsafe_allow_html=True)
            else:
                st.markdown("<small>None detected</small>", unsafe_allow_html=True)
        
        with col_s2:
            st.markdown("❌ **Missing Skills**")
            if res["missing"]:
                st.markdown("<ul class='skill-list'>", unsafe_allow_html=True)
                for s in res["missing"][:5]:
                    st.markdown(f"<li><span class='missing-skill'>✖</span> {s}</li>", unsafe_allow_html=True)
                st.markdown("</ul>", unsafe_allow_html=True)
            else:
                st.markdown("<small>No missing required skills</small>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # 🧠 Section 3: Explainability Panel
        st.markdown('<div class="explain-card">', unsafe_allow_html=True)
        st.markdown("### 🧠 Why This Candidate?")
        
        # Format the summary string into bullet points if it's not already
        summary_lines = res["summary"].split('. ')
        st.markdown("<ul>", unsafe_allow_html=True)
        for line in summary_lines[:4]: # Take key lines
            if line.strip():
                clean_line = line.replace('*', '').replace('-', '').strip()
                st.markdown(f"<li>{clean_line}</li>", unsafe_allow_html=True)
        st.markdown("</ul>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ⚖️ Section 4: Bias Check & 📌 Section 5: Final Recommendation
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.markdown('<div class="card" style="height: 100%;">', unsafe_allow_html=True)
            st.markdown("<h4 style='margin-top:0;'>Bias Check</h4>", unsafe_allow_html=True)
            if res['bias']['is_bias_free']:
                st.markdown('<div class="bias-badge">✅ PASS</div>', unsafe_allow_html=True)
                st.markdown("<p style='font-size:0.9rem; margin-top:8px;'>Score unchanged after removing personal identifiers.</p>", unsafe_allow_html=True)
            else:
                st.markdown('<div class="bias-badge" style="background:#FEE2E2;color:#991B1B;">⚠️ REVIEW</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with col_b2:
            st.markdown('<div class="card" style="height: 100%;">', unsafe_allow_html=True)
            st.markdown("<h4 style='margin-top:0;'>Recommendation</h4>", unsafe_allow_html=True)
            if score >= 70:
                st.markdown("🟢 **Recommended**", unsafe_allow_html=True)
                st.markdown("<p style='font-size:0.9rem;'>Strong technical alignment.</p>", unsafe_allow_html=True)
            elif score >= 40:
                st.markdown("🟡 **Consider**", unsafe_allow_html=True)
                st.markdown("<p style='font-size:0.9rem;'>Good foundation with minor skill gaps.</p>", unsafe_allow_html=True)
            else:
                st.markdown("🔴 **Not Recommended**", unsafe_allow_html=True)
                st.markdown("<p style='font-size:0.9rem;'>Significant gaps in required skills.</p>", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # 📊 Section 6: Skill Gap Visualization
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("<h4 style='margin-top:0;'>Skill Proficiency Signals</h4>", unsafe_allow_html=True)
        
        # Generate some simple bars matching the design request for top skills
        all_skills_list = res["matched"] + res["missing"]
        for s in all_skills_list[:4]:
            if s in res["matched"]:
                fill_w = "100%"
                color = "var(--primary)"
            else:
                fill_w = "15%"
                color = "#CBD5E1"
            
            st.markdown(f"""
                <div class="skill-bar-row">
                    <div class="skill-bar-label">{s}</div>
                    <div class="skill-bar-track">
                        <div class="skill-bar-fill" style="width: {fill_w}; background: {color};"></div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True) # close fade-in
    else:
        # Placeholder styling before analysis
        st.markdown("""
        <div style="height: 100%; display: flex; align-items: center; justify-content: center; opacity: 0.5; margin-top: 100px;">
            <div style="text-align: center;">
                <h3 style="color: #64748B !important;">Awaiting Candidate Data</h3>
                <p>Paste the JD and candidate info on the left, then click analyze to see results.</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
