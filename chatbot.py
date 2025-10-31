# -*- coding: utf-8 -*-
# ======================================================================================
# PROJECT: AI QUIZ CHATBOT (Phiên bản "9 Tháng")
# STUDENT: Lu Nhat Truong
# VERSION: 2.0 (Advanced State Management, Multi-Language, File Processing)
#
# NOTE ON STRUCTURE:
# For a real 9-month project, this single 500+ line file would be split into:
# 1. `main_app.py`: (This file) For Streamlit UI and state management.
# 2. `ai_core.py`: (PART 2, 5) For all Gemini API calls and prompt engineering.
# 3. `file_processor.py`: (PART 3) For reading PDF, DOCX, TXT files.
# 4. `utils.py`: (PART 4, 10) For helper functions like save_to_txt.
# However, for Streamlit's single-file deployment model, we keep it unified.
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
        # Keeping the exact model name as requested by the user
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
    Uses Regular Expression (re) to find and extract the JSON *list*
    from the AI's response, even if there is "garbage" text around it.
    """
    if not response_text:
        return None
        
    # This regex pattern finds any text block starting with [ and ending with ]
    # (Because we are now asking for a LIST of questions)
    match = re.search(r'\[.*\]', response_text, re.DOTALL)
    
    if match:
        json_string = match.group(0)
        try:
            # Convert the clean JSON string into a Python list of dictionaries
            data = json.loads(json_string)
            if isinstance(data, list): # Ensure it's a list
                return data
            else:
                st.error("AI returned a valid JSON, but not a LIST as requested. Please try again.")
                return None
        except json.JSONDecodeError:
            st.error("AI returned a malformed JSON list. Please try again.")
            print(f"JSON Error: Could not parse: {json_string}")
            return None
    else:
        # If no [ ] block is found at all
        st.error("AI returned invalid data (no JSON list found). Please try again.")
        print(f"JSON Error: No JSON list found in: {response_text}")
        return None

# ======================================================================================
# PART 3: FILE PROCESSING FUNCTIONS (UPGRADED FOR LARGE FILES)
# ======================================================================================

# UPGRADED CHUNK SIZE for 10-question generation
MAX_CHUNK_SIZE = 8000 # 8000 characters (~4-5 pages of text)

def read_txt_file(uploaded_file):
    stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
    return stringio.read()

def read_pdf_file(uploaded_file):
    # This still reads the whole file into memory first,
    # as page-by-page streaming read is complex.
    # The 30MB file crash is a memory limit, not a Streamlit limit.
    try:
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading PDF file: {e}")
        return None

def read_docx_file(uploaded_file):
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
    Reads the uploaded file and returns its FULL text content.
    """
    if uploaded_file is None:
        return None
    
    file_type = uploaded_file.type
    full_text = ""
    
    if file_type == "text/plain":
        full_text = read_txt_file(uploaded_file)
    elif file_type == "application/pdf":
        full_text = read_pdf_file(uploaded_file)
    elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        full_text = read_docx_file(uploaded_file)
    else:
        st.error(f"File type '{file_type}' is not supported. Please upload .txt, .pdf, or .docx.")
        return None
    
    if not full_text:
        st.error("Could not read any text from the file. It might be empty or scanned images.")
        return None
        
    return full_text

def get_text_chunks(full_text):
    """
    Splits a long text into larger "chunks" for the 10-question prompt.
    """
    if not full_text:
        return []
    if len(full_text) <= MAX_CHUNK_SIZE:
        return [full_text] # If text is short, return as one chunk
        
    chunks = []
    for i in range(0, len(full_text), MAX_CHUNK_SIZE):
        chunks.append(full_text[i : i + MAX_CHUNK_SIZE])
    st.success(f"File is large. Split into {len(chunks)} sections.")
    return chunks

# ======================================================================================
# PART 4: SESSION STATE MANAGEMENT (COMPLETELY RE-ARCHITECTED)
# ======================================================================================
# This is the app's "brain".

if 'language' not in st.session_state:
    st.session_state.language = "Tiếng Việt" # NEW: Language state
if 'quiz_questions' not in st.session_state:
    # This is the NEW core state. A list of question objects.
    st.session_state.quiz_questions = []
if 'file_context_chunks' not in st.session_state:
    # Stores the text chunks read from the file
    st.session_state.file_context_chunks = []
if 'generated_questions_bank' not in st.session_state:
    # Stores ALL questions ever generated (for saving and deduplication)
    st.session_state.generated_questions_bank = []

# --- Dictionaries for Multi-Language (NEW) ---
lang_dict = {
    "Tiếng Việt": {
        "welcome": "Chào mừng",
        "control_panel": "Bảng điều khiển",
        "your_score": "Kết quả của bạn",
        "total_score": "Tổng điểm",
        "answered": "Đã trả lời",
        "reset_button": "Reset Điểm & Lịch sử",
        "reset_success": "Đã reset toàn bộ!",
        "save_header": "Lưu trữ",
        "save_count": "câu hỏi đã tạo.",
        "save_button": "Tải Ngân hàng Câu hỏi (.txt)",
        "save_no_q": "Chưa có câu hỏi nào để lưu!",
        "save_error": "Lỗi khi tạo file TXT",
        "lang_select": "Chọn Ngôn ngữ",
        "main_title": "🤖 Chatbot AI Hỗ trợ Ôn tập Trắc nghiệm (Bản 9 Tháng)",
        "tab_topic": "📝 Ôn tập theo Chủ đề",
        "tab_file": "📁 Ôn tập từ Tài liệu",
        "topic_header": "Tạo 10 câu hỏi theo chủ đề",
        "topic_desc": "Nhập một chủ đề (ví dụ: 'Lịch sử Việt Nam', 'Giải tích 1') và AI sẽ tạo một bộ 10 câu hỏi.",
        "topic_input": "Chủ đề của bạn:",
        "topic_button": "Tạo 10 câu hỏi từ Chủ đề",
        "topic_no_topic": "Vui lòng nhập một chủ đề!",
        "file_header": "Tạo 10 câu hỏi từ tài liệu",
        "file_desc": "Tải lên file .txt, .pdf, hoặc .docx. AI sẽ đọc và tạo 10 câu hỏi từ nội dung file.",
        "file_uploader": "Chọn một file",
        "file_processing": "Đang xử lý file",
        "file_processed": "Đã xử lý xong file!",
        "file_processed_desc": "Tìm thấy {char_count} ký tự, chia thành {chunk_count} phần.",
        "file_read_error": "Không thể đọc nội dung từ file này.",
        "file_ready": "Đã tải và xử lý xong tài liệu. Sẵn sàng tạo câu hỏi.",
        "file_chunk_select": "Tài liệu dài ({chunk_count} phần). Chọn một phần để tạo 10 câu hỏi:",
        "file_chunk_format": "Phần {i_plus_1}/{chunk_count}",
        "file_button": "Tạo 10 câu hỏi từ Tài liệu",
        "question_header": "Câu hỏi {i_plus_1}/10",
        "feedback_correct": "✅ Chính xác!",
        "feedback_incorrect": "❌ Sai rồi! Đáp án đúng là:",
        "feedback_explanation": "Giải thích chi tiết:",
        "welcome_info": "Chào mừng! Hãy chọn một Tab (Chủ đề hoặc Tài liệu) để bắt đầu.",
        "generating_questions": "🤖 AI đang tạo bộ 10 câu hỏi...",
        "generating_explanation": "🤖 AI đang phân tích câu trả lời...",
        "dedup_history": "Lịch sử câu hỏi đã tạo (để tránh trùng lặp)",
        "prompt_explanation_header": "Phân tích lý do các đáp án khác sai (nếu có)",
        "prompt_structure_error": "Lỗi cấu trúc câu hỏi từ AI"
    },
    "English": {
        "welcome": "Welcome",
        "control_panel": "Control Panel",
        "your_score": "Your Score",
        "total_score": "Total Score",
        "answered": "Answered",
        "reset_button": "Reset Score & History",
        "reset_success": "History reset!",
        "save_header": "Save Questions",
        "save_count": "questions generated.",
        "save_button": "Download Question Bank (.txt)",
        "save_no_q": "No questions to save!",
        "save_error": "Error creating TXT file",
        "lang_select": "Select Language",
        "main_title": "🤖 AI Quiz Chatbot (9-Month Version)",
        "tab_topic": "📝 Review by Topic",
        "tab_file": "📁 Review from Document",
        "topic_header": "Generate 10 Questions by Topic",
        "topic_desc": "Enter a topic (e.g., 'Vietnamese History', 'Calculus 1') and the AI will generate a 10-question quiz.",
        "topic_input": "Your Topic:",
        "topic_button": "Generate 10 Questions from Topic",
        "topic_no_topic": "Please enter a topic!",
        "file_header": "Generate 10 Questions from Document",
        "file_desc": "Upload a .txt, .pdf, or .docx file. The AI will read it and create 10 questions.",
        "file_uploader": "Choose a file",
        "file_processing": "Processing file",
        "file_processed": "File processed!",
        "file_processed_desc": "Found {char_count} characters, split into {chunk_count} section(s).",
        "file_read_error": "Could not read content from this file.",
        "file_ready": "Document is loaded and ready.",
        "file_chunk_select": "Document is long ({chunk_count} sections). Choose a section to generate 10 questions from:",
        "file_chunk_format": "Section {i_plus_1}/{chunk_count}",
        "file_button": "Generate 10 Questions from Document",
        "question_header": "Question {i_plus_1}/10",
        "feedback_correct": "✅ Correct!",
        "feedback_incorrect": "❌ Incorrect! The correct answer was:",
        "feedback_explanation": "Detailed Explanation:",
        "welcome_info": "Welcome! Please select a Tab (Topic or Document) to begin.",
        "generating_questions": "🤖 AI is generating a 10-question quiz...",
        "generating_explanation": "🤖 AI is analyzing your answer...",
        "dedup_history": "History of previously generated questions (to avoid duplicates)",
        "prompt_explanation_header": "Analysis of why other options are incorrect (if applicable)",
        "prompt_structure_error": "Question structure error from AI"
    }
}

# Helper to get text based on current language
def get_lang(key):
    return lang_dict[st.session_state.language][key]

# ======================================================================================
# PART 5: CORE LOGIC FUNCTIONS (FULLY REBUILT)
# ======================================================================================

# --- Function 1: Generate 10 New Questions ---
def generate_new_quiz(mode="topic", topic=None, context_chunk=None):
    """
    Generates a NEW set of 10 questions.
    This will call the AI, parse the response, and reset the quiz.
    """
    
    # 1. Create the prompt
    lang = st.session_state.language
    
    if mode == "topic":
        if not topic:
            st.warning(get_lang("topic_no_topic"))
            return
        prompt_content = f"the topic: '{topic}'"
        
    elif mode == "context":
        if not context_chunk:
            st.error("Error: No file content provided.")
            return
        prompt_content = f'the following text content: "{context_chunk}"'
        
    else:
        st.error("Error: Unknown generation mode.")
        return

    # De-duplication: Get a list of old question texts
    old_questions_list = [q['q_data']['question'] for q in st.session_state.generated_questions_bank]
    history_prompt = f"{get_lang('dedup_history')}: {json.dumps(old_questions_list)}" if old_questions_list else ""

    # This is the "Master Prompt" for a 9-Month Project
    prompt = f"""
    You are a professional AI assistant specializing in creating high-quality, {lang} multiple-choice quizzes.
    Your task is to generate TEN (10) multiple-choice questions based on {prompt_content}.

    CRITICAL REQUIREMENTS:
    1.  LANGUAGE: All content (questions, options, explanations) MUST be in {lang}.
    2.  QUANTITY: You MUST generate exactly 10 questions.
    3.  QUESTION VARIETY: Do NOT just ask 'What is...'. You MUST include varied formats like:
        - 'Which of the following statements is FALSE?'
        - 'All of the following are true EXCEPT...'
        - 'What is the primary reason for...?'
    4.  VALIDATION: (If from document) Ensure the question is answerable from the text and is a high-quality, logical question.
    5.  EXPLANATION (CRITICAL): The explanation MUST be detailed. It must first explain WHY the correct answer is right, and then briefly explain WHY the other three options are WRONG.
    6.  DE-DUPLICATION: (If history is provided) Do NOT generate questions similar to these: {history_prompt}
    7.  FORMAT: Return ONLY a single, valid JSON LIST (an array of 10 objects). Do NOT include any other text, markdown, or explanations outside the main `[` and `]`.

    JSON Format (A LIST of 10 of these objects):
    [
      {{
        "question": "Question text in {lang}?",
        "options": [
          "Option A in {lang}",
          "Option B in {lang}",
          "Option C in {lang}",
          "Option D in {lang}"
        ],
        "correct_answer_index": N,
        "explanation": "Detailed explanation in {lang} covering all 4 options."
      }},
      ... (9 more objects) ...
    ]
    
    Where 'correct_answer_index' is the index (0-3) of the correct answer.
    """
    
    # 2. Call AI and Process Result
    with st.spinner(get_lang("generating_questions")):
        response_text = get_gemini_response(prompt)
        
        if response_text:
            # Use our robust parser
            question_data_list = parse_ai_response_robust(response_text)
            
            if question_data_list and isinstance(question_data_list, list) and len(question_data_list) > 0:
                new_quiz = []
                # Initialize our new state structure
                for q_data in question_data_list:
                    # Basic validation of the AI's response structure
                    if not all(k in q_data for k in ["question", "options", "correct_answer_index", "explanation"]) or len(q_data["options"]) != 4:
                        st.error(f"{get_lang('prompt_structure_error')}: {q_data.get('question', 'Unknown')}")
                        continue
                        
                    new_quiz.append({
                        "q_data": q_data,                # The question data from AI
                        "user_answer_index": None,       # User's choice (e.g., 0, 1, 2, 3)
                        "feedback_visible": False,       # To show/hide explanation
                        "ai_explanation": q_data["explanation"] # Pre-store the explanation
                    })
                
                # Reset the quiz state
                st.session_state.quiz_questions = new_quiz
                # Add these new questions to the permanent bank
                st.session_state.generated_questions_bank.extend(new_quiz)
                # Clear old feedback
                st.session_state.answer_feedback = None # This state is now legacy, but we clear it
                st.rerun() # Refresh the page to show the new quiz
            else:
                st.error("AI did not return a valid list of 10 questions. Please try again.")

# --- Function 2: Handle User's Answer (NEW ARCHITECTURE) ---
def handle_answer(question_index, chosen_index):
    """
    This function is called by the `on_click` of an answer button.
    It updates the state for *that specific question*.
    """
    # Get the specific question from our list
    q_state = st.session_state.quiz_questions[question_index]
    
    # Lock in the user's answer
    q_state["user_answer_index"] = chosen_index
    
    # Make the feedback visible
    q_state["feedback_visible"] = True
    
    # (No st.rerun() needed, on_click handles it)

# --- Function 3: Reset App State ---
def reset_app_state():
    """
    Resets all session state variables to their defaults.
    """
    st.session_state.quiz_questions = []
    st.session_state.file_context_chunks = []
    st.session_state.generated_questions_bank = []
    st.session_state.user_score = 0 # Legacy score, clear it
    st.session_state.questions_answered = 0 # Legacy count, clear it
    
    # Clear the file uploader's internal state
    st.session_state.file_uploader_key = str(st.session_state.get('file_uploader_key', 0) + 1)
    
    st.success(get_lang("reset_success"))
    # (Implicit rerun)

# --- Function 4: Handle File Uploader Change (FIX for 'X' button) ---
def handle_file_change():
    """
    Called `on_change` of the file_uploader.
    If the file is cleared (X button), it resets the file context.
    """
    current_key = f"file_uploader_{st.session_state.file_uploader_key}"
    if st.session_state.get(current_key) is None:
        st.session_state.file_context_chunks = []

# ======================================================================================
# PART 6: SIDEBAR UI
# ======================================================================================

with st.sidebar:
    st.title(get_lang("control_panel"))
    st.write(f"{get_lang('welcome')}, Lu Nhat Truong!")
    
    st.divider()
    
    # --- Language Selector (NEW) ---
    st.session_state.language = st.selectbox(
        get_lang("lang_select"),
        options=["Tiếng Việt", "English"],
        key="lang_selector"
    )
    
    st.divider()
    
    # --- Score Calculation (NEW: Dynamic) ---
    st.header(get_lang("your_score"))
    
    total_answered = 0
    total_correct = 0
    for q in st.session_state.quiz_questions:
        if q["user_answer_index"] is not None:
            total_answered += 1
            if q["user_answer_index"] == q["q_data"]["correct_answer_index"]:
                total_correct += 1
                
    col1, col2 = st.columns(2)
    col1.metric(label=get_lang("total_score"), value=total_correct)
    col2.metric(label=get_lang("answered"), value=total_answered)
    
    # --- Reset Button (FIXED) ---
    st.button(get_lang("reset_button"), on_click=reset_app_state)

    st.divider()
    
    # --- Save Function (NEW: TXT Format) ---
    st.header(get_lang("save_header"))
    bank = st.session_state.generated_questions_bank
    st.write(f"{len(bank)} {get_lang('save_count')}")
    
    if bank:
        try:
            # Create the TXT content
            txt_output = ""
            for i, q_state in enumerate(bank):
                q_data = q_state["q_data"]
                txt_output += f"--- QUESTION {i+1} ---\n"
                txt_output += f"Question: {q_data['question']}\n"
                options = q_data['options']
                correct_idx = q_data['correct_answer_index']
                
                txt_output += f"  A: {options[0]}\n"
                txt_output += f"  B: {options[1]}\n"
                txt_output += f"  C: {options[2]}\n"
                txt_output += f"  D: {options[3]}\n"
                
                correct_letter = ['A', 'B', 'C', 'D'][correct_idx]
                txt_output += f"CORRECT ANSWER: ({correct_letter})\n"
                txt_output += f"Explanation: {q_data['explanation']}\n\n"

            st.download_button(
                label=get_lang("save_button"),
                data=txt_output,
                file_name="cau_hoi_da_luu.txt",
                mime="text/plain"
            )
            
        except Exception as e:
            st.error(f"{get_lang('save_error')}: {e}")
    else:
        st.caption(get_lang("save_no_q"))


# ======================================================================================
# PART 7: MAIN PAGE UI (TABS)
# ======================================================================================

st.title(get_lang("main_title"))

# --- Use TABS for different modes ---
tab_topic, tab_file = st.tabs([
    get_lang("tab_topic"), 
    get_lang("tab_file")
])

# --- Tab 1: Review by Topic ---
with tab_topic:
    st.header(get_lang("topic_header"))
    st.write(get_lang("topic_desc"))
    
    topic_input = st.text_input(get_lang("topic_input"), key="topic_input_main")
    
    st.button(
        get_lang("topic_button"), 
        key="btn_topic",
        on_click=generate_new_quiz, # Calls the function
        args=("topic", topic_input, None) # Passes arguments to the function
    )

# --- Tab 2: Review from Document (FIXED) ---
with tab_file:
    st.header(get_lang("file_header"))
    st.write(get_lang("file_desc"))
    
    # This key reset is magic to fix the "X" button not working
    if 'file_uploader_key' not in st.session_state:
        st.session_state.file_uploader_key = 0
        
    uploaded_file = st.file_uploader(
        get_lang("file_uploader"), 
        type=["txt", "pdf", "docx"],
        key=f"file_uploader_{st.session_state.file_uploader_key}", # Dynamic key
        on_change=handle_file_change # FIX: Call this when file is changed/cleared
    )
    
    # 1. Process the file if it's new
    if uploaded_file and not st.session_state.file_context_chunks:
        with st.spinner(f"{get_lang('file_processing')} '{uploaded_file.name}'..."):
            full_text = process_uploaded_file(uploaded_file)
            if full_text:
                st.session_state.file_context_chunks = get_text_chunks(full_text)
                st.success(get_lang("file_processed_desc").format(
                    char_count=len(full_text),
                    chunk_count=len(st.session_state.file_context_chunks)
                ))
            else:
                st.error(get_lang("file_read_error"))

    # 2. If file is processed and ready, show options
    if st.session_state.file_context_chunks:
        st.info(get_lang("file_ready"))
        
        context_chunks = st.session_state.file_context_chunks
        selected_chunk_index = 0
        
        if len(context_chunks) > 1:
            selected_chunk_index = st.selectbox(
                get_lang("file_chunk_select").format(chunk_count=len(context_chunks)),
                options=range(len(context_chunks)),
                format_func=lambda x: get_lang("file_chunk_format").format(i_plus_1=x+1, chunk_count=len(context_chunks))
            )
        
        selected_chunk = context_chunks[selected_chunk_index]
        st.button(
            get_lang("file_button"), 
            key="btn_file",
            on_click=generate_new_quiz, # Calls the same function
            args=("context", None, selected_chunk) # Passes different arguments
        )

# ======================================================================================
# PART 8: QUIZ DISPLAY AREA (THE "DON'T DISAPPEAR" FIX)
# ======================================================================================

st.divider() 

# This is the main quiz area. We loop through the list of questions.
if st.session_state.quiz_questions:
    
    for i, q_state in enumerate(st.session_state.quiz_questions):
        q_data = q_state["q_data"]
        
        with st.container(border=True):
            st.subheader(get_lang("question_header").format(i_plus_1=i+1))
            st.markdown(f"**{q_data['question']}**") # Bold question
            st.write("") # Spacer
            
            col1, col2 = st.columns(2)
            options = q_data['options']
            
            # Check if this question has been answered
            is_answered = (q_state["user_answer_index"] is not None)
            
            # Create the 4 buttons
            button_keys = [f"q{i}_A", f"q{i}_B", f"q{i}_C", f"q{i}_D"]
            button_cols = [col1, col2, col1, col2]
            
            for j in range(4): # Loop 0, 1, 2, 3
                button_cols[j].button(
                    f"**{['A', 'B', 'C', 'D'][j]}:** {options[j]}",
                    key=button_keys[j],
                    use_container_width=True,
                    disabled=is_answered, # CRITICAL: Disable button if answered
                    on_click=handle_answer, # Call the handler
                    args=(i, j) # Pass (question_index, chosen_index)
                )

            # --- Feedback Area (NEW) ---
            # If this question's feedback should be visible
            if q_state["feedback_visible"]:
                user_idx = q_state["user_answer_index"]
                correct_idx = q_data["correct_answer_index"]
                
                if user_idx == correct_idx:
                    st.success(f"**{get_lang('feedback_correct')}**")
                else:
                    st.error(f"**{get_lang('feedback_incorrect')}** {['A', 'B', 'C', 'D'][correct_idx]}: {options[correct_idx]}")
                
                # Show detailed explanation
                with st.expander(get_lang("feedback_explanation")):
                    st.markdown(q_state["ai_explanation"])

        st.write("") # Spacer between questions

# Case where the app just started
elif not st.session_state.quiz_questions:
    st.info(get_lang("welcome_info"))

