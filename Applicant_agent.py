from dotenv import load_dotenv
import os
import openai
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from PyPDF2 import PdfReader
import gradio as gr
import asyncio
from pydantic import BaseModel
from openai import OpenAI
import json
import re
from typing import List, Dict, Optional

load_dotenv()  # Load environment variables from .env file

def set_env():
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    model = os.getenv("AZURE_OPENAI_MODEL")

    # Create the Azure OpenAI client
    az_model_client = AzureOpenAIChatCompletionClient(
        azure_deployment=deployment,
        model=model,
        api_version=api_version,
        azure_endpoint=endpoint,
        api_key=api_key,
    )
    client = openai.AzureOpenAI(
        api_version=api_version,
        api_key=api_key,
        azure_endpoint=endpoint
    )
 
    return az_model_client, client

def read_pdf(file_path):
    """Extract text from PDF file"""
    try:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

def extract_name_from_resume(resume_text):
    """Extract name from resume text using simple heuristics"""
    try:
        lines = resume_text.strip().split('\n')
        # Usually the name is in the first few lines
        for line in lines[:5]:
            line = line.strip()
            if len(line) > 2 and len(line) < 50:
                # Check if it looks like a name (not email, phone, address)
                if not any(char in line for char in ['@', '.com', '+', 'www', 'http']):
                    if not line.isupper() and not line.islower():  # Mixed case suggests name
                        return line
        return "Candidate"  # Default if can't extract
    except:
        return "Candidate"

class ATSAnalysis(BaseModel):
    ats_score: int  # 0-100
    keyword_matches: List[str]
    missing_keywords: List[str]
    recommendations: List[str]
    strengths: List[str]
    weaknesses: List[str]

class InterviewEvaluation(BaseModel):
    is_acceptable: bool
    feedback: str
    professionalism_score: int  # 1-10
    relevance_score: int  # 1-10

# Global state management
class GlobalState:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.current_mode = "job_seeker"
        self.candidate_name = "Candidate"
        self.resume_text = ""
        self.cover_letter_text = ""
        self.job_description = ""
        self.ats_analysis_result = None
        self.chat_history = []

# Create global state instance
app_state = GlobalState()

def calculate_ats_score(resume_text: str, job_description: str, client) -> ATSAnalysis:
    """Calculate ATS score by comparing resume with job description"""
    
    ats_prompt = f"""
    You are an ATS (Applicant Tracking System) analyzer. Analyze the following resume against the job description and provide a comprehensive evaluation.

    JOB DESCRIPTION:
    {job_description}

    RESUME:
    {resume_text}

    Please analyze and provide:
    1. ATS Score (0-100) based on keyword matching, relevance, and formatting
    2. Keywords that match between resume and job description
    3. Important keywords missing from the resume
    4. Specific recommendations to improve ATS score
    5. Key strengths of the resume for this position
    6. Areas of weakness or improvement

    Consider factors like:
    - Keyword density and relevance
    - Skills alignment
    - Experience relevance
    - Education requirements
    - Technical skills match
    - Industry-specific terms
    """
    
    try:
        messages = [{"role": "system", "content": ats_prompt}]
        
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            messages=messages
        )
        
        # Parse the response manually since we can't use structured output reliably
        content = response.choices[0].message.content
        
        # Extract score (simple regex)
        score_match = re.search(r'(\d+)/100|(\d+)%|Score[:\s]*(\d+)', content, re.IGNORECASE)
        ats_score = 50  # default
        if score_match:
            ats_score = int(score_match.group(1) or score_match.group(2) or score_match.group(3))
        
        return ATSAnalysis(
            ats_score=ats_score,
            keyword_matches=["Skills analysis completed"],
            missing_keywords=["Detailed in analysis"],
            recommendations=[content[:500] + "..." if len(content) > 500 else content],
            strengths=["Resume processed successfully"],
            weaknesses=["See detailed analysis"]
        )
        
    except Exception as e:
        return ATSAnalysis(
            ats_score=0,
            keyword_matches=[],
            missing_keywords=[],
            recommendations=[f"Error in analysis: {str(e)}"],
            strengths=[],
            weaknesses=["Could not perform analysis"]
        )

def set_interviewer_prompt(candidate_name: str, resume_text: str, job_description: str, cover_letter: str = ""):
    """Set system prompt for job seeker mode - AI acts as interviewer"""
    system_prompt = f"""You are a professional HR interviewer conducting an interview with {candidate_name}. 
    You are interviewing them for the position described in the job description below.
    
    Your role as the interviewer:
    - Ask relevant, thoughtful questions based on the job requirements
    - Evaluate the candidate's experience against the role requirements
    - Ask behavioral questions (STAR method)
    - Probe into specific experiences mentioned in their resume
    - Ask technical questions relevant to the role
    - Be professional, friendly, and thorough
    - Follow up on answers with deeper questions
    - Ask about motivation, career goals, and cultural fit
    
    Interview Guidelines:
    - Start with a warm introduction and overview of the role
    - Ask one question at a time
    - Build questions based on their resume and the job requirements
    - Include a mix of: experience questions, technical questions, behavioral questions, and situational questions
    - Be encouraging but thorough in your evaluation
    - End with asking if they have questions for you
    
    ## Job Description (Role you're hiring for):
    {job_description}
    
    ## Candidate's Resume:
    {resume_text}
    
    {f"## Candidate's Cover Letter: {cover_letter}" if cover_letter else ""}
    
    Conduct a professional interview, asking questions that help evaluate {candidate_name}'s fit for this specific role. 
    Make your questions specific to their background and the job requirements.
    """
    return system_prompt

def set_candidate_prompt(candidate_name: str, resume_text: str, job_description: str, cover_letter: str = ""):
    """Set system prompt for HR/recruiter mode - AI acts as the candidate"""
    system_prompt = f"""You are {candidate_name}, a job candidate being interviewed for a position. 
    The person talking to you is an HR recruiter or hiring manager interviewing you for the role.
    
    Your approach as the candidate:
    - Be professional, confident, and enthusiastic about the opportunity
    - Answer questions based on the experiences in your resume
    - Provide specific examples and stories from your background
    - Show genuine interest in the role and company
    - Ask thoughtful questions when appropriate
    - Be honest about your strengths and acknowledge areas for growth
    - Use the STAR method (Situation, Task, Action, Result) for behavioral questions
    
    ## Job Description (Position you're applying for):
    {job_description}
    
    ## Your Background (Resume):
    {resume_text}
    
    {f"## Your Cover Letter: {cover_letter}" if cover_letter else ""}
    
    The interviewer may ask about your experience, motivations, technical skills, or behavioral questions. 
    Respond authentically as {candidate_name} would, using specific examples from your resume and showing 
    genuine enthusiasm for the opportunity.
    """
    return system_prompt

# Initialize Azure OpenAI client
az_model_client, client = set_env()

# Initialize Gemini client for evaluation (optional)
try:
    gemini = OpenAI(
        api_key=os.getenv("GEMINI_API_KEY"), 
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
except:
    gemini = client  # Fallback to Azure OpenAI

def process_resume_pdf(pdf_file):
    """Process uploaded PDF resume"""
    if pdf_file is None:
        return "❌ No file uploaded.", "", ""
    
    try:
        resume_text = read_pdf(pdf_file.name)
        app_state.resume_text = resume_text
        app_state.candidate_name = extract_name_from_resume(resume_text)
        
        preview = resume_text[:300] + "..." if len(resume_text) > 300 else resume_text
        return f"✅ Resume uploaded! Name detected: {app_state.candidate_name}", preview, app_state.candidate_name
    except Exception as e:
        return f"❌ Error processing PDF: {str(e)}", "", ""

def process_cover_letter_pdf(pdf_file):
    """Process uploaded PDF cover letter"""
    if pdf_file is None:
        app_state.cover_letter_text = ""
        return "No cover letter uploaded."
    
    try:
        cover_letter_text = read_pdf(pdf_file.name)
        app_state.cover_letter_text = cover_letter_text
        return f"✅ Cover letter uploaded! ({len(cover_letter_text)} characters)"
    except Exception as e:
        return f"❌ Error processing cover letter PDF: {str(e)}"

def update_job_description(job_desc):
    """Update job description"""
    app_state.job_description = job_desc
    return "✅ Job description updated!" if job_desc.strip() else "⚠️ Job description cleared"

def switch_mode(new_mode):
    """Switch between job seeker and HR recruiter modes"""
    # Store current state
    previous_resume = app_state.resume_text
    previous_cover_letter = app_state.cover_letter_text
    previous_job_description = app_state.job_description
    previous_candidate_name = app_state.candidate_name
    
    # Only reset chat history and mode
    app_state.chat_history = []
    app_state.current_mode = new_mode
    
    # Restore the previous state
    app_state.resume_text = previous_resume
    app_state.cover_letter_text = previous_cover_letter
    app_state.job_description = previous_job_description
    app_state.candidate_name = previous_candidate_name
    
    if new_mode == "job_seeker":
        return "🔄 Switched to Job Seeker Mode: I'll interview you based on the job description", []
    else:
        return "🔄 Switched to HR Recruiter Mode: I'll act as the candidate you're interviewing", []

def get_ats_analysis():
    """Get ATS analysis for uploaded resume and job description"""
    if not app_state.job_description.strip():
        return "❌ Please enter a job description first."
    
    if not app_state.resume_text.strip():
        return "❌ Please upload a resume PDF first."
    
    try:
        app_state.ats_analysis_result = calculate_ats_score(
            app_state.resume_text, 
            app_state.job_description, 
            client
        )
        
        result = f"""# 📊 ATS Analysis Results for {app_state.candidate_name}

## 🎯 Overall Score: {app_state.ats_analysis_result.ats_score}/100

### 📋 **Detailed Analysis:**
{app_state.ats_analysis_result.recommendations[0] if app_state.ats_analysis_result.recommendations else 'Analysis completed successfully'}

### 💡 **Key Recommendations:**
{chr(10).join('• ' + rec for rec in app_state.ats_analysis_result.recommendations[1:]) if len(app_state.ats_analysis_result.recommendations) > 1 else '• Review the detailed analysis above'}

---
*This analysis compares the resume against the job description for keyword matching, skills alignment, and overall relevance.*
        """
        return result
    except Exception as e:
        return f"❌ Error performing ATS analysis: {str(e)}"

def chat_interface(message, history):
    """Main chat interface function"""
    
    # Check if we have the necessary information
    if not app_state.resume_text.strip():
        return "⚠️ Please upload a resume first before starting the conversation."
    
    # Set system prompt based on current mode
    if app_state.current_mode == "job_seeker":
        # AI acts as interviewer, user is the job seeker
        if not app_state.job_description.strip():
            return "⚠️ Please provide a job description first so I can conduct a proper interview."
        
        system_prompt = set_interviewer_prompt(
            app_state.candidate_name, 
            app_state.resume_text, 
            app_state.job_description,
            app_state.cover_letter_text
        )
            
    else:  # hr_recruiter mode
        # AI acts as the candidate, user is the recruiter
        if not app_state.job_description.strip():
            return "⚠️ Please provide a job description first so I know what role I'm interviewing for."
        
        system_prompt = set_candidate_prompt(
            app_state.candidate_name,
            app_state.resume_text,
            app_state.job_description,
            app_state.cover_letter_text
        )
    
    # Generate response
    messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": message}]
    
    try:
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            messages=messages
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"❌ I apologize, but I encountered an error: {str(e)}"

def create_interface():
    """Create the Gradio interface with improved layout"""
    
    # Custom CSS for better styling
    custom_css = """
    .mode-card {
        border: 2px solid #e1e5e9;
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
    }
    .upload-section {
        background: #f8fafc;
        border-radius: 8px;
        padding: 12px;
        margin: 4px 0;
    }
    .status-success {
        color: #16a34a;
        font-weight: bold;
    }
    .status-error {
        color: #dc2626;
        font-weight: bold;
    }
    .status-warning {
        color: #ca8a04;
        font-weight: bold;
    }
    """
    
    with gr.Blocks(title="🎯 AI Recruitment Assistant", theme=gr.themes.Soft(), css=custom_css) as interface:
        
        # Header
        with gr.Row():
            gr.Markdown("""
            # 🎯 AI Recruitment Assistant
            
            **Practice interviews and get ATS insights with AI-powered assistance**
            """, elem_classes="header")
        
        # Mode explanation cards
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("""
                ### 🧑‍💼 Job Seeker Mode
                **You are the candidate**
                - Upload your resume & job description
                - AI interviews you with relevant questions
                - Practice answering interview questions
                - Get ATS score for your resume
                """, elem_classes="mode-card")
            
            with gr.Column(scale=1):
                gr.Markdown("""
                ### 👔 HR Recruiter Mode
                **You are the interviewer**
                - Upload candidate's resume & job description  
                - AI acts as the candidate
                - Practice conducting interviews
                - Evaluate candidate-job fit
                """, elem_classes="mode-card")
        
        # Main interface
        with gr.Row():
            # Left Panel - Controls
            with gr.Column(scale=2):
                
                # Mode Selection
                with gr.Group():
                    gr.Markdown("## 🔄 Select Mode")
                    mode_selector = gr.Radio(
                        choices=[
                            ("🧑‍💼 Job Seeker (I'm being interviewed)", "job_seeker"), 
                            ("👔 HR Recruiter (I'm interviewing)", "hr_recruiter")
                        ], 
                        value="job_seeker",
                        label="Choose Your Role",
                        info="This determines who the AI acts as"
                    )
                    
                    mode_status = gr.Markdown(
                        "🧑‍💼 **Job Seeker Mode Active:** Upload your resume and JD, then I'll interview you",
                        elem_classes="status-success"
                    )
                
                # Document Upload Section
                with gr.Group():
                    gr.Markdown("## 📄 Upload Documents")
                    
                    with gr.Tab("📋 Resume"):
                        resume_file = gr.File(
                            label="Upload Resume (PDF)", 
                            file_types=[".pdf"],
                            file_count="single",
                            elem_classes="upload-section"
                        )
                        
                        candidate_name_display = gr.Textbox(
                            label="👤 Detected Name",
                            value="(Upload resume to detect name)",
                            interactive=False
                        )
                        
                        resume_preview = gr.Textbox(
                            label="📄 Resume Preview",
                            lines=4,
                            interactive=False,
                            visible=False
                        )
                    
                    with gr.Tab("📝 Cover Letter (Optional)"):
                        cover_letter_file = gr.File(
                            label="Upload Cover Letter (PDF)", 
                            file_types=[".pdf"],
                            file_count="single",
                            elem_classes="upload-section"
                        )
                        
                        cover_letter_status = gr.Markdown("No cover letter uploaded")
                    
                    with gr.Tab("💼 Job Description"):
                        job_desc_input = gr.Textbox(
                            label="Job Description",
                            placeholder="Paste the complete job description here...\n\nInclude:\n- Role responsibilities\n- Required skills\n- Experience requirements\n- Company information",
                            lines=8,
                            elem_classes="upload-section"
                        )
                        
                        job_status = gr.Markdown("⚠️ No job description provided")
                
                # Status Panel
                with gr.Group():
                    gr.Markdown("## ℹ️ Status")
                    overall_status = gr.Markdown(
                        "📋 **Ready to start:** Upload resume and job description",
                        elem_classes="status-warning"
                    )
                
                # ATS Analysis Section
                with gr.Group():
                    gr.Markdown("## 📊 ATS Analysis")
                    ats_button = gr.Button(
                        "🔍 Analyze Resume vs Job Description", 
                        variant="primary", 
                        size="lg"
                    )
            
            # Right Panel - Chat Interface
            with gr.Column(scale=3):
                gr.Markdown("## 💬 Interview Chat")
                
                chat_interface_component = gr.ChatInterface(
                    fn=chat_interface,
                    chatbot=gr.Chatbot(
                        label="Interview Session",
                        height=600,
                        show_copy_button=True
                    ),
                    title=None,
                    description=None
                )
        
        # ATS Results Panel
        with gr.Row():
            with gr.Column():
                ats_result = gr.Markdown("📋 Upload resume and job description, then click 'Analyze' for ATS insights")
        
        # Event Handlers
        def on_mode_change(new_mode):
            status, cleared_history = switch_mode(new_mode)
            
            if new_mode == "job_seeker":
                mode_description = "🧑‍💼 **Job Seeker Mode Active:** Upload your resume and JD, then I'll interview you"
                mode_class = "status-success"
            else:
                mode_description = "👔 **HR Recruiter Mode Active:** Upload candidate's resume and JD, then I'll act as the candidate"
                mode_class = "status-success"
            
            return (
                mode_description,
                "(Upload resume to detect name)",
                "📋 **Ready to start:** Upload resume and job description",
                "⚠️ No job description provided",
                "No cover letter uploaded",
                "📋 Upload resume and job description, then click 'Analyze' for ATS insights",
                gr.update(visible=False)
            )
        
        def on_resume_upload(file):
            status, preview, name = process_resume_pdf(file)
            
            # Update overall status
            if app_state.resume_text and app_state.job_description:
                overall_status_text = "✅ **Ready to chat:** All documents uploaded successfully!"
                overall_class = "status-success"
            elif app_state.resume_text:
                overall_status_text = "⚠️ **Almost ready:** Upload job description to start"
                overall_class = "status-warning"
            else:
                overall_status_text = "📋 **Getting started:** Upload resume first"
                overall_class = "status-warning"
            
            return (
                status,
                preview, 
                gr.update(visible=bool(preview.strip())), 
                name,
                overall_status_text
            )
        
        def on_cover_letter_upload(file):
            status = process_cover_letter_pdf(file)
            return status
        
        def on_job_desc_change(text):
            status = update_job_description(text)
            
            # Update overall status
            if app_state.resume_text and app_state.job_description:
                overall_status_text = "✅ **Ready to chat:** All documents uploaded successfully!"
            elif app_state.job_description:
                overall_status_text = "⚠️ **Almost ready:** Upload resume to start"
            else:
                overall_status_text = "⚠️ Job description cleared"
            
            return status, overall_status_text
        
        def on_ats_click():
            return get_ats_analysis()
        
        # Connect Events
        mode_selector.change(
            fn=on_mode_change,
            inputs=[mode_selector],
            outputs=[
                mode_status,
                candidate_name_display,
                overall_status,
                job_status,
                cover_letter_status,
                ats_result,
                resume_preview
            ]
        )
        
        resume_file.upload(
            fn=on_resume_upload,
            inputs=[resume_file],
            outputs=[
                mode_status,  # Using mode_status as a proxy for resume status
                resume_preview, 
                resume_preview, 
                candidate_name_display,
                overall_status
            ]
        )
        
        cover_letter_file.upload(
            fn=on_cover_letter_upload,
            inputs=[cover_letter_file],
            outputs=[cover_letter_status]
        )
        
        job_desc_input.change(
            fn=on_job_desc_change,
            inputs=[job_desc_input],
            outputs=[job_status, overall_status]
        )
        
        ats_button.click(
            fn=on_ats_click,
            outputs=[ats_result]
        )
    
    return interface

# Launch the interface
if __name__ == "__main__":
    interface = create_interface()
    interface.queue().launch(share=True, debug=True)