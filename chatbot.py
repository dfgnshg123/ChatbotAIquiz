# -*- coding: utf-8 -*-
# ======================================================================================
# PROJECT: AI QUIZ CHATBOT
# STUDENT: Lu Nhat Truong
# VERSION: "9-Month Project" (Advanced - File Upload & Save)
# ======================================================================================

# --- PART 1: IMPORT NECESSARY LIBRARIES ---
import streamlit as st
import google.generativeai as genai
import json         # For handling JSON data from AI
import re           # For robust JSON parsing (Regular Expression)
import io           # For handling file uploads in memory

# Libraries for reading specific file types
try:
    import PyPDF2       # To read .pdf files
    import docx         # To read .docx files
except ImportError:
    st.error("ERROR: Required libraries are missing. Please run: pip install PyPDF2 python-docx")
    st.stop()

# ======================================================================================
# PART 2: AI CONFIGURATION AND API CONNECTION
# ======================================================================================

# --- Configure API Key ---
# WARNING: DO NOT SHARE YOUR API KEY.
# Replace 'YOUR_API_KEY_HERE' with your actual API Key.
API_KEY = "AIzaSyBvRinq1e-AmJdFqy4_1k_McDIe2q1BWRo" 

try:
    genai.configure(api_key=API_KEY)
except Exception as e:
    st.error(f"API Key Configuration Error: {e}. Please check your API Key!")
    st.stop()

# --- AI Core Function ---
def get_gemini_response(prompt):
    """
    Sends a prompt to the Gemini AI and returns the text response.
    """
    try:
        # --- USER REQUESTED MODEL ---
        # Using the specific model name you provided
        model = genai.GenerativeModel('models/gemini-pro-latest')
        # --- END USER REQUESTED MODEL ---
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Error calling AI (model 'models/gemini-pro-latest'): {e}")
        return None

# --- Robust JSON Parser (FIX FOR "INVALID DATA" ERROR) ---
def parse_ai_response_robust(response_text):
    """
    Uses Regular Expression (re) to find and extract the JSON block 
    from the AI's response, even if there is "garbage" text around it.
    This fixes the "AI da tra ve du lieu khong hop le" error.
    """
    if not response_text:
        return None
        
    # This regex pattern finds any text block starting with { and ending with }
    # re.DOTALL makes . match newlines as well
    match = re.search(r'\{.*\}', response_text, re.DOTALL)
    
    if match:
        json_string = match.group(0)
        try:
            # Convert the clean JSON string into a Python dictionary
            data = json.loads(json_string)
            return data
        except json.JSONDecodeError:
            st.error("AI returned a malformed JSON. Please try again.")
            print(f"JSON Error: Could not parse: {json_string}")
            return None
    else:
        # If no { } block is found at all
        st.error("AI returned invalid data (no JSON block found). Please try again.")
        print(f"JSON Error: No JSON found in: {response_text}")
        return None

# ======================================================================================
# PART 3: FILE PROCESSING FUNCTIONS (NEW FEATURE)
# ======================================================================================

# Max characters per "chunk" sent to the AI
# We cannot send a 200-page book at once
MAX_CHUNK_SIZE = 2000 # 2000 characters

def read_txt_file(uploaded_file):
    # Read a simple .txt file
    stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
    return stringio.read()

def read_pdf_file(uploaded_file):
    # Use PyPDF2 to read a .pdf file
    try:
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"Error reading PDF file: {e}")
        return None

def read_docx_file(uploaded_file):
    # Use python-docx to read a .docx file
    try:
        doc = docx.Document(uploaded_file)
        text = ""
        for para in doc.paragraphs:
            text += para.text + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading DOCX file: {e}")
        return None

def process_uploaded_file(uploaded_file):
    """
    Checks the file type of the uploaded file and calls the
    correct reading function.
    """
    if uploaded_file is None:
        return None

    file_type = uploaded_file.type
    
    if file_type == "text/plain":
        return read_txt_file(uploaded_file)
    elif file_type == "application/pdf":
        return read_pdf_file(uploaded_file)
    elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return read_docx_file(uploaded_file)
    else:
        st.error(f"File type '{file_type}' is not supported. Please upload .txt, .pdf, or .docx.")
        return None

def get_text_chunks(full_text):
    """
    Splits a long text into smaller "chunks" that the AI can handle.
    """
    if len(full_text) <= MAX_CHUNK_SIZE:
        return [full_text] # If text is short, return as one chunk
        
    chunks = []
    for i in range(0, len(full_text), MAX_CHUNK_SIZE):
        chunks.append(full_text[i : i + MAX_CHUNK_SIZE])
    return chunks

# ======================================================================================
# PART 4: SESSION STATE MANAGEMENT
# ======================================================================================
# This is the app's "short-term memory".
# It's CRITICAL for storing score, current question, etc.
# because Streamlit reruns the script on every interaction.

if 'user_score' not in st.session_state:
    st.session_state.user_score = 0
if 'questions_answered' not in st.session_state:
    st.session_state.questions_answered = 0
if 'current_question_data' not in st.session_state:
    st.session_state.current_question_data = None 
if 'answer_feedback' not in st.session_state:
    st.session_state.answer_feedback = None
if 'file_context' not in st.session_state:
    # Stores the text content read from the file
    st.session_state.file_context = None 
if 'generated_questions_bank' not in st.session_state:
    # Stores ALL generated questions for saving (NEW FEATURE)
    st.session_state.generated_questions_bank = [] 

# ======================================================================================
# PART 5: CORE LOGIC FUNCTIONS
# ======================================================================================

# --- Function 1: Generate New Question (Upgraded) ---
def generate_new_question(mode="topic", topic=None, context_chunk=None):
    """
    Generates a new question.
    - mode="topic": Generates based on a user-provided topic.
    - mode="context": Generates based on a chunk of text from a file (NEW).
    """
    
    # 1. Create the prompt
    if mode == "topic":
        if not topic:
            st.warning("Please enter a topic to review!")
            return
        
        prompt_content = f'the topic: "{topic}"'
        spinner_text = f"🤖 AI is generating a question about '{topic}'..."
        
    elif mode == "context":
        if not context_chunk:
            st.error("Error: No file content provided to generate a question.")
            return
            
        # We "wrap" the context text for the AI
        prompt_content = f'the following text content: "{context_chunk}"'
        spinner_text = "🤖 AI is analyzing the document and generating a question..."
        
    else:
        st.error("Error: Unknown question generation mode.")
        return

    # This is the standardized "Master Prompt".
    # We command the AI to return ONLY a valid JSON.
    prompt = f"""
    You are a professional AI assistant specializing in creating multiple-choice quizzes.
    Your task is to generate ONE multiple-choice question based on {prompt_content}.

    Requirements:
    1. The question must have 4 options (A, B, C, D).
    2. There must be only ONE correct answer.
    3. You must provide a brief, clear explanation for the correct answer.
    4. There must be NO other text outside the JSON block.
    5. Return ONLY a single, valid JSON string in the following format:

    {{
      "question": "What is the content of the question?",
      "options": [
        "Option A content",
        "Option B content",
        "Option C content",
        "Option D content"
      ],
      "correct_answer_index": N,
      "explanation": "A brief explanation of why this answer is correct."
    }}

    Where 'correct_answer_index' is the index of the correct answer (0 for A, 1 for B, 2 for C, 3 for D).
    """
    
    # 2. Call AI and Process Result
    with st.spinner(spinner_text):
        response_text = get_gemini_response(prompt)
        
        if response_text:
            # Use our powerful JSON parser
            question_data = parse_ai_response_robust(response_text)
            
            if question_data:
                # Save to "session memory"
                st.session_state.current_question_data = question_data
                # Save to the "bank" for download (NEW)
                st.session_state.generated_questions_bank.append(question_data)
                # Clear old feedback
                st.session_state.answer_feedback = None

# --- Function 2: Handle User's Answer ---
def handle_user_answer(user_choice_index):
    """
    Checks the user's answer, updates the score, and stores feedback.
    """
    q_data = st.session_state.current_question_data
    if not q_data: return

    correct_index = q_data['correct_answer_index']
    explanation = q_data['explanation']
    is_correct = (user_choice_index == correct_index)
    
    if is_correct:
        st.session_state.user_score += 1
        st.session_state.answer_feedback = f"✅ Correct! \n\n**Explanation:** {explanation}"
    else:
        correct_option_text = q_data['options'][correct_index]
        st.session_state.answer_feedback = f"❌ Incorrect. The correct answer was: **{correct_option_text}** \n\n**Explanation:** {explanation}"

    st.session_state.questions_answered += 1
    st.session_state.current_question_data = None # Clear the question
    st.rerun() # Tell Streamlit to refresh the UI

# --- Function 3: Save Questions to File (NEW FEATURE) ---
def save_questions_to_file():
    """
    Prepares the generated question bank for download as a JSON file.
    """
    bank = st.session_state.generated_questions_bank
    if not bank:
        st.warning("No questions have been generated yet!")
        return
        
    try:
        # Convert the list of questions into a "pretty" JSON string
        # indent=2 makes it readable
        # ensure_ascii=False keeps Vietnamese characters
        json_data = json.dumps(bank, indent=2, ensure_ascii=False)
        
        # Create the download button
        st.download_button(
            label="Download Question Bank (JSON)",
            data=json_data,
            file_name="cau_hoi_da_luu.json",
            mime="application/json"
        )
        
    except Exception as e:
        st.error(f"Error creating JSON file: {e}")

# ======================================================================================
# PART 6: DRAW THE USER INTERFACE (UI)
# ======================================================================================

# --- Page Configuration ---
st.set_page_config(
    page_title="AI Quiz Chatbot (Project)",
    page_icon="🎓",
    layout="wide" # Use "wide" layout for more space
)

# --- Sidebar ---
with st.sidebar:
    st.title("🎓 Control Panel")
    
    # --- THIS LINE IS THE FIX for the StreamlitSecretNotFoundError ---
    st.write(f"Welcome, Lu Nhat Truong!")
    # --- END FIX ---
    
    st.divider()
    
    st.header("📈 Your Score")
    
    col1, col2 = st.columns(2)
    col1.metric(label="Total Score", value=st.session_state.user_score)
    col2.metric(label="Answered", value=st.session_state.questions_answered)
    
    if st.button("Reset Score & History"):
        st.session_state.user_score = 0
        st.session_state.questions_answered = 0
        st.session_state.generated_questions_bank = []
        st.session_state.file_context = None
        st.session_state.current_question_data = None
        st.session_state.answer_feedback = None
        st.rerun()

    st.divider()
    
    # --- Save Function (NEW) ---
    st.header("💾 Save Questions")
    st.write(f"{len(st.session_state.generated_questions_bank)} questions generated.")
    # Call the save function to create the button
    save_questions_to_file()


# --- Main Display Area ---
st.title("🤖 AI Quiz Chatbot ")

# --- Use TABS for different modes (NEW UI) ---
tab_topic, tab_file = st.tabs([
    "📝 Review by Topic", 
    "📁 Review from Document"
])

# --- Tab 1: Review by Topic ---
with tab_topic:
    st.header("Generate Question by Topic")
    st.write("Enter any topic (e.g., 'Vietnamese History', 'Calculus 1', 'A* Algorithm') and the AI will create a question.")
    
    topic_input = st.text_input("Your Topic:", key="topic_input")
    
    if st.button("Generate from Topic", key="btn_topic"):
        generate_new_question(mode="topic", topic=topic_input)

# --- Tab 2: Review from Document (NEW) ---
with tab_file:
    st.header("Generate Questions from Your Document")
    st.write("Upload a .txt, .pdf, or .docx file. The AI will read it and create questions based on its content.")
    
    uploaded_file = st.file_uploader(
        "Choose a file", 
        type=["txt", "pdf", "docx"],
        key="file_uploader"
    )
    
    if uploaded_file:
        # Process the file *only once* when it's first uploaded
        if st.session_state.file_context is None:
            with st.spinner(f"Processing '{uploaded_file.name}'..."):
                full_text = process_uploaded_file(uploaded_file)
                if full_text:
                    # Split the text into manageable chunks
                    st.session_state.file_context = get_text_chunks(full_text)
                    st.success(f"File processed! Found {len(full_text)} characters, split into {len(st.session_state.file_context)} chunk(s).")
                else:
                    st.error("Could not read content from this file.")
    
    # If a file has been processed and is in memory
    if st.session_state.file_context:
        st.info(f"Document is loaded and ready. You can now generate questions from it.")
        
        context_chunks = st.session_state.file_context
        selected_chunk_index = 0
        
        # If the file was long and split into many chunks, let the user choose
        if len(context_chunks) > 1:
            selected_chunk_index = st.selectbox(
                f"This document is long ({len(context_chunks)} chunks). Choose a section to generate a question from:",
                options=range(len(context_chunks)),
                format_func=lambda x: f"Section {x+1}/{len(context_chunks)}"
            )
        
        if st.button("Generate from Document", key="btn_file"):
            selected_chunk = context_chunks[selected_chunk_index]
            generate_new_question(mode="context", context_chunk=selected_chunk)

# ======================================================================================
# PART 7: QUESTION & FEEDBACK DISPLAY AREA
# ======================================================================================

st.divider() # A big horizontal line

# This logic decides WHAT to show in the main area

# --- CASE 1: A question is active and waiting for an answer ---
if st.session_state.current_question_data:
    q_data = st.session_state.current_question_data
    
    # Display the question in a formatted box
    with st.container(border=True):
        st.subheader(f"Question (Score: {st.session_state.user_score} | Answered: {st.session_state.questions_answered})")
        st.markdown(f"**{q_data['question']}**") # Bold question
        st.write("") # Spacer
        
        # Display the 4 answer buttons in 2 columns
        col1, col2 = st.columns(2)
        
        options = q_data['options']
        buttons = [
            col1.button(f"**A:** {options[0]}", use_container_width=True, key="btn_A"),
            col2.button(f"**B:** {options[1]}", use_container_width=True, key="btn_B"),
            col1.button(f"**C:** {options[2]}", use_container_width=True, key="btn_C"),
            col2.button(f"**D:** {options[3]}", use_container_width=True, key="btn_D")
        ]
        
        # Check which button was pressed
        for i, (button_pressed, option) in enumerate(zip(buttons, options)):
            if button_pressed:
                handle_user_answer(i) # Call handler with the index (0, 1, 2, or 3)

# --- CASE 2: No active question (App start OR just answered) ---
else:
    # If we just answered, show the feedback
    if st.session_state.answer_feedback:
        if "Correct" in st.session_state.answer_feedback:
            st.success(st.session_state.answer_feedback)
        else:
            st.error(st.session_state.answer_feedback)
        
        st.info("Please generate the next question from either Tab above.")
    
    # If the app just started
    else:
        st.info("Welcome! Please select a Tab (Topic or Document) to begin.")