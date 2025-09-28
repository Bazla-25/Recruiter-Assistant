from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
import uuid
import os

# Import all functions from your existing file
# Replace 'your_existing_file' with the actual name of your original Python file
try:
    from Applicant_agent import (
        set_env,
        read_pdf,
        extract_name_from_resume,
        calculate_ats_score,
        set_interviewer_prompt,
        set_candidate_prompt,
        ATSAnalysis
    )
except ImportError:
    print("Please rename your existing file to match the import above, or update the import statement")
    print("For example, if your file is 'recruitment_assistant.py', change the import to:")
    print("from recruitment_assistant import (...)")
    raise

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')
CORS(app)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize Azure OpenAI client using your existing function
az_model_client, client = set_env()

# Initialize session variables
def init_session():
    if 'current_mode' not in session:
        session['current_mode'] = "job_seeker"
    if 'candidate_name' not in session:
        session['candidate_name'] = "Candidate"
    if 'resume_text' not in session:
        session['resume_text'] = ""
    if 'cover_letter_text' not in session:
        session['cover_letter_text'] = ""
    if 'job_description' not in session:
        session['job_description'] = ""
    if 'chat_history' not in session:
        session['chat_history'] = []

@app.route('/')
def index():
    init_session()
    return render_template('index.html')

@app.route('/api/upload-resume', methods=['POST'])
def upload_resume():
    init_session()
    
    if 'resume' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['resume']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and file.filename.endswith('.pdf'):
        filename = str(uuid.uuid4()) + '.pdf'
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        resume_text = read_pdf(filepath)
        if resume_text and not resume_text.startswith("Error reading PDF"):
            candidate_name = extract_name_from_resume(resume_text)
            session['resume_text'] = resume_text
            session['candidate_name'] = candidate_name
            
            # Clean up file
            os.remove(filepath)
            
            return jsonify({
                'success': True,
                'candidate_name': candidate_name,
                'preview': resume_text[:300] + "..." if len(resume_text) > 300 else resume_text
            })
        else:
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': 'Could not read PDF file'}), 400
    
    return jsonify({'error': 'Invalid file format. Please upload a PDF.'}), 400

@app.route('/api/upload-cover-letter', methods=['POST'])
def upload_cover_letter():
    init_session()
    
    if 'cover_letter' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['cover_letter']
    if file.filename == '':
        session['cover_letter_text'] = ''
        return jsonify({'success': True, 'message': 'Cover letter removed'})
    
    if file and file.filename.endswith('.pdf'):
        filename = str(uuid.uuid4()) + '.pdf'
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        cover_letter_text = read_pdf(filepath)
        if cover_letter_text and not cover_letter_text.startswith("Error reading PDF"):
            session['cover_letter_text'] = cover_letter_text
            os.remove(filepath)
            return jsonify({'success': True, 'message': 'Cover letter uploaded successfully'})
        else:
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': 'Could not read PDF file'}), 400
    
    return jsonify({'error': 'Invalid file format. Please upload a PDF.'}), 400

@app.route('/api/job-description', methods=['POST'])
def set_job_description():
    init_session()
    
    data = request.get_json()
    job_description = data.get('job_description', '')
    session['job_description'] = job_description
    return jsonify({'success': True, 'message': 'Job description updated'})

@app.route('/api/set-mode', methods=['POST'])
def set_mode():
    init_session()
    
    data = request.get_json()
    mode = data.get('mode', 'job_seeker')
    session['current_mode'] = mode
    session['chat_history'] = []  # Reset chat history
    return jsonify({'success': True, 'mode': mode})

@app.route('/api/ats-analysis', methods=['GET'])
def get_ats_analysis():
    init_session()
    
    resume_text = session.get('resume_text', '')
    job_description = session.get('job_description', '')
    
    if not resume_text:
        return jsonify({'error': 'Please upload a resume first'}), 400
    
    if not job_description:
        return jsonify({'error': 'Please provide a job description first'}), 400
    
    try:
        analysis = calculate_ats_score(resume_text, job_description, client)
        return jsonify({
            'ats_score': analysis.ats_score,
            'keyword_matches': analysis.keyword_matches,
            'missing_keywords': analysis.missing_keywords,
            'recommendations': analysis.recommendations,
            'strengths': analysis.strengths,
            'weaknesses': analysis.weaknesses
        })
    except Exception as e:
        return jsonify({'error': f'ATS analysis failed: {str(e)}'}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    init_session()
    
    data = request.get_json()
    message = data.get('message', '')
    
    resume_text = session.get('resume_text', '')
    job_description = session.get('job_description', '')
    cover_letter_text = session.get('cover_letter_text', '')
    candidate_name = session.get('candidate_name', 'Candidate')
    mode = session.get('current_mode', 'job_seeker')
    chat_history = session.get('chat_history', [])
    
    if not resume_text:
        return jsonify({'error': 'Please upload a resume first'}), 400
    
    if not job_description:
        return jsonify({'error': 'Please provide a job description first'}), 400
    
    # Set system prompt based on mode
    if mode == 'job_seeker':
        system_prompt = set_interviewer_prompt(candidate_name, resume_text, job_description, cover_letter_text)
    else:
        system_prompt = set_candidate_prompt(candidate_name, resume_text, job_description, cover_letter_text)
    
    # Prepare messages
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history)
    messages.append({"role": "user", "content": message})
    
    try:
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            messages=messages
        )
        
        ai_response = response.choices[0].message.content
        
        # Update chat history
        chat_history.extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": ai_response}
        ])
        session['chat_history'] = chat_history
        
        return jsonify({'response': ai_response})
        
    except Exception as e:
        return jsonify({'error': f'Chat error: {str(e)}'}), 500

@app.route('/api/clear-chat', methods=['POST'])
def clear_chat():
    init_session()
    session['chat_history'] = []
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)