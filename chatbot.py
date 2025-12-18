# -*- coding: utf-8 -*-
import streamlit as st
import google.generativeai as genai
import json
import re
import io
import time
import PyPDF2
import docx

# ======================================================================================
# 1. CẤU HÌNH GIAO DIỆN & CSS
# ======================================================================================
st.set_page_config(page_title="Hệ thống Ôn tập Thông minh", page_icon="🎓", layout="wide")

js_scroll_to_latest = """
<script>
    var element = window.parent.document.getElementById("latest_quiz_batch");
    if (element) {
        element.scrollIntoView({behavior: "smooth", block: "start"});
    }
</script>
"""

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    [data-testid="stStatusWidget"] {display:none;}
    div[data-testid="stDecoration"] {visibility: hidden; height: 0px;}
    html, body, [class*="css"] {font-family: 'Segoe UI', sans-serif;}
    [data-testid="stSidebar"] {background-color: #f8f9fa; border-right: 1px solid #e0e0e0; padding-top: 20px;}
    
    .stButton > button {
        border-radius: 6px; border: 1px solid #E0E0E0; background-color: #fff;
        color: #333; transition: all 0.2s ease;
    }
    .stButton > button:hover {border-color: #2E86C1; color: #2E86C1;}

    /* Style cho Dashboard kết quả */
    .result-card {
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Style cho khung giải thích - KHÔNG LÀM MỜ */
    .explanation-box {
        background-color: #e8f4f8;
        border-left: 5px solid #2E86C1;
        padding: 15px;
        margin-top: 10px;
        border-radius: 5px;
        color: #2c3e50;
        font-size: 1rem; /* Cỡ chữ chuẩn */
        line-height: 1.6;
    }

    .scroll-to-top {
        position: fixed; bottom: 20px; right: 20px; 
        background-color: #2E86C1; color: white !important;
        width: 40px; height: 40px; border-radius: 50%; 
        text-align: center; line-height: 40px; font-size: 20px; 
        cursor: pointer; z-index: 99999; text-decoration: none;
    }
</style>
<div id="top_of_page"></div>
<a href="#top_of_page" class="scroll-to-top" title="Lên đầu trang">⬆</a>
""", unsafe_allow_html=True)

# ======================================================================================
# 2. CẤU HÌNH API
# ======================================================================================
API_KEY = "AIzaSyDDmwi4eDrp0fJzl-wy64lJEz5TJWIGGiQ"  # <--- DÁN API KEY CỦA BẠN VÀO ĐÂY

try:
    genai.configure(api_key=API_KEY)
except Exception as e:
    st.error(f"Lỗi API Key: {e}")
    st.stop()

def get_gemini_response(prompt):
    model = genai.GenerativeModel('models/gemini-flash-latest')
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        if "429" in str(e):
            time.sleep(2)
            try: return model.generate_content(prompt).text
            except: pass
        st.error(f"Lỗi kết nối AI: {e}")
        return None

def parse_json_response(response_text):
    if not response_text: return None
    # Làm sạch Markdown code block
    cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
    try:
        start_idx = cleaned_text.find('[')
        end_idx = cleaned_text.rfind(']') + 1
        if start_idx != -1 and end_idx > start_idx:
            json_str = cleaned_text[start_idx:end_idx]
            return json.loads(json_str)
        else: return None
    except json.JSONDecodeError:
        try:
            json_str = re.sub(r',\s*]', ']', json_str)
            return json.loads(json_str)
        except: pass
        return None

def clean_option_text(text):
    cleaned = re.sub(r'^\s*[a-zA-Z0-9]+[\.\)\:\-]\s*', '', text)
    return cleaned.strip()

# ======================================================================================
# 3. XỬ LÝ FILE
# ======================================================================================
def read_file_content(uploaded_file):
    if not uploaded_file: return None
    try:
        if uploaded_file.type == "text/plain":
            return io.StringIO(uploaded_file.getvalue().decode("utf-8")).read()
        elif uploaded_file.type == "application/pdf":
            reader = PyPDF2.PdfReader(uploaded_file)
            return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
        elif "wordprocessingml" in uploaded_file.type:
            doc = docx.Document(uploaded_file)
            return "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        st.error(f"Lỗi đọc file: {e}")
    return None

def split_text(text, limit=8000):
    return [text[i:i+limit] for i in range(0, len(text), limit)] if text else []

# ======================================================================================
# 4. QUẢN LÝ TRẠNG THÁI
# ======================================================================================
if 'quiz_batches' not in st.session_state: st.session_state.quiz_batches = []
if 'file_chunks' not in st.session_state: st.session_state.file_chunks = []
if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
if 'lang' not in st.session_state: st.session_state.lang = "Tiếng Việt"
if 'current_topic' not in st.session_state: st.session_state.current_topic = ""
if 'scroll_trigger' not in st.session_state: st.session_state.scroll_trigger = False
if 'total_generated' not in st.session_state: st.session_state.total_generated = 0
if 'active_tab' not in st.session_state: st.session_state.active_tab = 0 
if 'mode' not in st.session_state: st.session_state.mode = "Luyện tập"

# ======================================================================================
# 5. LOGIC TẠO CÂU HỎI
# ======================================================================================
def generate_quiz(mode="topic", input_data=None, is_continue=False, source_name="", num_questions=10, quiz_type="practice"):
    
    # --- PHẦN 1: XỬ LÝ INPUT ---
    if mode == "topic" and input_data is None:
        input_data = st.session_state.get("topic_input_main", "")

    if is_continue:
        input_data = st.session_state.current_topic
    
    if not input_data:
        st.warning("Vui lòng nhập chủ đề hoặc chọn file!")
        return

    keep_history = st.session_state.get('keep_history_check', False)
    if not is_continue:
        if quiz_type == "exam":
            st.session_state.quiz_batches = []
            st.session_state.total_generated = 0
        elif not keep_history:
            st.session_state.quiz_batches = []
            st.session_state.total_generated = 0
            
        st.session_state.current_topic = input_data

    display_topic = source_name if source_name else input_data
    if mode == "context": st.session_state.current_topic = display_topic
    lang = st.session_state.lang
    
    prompt = ""
    
    # --- NHÁNH A: LUYỆN TẬP ---
    if quiz_type == "practice":
        recent_qs = []
        for batch in st.session_state.quiz_batches:
            for item in batch['data']:
                if 'data' in item and 'question' in item['data']:
                    recent_qs.append(item['data']['question'])
        avoid_str = json.dumps(recent_qs[-20:]) if recent_qs else ""

        prompt = f"""
        Act as a strict exam creator.
        Topic/Content: '{input_data}' ({mode}).
        Create 10 multiple-choice questions in {lang}.
        Avoid: {avoid_str}

        RULES:
        1. Output JSON LIST of 10 objects. NO Markdown block.
        2. EXPLANATION: Explain WHY correct answer is right and WHY others are wrong.
        3. FORMAT:
        [
          {{
            "question": "...",
            "options": ["A", "B", "C", "D"],
            "correct_index": 0,
            "explanation": "..."
          }}
        ]
        """

    # --- NHÁNH B: THI THỬ (NÂNG CẤP PROMPT) ---
    elif quiz_type == "exam":
        prompt = f"""
        Act as an Intelligent Exam Processor. 
        Target: Create exactly {num_questions} multiple-choice questions in {lang}.
        SOURCE MATERIAL:
        '''{input_data}'''

        INSTRUCTIONS:
        1. Return ONLY the raw JSON list. NO Markdown block.
        2. DATA QUALITY CHECK (Important):
           - Do NOT generate placeholder text like "000" or "XYZ".
           - If a specific detail (like exact number) is missing in text, skip that question or find another angle.
           - Options must be distinct and meaningful.
        
        3. EXPLANATION REQUIREMENT:
           - Provide a DETAILED, CLEAR explanation.
           - Explain the logic step-by-step so a beginner can understand.
           - No word limit for explanation.

        4. MODE DETECTION:
           - CASE A (File contains Questions): EXTRACT them. If answers missing, SOLVE them.
           - CASE B (File is Theory): GENERATE new questions.
           - CASE C (Mixed): Extract first, then GENERATE more.
        
        OUTPUT FORMAT (Strict JSON):
        [
          {{
            "question": "Question text?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_index": 0, 
            "explanation": "Detailed explanation here..." 
          }}
        ]
        """

    # --- GỌI AI ---
    with st.spinner("Đang xử lý... Vui lòng đợi."):
        res = get_gemini_response(prompt)
        data = parse_json_response(res)
    
    if data:
        if len(data) == 0:
            st.error("AI từ chối tạo câu hỏi (Nội dung không hợp lệ).")
            return

        batch_data = []
        for item in data:
            item['topic_name'] = str(display_topic)
            cleaned_options = [clean_option_text(opt) for opt in item['options']]
            item['options'] = cleaned_options
            batch_data.append({"data": item, "user_ans": None, "show_res": False})

        st.session_state.quiz_batches.append({
            "id": len(st.session_state.quiz_batches) + 1,
            "data": batch_data,
            "topic": display_topic,
            "type": quiz_type, 
            "is_submitted": False 
        })
        
        st.session_state.total_generated += len(data)
        st.session_state.scroll_trigger = True 
    else:
        st.error("Lỗi: AI trả về định dạng không khớp. Hãy thử lại!")

def handle_choice(batch_idx, q_idx, opt_idx):
    st.session_state.quiz_batches[batch_idx]['data'][q_idx]['user_ans'] = opt_idx
    st.session_state.quiz_batches[batch_idx]['data'][q_idx]['show_res'] = True

def submit_exam(batch_idx, form_data):
    batch = st.session_state.quiz_batches[batch_idx]
    for q_idx, item in enumerate(batch['data']):
        key = f"q{q_idx}"
        if key in form_data:
            selected_text = form_data[key]
            if selected_text:
                try:
                    opt_list = [f"{['A','B','C','D'][i]}. {opt}" for i, opt in enumerate(item['data']['options'])]
                    idx = opt_list.index(selected_text)
                    item['user_ans'] = idx
                except:
                    item['user_ans'] = None
        item['show_res'] = True
    
    st.session_state.quiz_batches[batch_idx]['is_submitted'] = True
    # Lưu timestamp để trick Streamlit render lại
    st.session_state['last_submit_time'] = time.time() 

def delete_all_questions():
    st.session_state.quiz_batches = []
    st.session_state.total_generated = 0
    st.session_state.current_topic = ""
    st.success("Đã xóa toàn bộ câu hỏi!")

def reset_system():
    delete_all_questions()
    st.session_state.file_chunks = []
    st.session_state.uploader_key += 1
    st.success("Đã làm mới hệ thống!")

# ======================================================================================
# 6. GIAO DIỆN CHÍNH
# ======================================================================================

if st.session_state.scroll_trigger:
    st.components.v1.html(js_scroll_to_latest, height=0)
    st.session_state.scroll_trigger = False

with st.sidebar:
    st.markdown("**SV:** Lữ Nhật Trường <br> **MSSV:** 2252010042", unsafe_allow_html=True)
    st.divider()
    
    st.header("⚙️ Cấu hình")
    mode_select = st.radio("Chế độ ôn tập:", ["Luyện tập", "Thi thử"], 
                          help="Luyện tập: Biết đúng sai ngay.\nThi thử: Làm hết mới biết điểm.")
    st.session_state.mode = mode_select
    st.session_state.lang = st.selectbox("Ngôn ngữ", ["Tiếng Việt", "English"])
    
    st.divider()
    
    total_q = st.session_state.total_generated
    score = 0
    done = 0
    for batch in st.session_state.quiz_batches:
        for q in batch['data']:
            if q['user_ans'] is not None:
                done += 1
                if q['user_ans'] == q['data']['correct_index']: score += 1
    
    c1, c2 = st.columns(2)
    c1.metric("Điểm", score)
    c2.metric("Đã làm", f"{done}/{total_q}")
    
    col_total, col_del = st.columns([3, 1])
    col_total.info(f"Tổng câu: {total_q}")
    col_del.button("🗑️", on_click=delete_all_questions, help="Xóa tất cả", key="btn_del_all") 

    if st.session_state.mode == "Luyện tập":
        st.checkbox("Lưu lịch sử (Cộng dồn)", key="keep_history_check")

    st.divider()
    st.button("Làm mới hệ thống", on_click=reset_system, use_container_width=True, key="btn_reset_sys")

st.title(f"🤖 {st.session_state.mode} Trắc nghiệm")

tab1, tab2 = st.tabs(["📝 Theo Chủ đề", "📁 Từ Tài liệu"])

with tab1:
    if st.session_state.mode == "Thi thử":
        st.info("💡 Nên dùng 'Từ Tài liệu' để đề thi chính xác nhất.")
    
    c1, c2 = st.columns([4, 1])
    topic_in = c1.text_input("Nhập chủ đề", key="topic_input_main", label_visibility="collapsed", placeholder="Nhập chủ đề...")
    btn_label = "Tạo đề" if st.session_state.mode == "Luyện tập" else "Bắt đầu thi"
    
    if c2.button(btn_label, key="btn_create_topic", use_container_width=True):
        if topic_in:
            q_type = "practice" if st.session_state.mode == "Luyện tập" else "exam"
            generate_quiz("topic", topic_in, quiz_type=q_type)

with tab2:
    f = st.file_uploader("Chọn file (PDF/Word/TXT)", type=["pdf","docx","txt"], 
                         key=f"up_{st.session_state.uploader_key}", 
                         on_change=lambda: st.session_state.update(file_chunks=[]))
    
    if f:
        if not st.session_state.file_chunks:
            with st.spinner("Đang đọc file..."):
                text = read_file_content(f)
                if text:
                    st.session_state.file_chunks = split_text(text)
                    st.success(f"Đã đọc xong file: {f.name}")
                else: st.error("Lỗi đọc file.")

    if st.session_state.file_chunks:
        chs = st.session_state.file_chunks
        chunk_options = [f"Phần {i+1} (Ký tự {i*8000}-{(i+1)*8000})" for i in range(len(chs))]
        idx = st.selectbox("Chọn phạm vi nội dung", range(len(chs)), format_func=lambda x: chunk_options[x])
        
        num_q = 10
        if st.session_state.mode == "Thi thử":
            num_q = st.slider("Số lượng câu hỏi:", 5, 30, 10)

        if st.button(f"{btn_label} từ file", key="btn_create_file"):
             file_topic_name = f"Tài liệu: {f.name}"
             q_type = "practice" if st.session_state.mode == "Luyện tập" else "exam"
             generate_quiz("context", chs[idx], False, file_topic_name, num_questions=num_q, quiz_type=q_type)

st.divider()

if st.session_state.quiz_batches:
    total_batches = len(st.session_state.quiz_batches)
    g_idx = 0 
    
    for b_idx, batch in enumerate(st.session_state.quiz_batches):
        batch_type = batch.get('type', 'practice')
        batch_len = len(batch['data'])
        start = g_idx + 1
        end = g_idx + batch_len
        is_latest = (b_idx == total_batches - 1)
        
        anchor_html = '<div id="latest_quiz_batch"></div>' if is_latest else ""
        st.markdown(anchor_html, unsafe_allow_html=True)
        
        # --- GIAO DIỆN 1: LUYỆN TẬP ---
        if batch_type == "practice":
            with st.expander(f"📌 [Luyện tập] Câu {start} - {end} | {batch.get('topic','TxT')}", expanded=is_latest):
                for q_idx, item in enumerate(batch['data']):
                    q = item['data']
                    r_num = g_idx + 1
                    
                    st.markdown(f"**Câu {r_num}:** {q['question']}")
                    
                    cols = st.columns(2)
                    for j, opt in enumerate(q['options']):
                        dis = item['user_ans'] is not None
                        cols[j%2].button(f"{['A','B','C','D'][j]}. {opt}", key=f"b{b_idx}q{q_idx}o{j}", 
                                         disabled=dis, use_container_width=True,
                                         on_click=handle_choice, args=(b_idx, q_idx, j))
                    
                    if item['show_res']:
                        u, c = item['user_ans'], q['correct_index']
                        if u == c: st.success("✅ Chính xác!")
                        else: st.error(f"❌ Sai rồi. Đáp án đúng: {['A','B','C','D'][c]}")
                        st.info(f"💡 Giải thích: {q['explanation']}")
                    st.markdown("---")
                    g_idx += 1
                
                if is_latest:
                     if st.button(f"⏩ Tạo tiếp câu hỏi luyện tập", key="btn_cont_prac"):
                         generate_quiz("topic", None, True, quiz_type="practice")

        # --- GIAO DIỆN 2: THI THỬ (ĐÃ SỬA LỖI SUBMIT BUTTON) ---
        elif batch_type == "exam":
            st.subheader(f"📝 BÀI THI: {batch.get('topic','Exam')}")
            
            # 1. Tính toán điểm số (Chỉ hiện khi đã nộp bài)
            is_sub = batch.get('is_submitted', False)
            if is_sub:
                correct_count = sum(1 for q in batch['data'] if q['user_ans'] == q['data']['correct_index'])
                total_count = len(batch['data'])
                score_10 = round((correct_count / total_count) * 10, 2)
                
                # Logic màu sắc
                color_code = "#e74c3c" # Đỏ (Mặc định thấp)
                result_msg = "Cần cố gắng nhiều hơn!"
                if score_10 >= 8.0: 
                    color_code = "#27ae60" # Xanh
                    result_msg = "Xuất sắc! Bạn nắm bài rất tốt."
                elif score_10 >= 5.0: 
                    color_code = "#f39c12" # Cam
                    result_msg = "Đạt yêu cầu, nhưng cần ôn thêm."

                # HTML Dashboard đẹp
                st.markdown(f"""
                <div class="result-card" style="background-color: {color_code}20; border: 2px solid {color_code};">
                    <h2 style="color: {color_code}; margin:0;">KẾT QUẢ: {score_10} / 10</h2>
                    <p style="font-size: 1.2em; margin: 5px 0;">Số câu đúng: <b>{correct_count}/{total_count}</b></p>
                    <p style="font-style: italic;">"{result_msg}"</p>
                </div>
                """, unsafe_allow_html=True)

            # 2. Form làm bài
            with st.form(key=f"exam_form_{b_idx}"):
                user_choices = {}
                for q_idx, item in enumerate(batch['data']):
                    q = item['data']
                    r_num = g_idx + 1
                    st.markdown(f"**Câu {r_num}:** {q['question']}")
                    opts = [f"{['A','B','C','D'][i]}. {opt}" for i, opt in enumerate(q['options'])]
                    
                    choice = st.radio(
                        "Chọn đáp án:", opts, index=None, key=f"rad_{b_idx}_{q_idx}",
                        disabled=is_sub, # Khóa sau khi nộp
                        label_visibility="collapsed"
                    )
                    user_choices[f"q{q_idx}"] = choice
                    
                    # Logic hiển thị kết quả (Chỉ hiện khi đã nộp)
                    if is_sub:
                        u_idx = item['user_ans']
                        c_idx = q['correct_index']
                        
                        if u_idx == c_idx: 
                            st.success(f"✅ Bạn chọn đúng!")
                        else: 
                            st.error(f"❌ Sai. Đáp án đúng là: {['A','B','C','D'][c_idx]}")
                        
                        # HIỂN THỊ GIẢI THÍCH (Không làm mờ)
                        st.markdown(f"""
                        <div class="explanation-box">
                            <b>📖 Giải thích chi tiết:</b><br>
                            {q['explanation']}
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.markdown("---")
                    g_idx += 1
                
                # --- PHẦN SỬA LỖI Ở ĐÂY ---
                if not is_sub:
                    # Nếu chưa nộp thì hiện nút để bấm
                    submitted = st.form_submit_button("NỘP BÀI THI", type="primary")
                    if submitted:
                        submit_exam(b_idx, user_choices)
                        st.rerun()
                else:
                    # Nếu đã nộp rồi, vẫn phải render nút (nhưng disable nó) 
                    # để thỏa mãn yêu cầu bắt buộc của st.form
                    st.form_submit_button("Đã nộp bài", disabled=True)

elif not st.session_state.quiz_batches:
    st.info("👋 Chào mừng! Hãy chọn chế độ bên trái và bắt đầu.")


