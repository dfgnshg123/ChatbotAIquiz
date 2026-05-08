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
st.set_page_config(page_title="Hệ thống Ôn tập Trắc nghiệm", page_icon="🎓", layout="wide")

# JavaScript để tự động cuộn (Auto-scroll)
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
    /* Ẩn các thành phần mặc định thừa */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    [data-testid="stStatusWidget"] {display:none;}
    
    /* Font chữ toàn hệ thống */
    html, body, [class*="css"] {font-family: 'Segoe UI', sans-serif;font-size: 14px;}
    
    /* Tùy chỉnh Sidebar cho gọn */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa; 
        border-right: 1px solid #e0e0e0; 
        padding-top: 10px;
    }
    [data-testid="stSidebar"] .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
    /* Style cho Button */
    .stButton > button {
        border-radius: 6px; 
        border: 1px solid #E0E0E0; 
        background-color: #fff;
        color: #333; 
        transition: all 0.2s ease;
        width: 100%;
        margin-bottom: 5px;
    }
    .stButton > button:hover {
        border-color: #2E86C1; 
        color: #2E86C1;
    }

    /* Dashboard kết quả thi thử */
    .result-card {
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 20px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Khung giải thích */
    .explanation-box {
        background-color: #f1f9ff;
        border-left: 4px solid #2E86C1;
        padding: 10px 15px;
        margin-top: 8px;
        border-radius: 4px;
        color: #2c3e50;
        font-size: 0.95rem;
        line-height: 1.5;
    }
    
    /* Nút về đầu trang */
    .scroll-to-top {
        position: fixed; bottom: 20px; right: 20px; 
        background-color: #2E86C1; color: white !important;
        width: 35px; height: 35px; border-radius: 50%; 
        text-align: center; line-height: 35px; font-size: 18px; 
        cursor: pointer; z-index: 99999; text-decoration: none;
    }

    /* Style hiển thị đúng sai cho thi thử */
    .exam-correct {
        color: #155724;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        padding: 5px 10px;
        border-radius: 4px;
        margin-top: 5px;
        font-weight: bold;
    }
    .exam-wrong {
        color: #721c24;
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        padding: 5px 10px;
        border-radius: 4px;
        margin-top: 5px;
        font-weight: bold;
    }
    
    /* Divider nhỏ trong sidebar */
    .sidebar-divider {
        margin-top: 10px;
        margin-bottom: 10px;
        border-top: 1px solid #e0e0e0;
    }
</style>
<div id="top_of_page"></div>
<a href="#top_of_page" class="scroll-to-top" title="Lên đầu trang">⬆</a>
""", unsafe_allow_html=True)

# ======================================================================================
# 2. CẤU HÌNH API (NHẬP 1 LẦN DUY NHẤT TẠI ĐÂY)
# ======================================================================================

API_KEY = "AIzaSyC3fnqXzSeECPnm5lsIfcIcTBN_Zhrml98"

try:
    genai.configure(api_key=API_KEY)
except Exception as e:
    st.error(f"Lỗi cấu hình API: {e}")

# Hàm gọi Gemini đã được nâng cấp với cơ chế tự động tìm Model miễn phí
def get_gemini_response(prompt):
    models_to_try = [
        'gemini-1.5-flash', 
        'gemini-1.5-flash-latest', 
        'gemini-pro'
    ]
    
    last_error = ""
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            last_error = str(e)
            if "404" in last_error or "not found" in last_error.lower():
                continue 
            elif "429" in last_error or "Quota exceeded" in last_error:
                st.error("⚠️ API của bạn đã hết lượt sử dụng miễn phí hôm nay. Vui lòng thử lại sau.")
                return None
            elif "400" in last_error:
                st.error("⚠️ Yêu cầu không hợp lệ (Lỗi 400).")
                return None

    st.error(f"⚠️ Lỗi kết nối AI (Đã thử hết các model). Lỗi: {last_error}")
    return None

def parse_json_response(response_text):
    if not response_text: return None
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
            # Cố gắng sửa lỗi dấu phẩy thừa
            json_str = re.sub(r',\s*]', ']', cleaned_text)
            return json.loads(json_str)
        except: pass
        return None

def clean_option_text(text):
    cleaned = re.sub(r'^\s*[a-zA-Z0-9]+[\.\)\:\-]\s*', '', text)
    return cleaned.strip()

def create_full_txt_export():
    """Hàm tạo file txt tổng hợp toàn bộ lịch sử để tải về từ Sidebar"""
    if not st.session_state.quiz_batches:
        return ""
    
    output = []
    output.append("=== DANH SÁCH CÂU HỎI ĐÃ TẠO ===")
    
    for b_idx, batch in enumerate(st.session_state.quiz_batches):
        prefix = "Thi thử: " if batch['type'] == 'exam' else ""
        output.append(f"\n>> {prefix}{batch['topic']}")
        
        for i, item in enumerate(batch['data']):
            q = item['data']
            output.append(f"Câu {i + 1}: {q['question']}")
            labels = ['A', 'B', 'C', 'D']
            for j, opt in enumerate(q['options']):
                output.append(f"{labels[j]}. {opt}")
            
            output.append("--- PHÂN TÍCH ---")
            correct_label = labels[q['correct_index']]
            output.append(f"ĐÁP ÁN ĐÚNG ({correct_label}): {q['explanation']}")
            output.append("-" * 20)
            
    return "\n".join(output)

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
            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted: text += extracted + "\n"
            return text
        elif "wordprocessingml" in uploaded_file.type:
            doc = docx.Document(uploaded_file)
            return "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        st.error(f"Lỗi đọc file: {e}")
    return None

def split_text_smart(text, max_chunk_size=4000):
    if not text: return []
    paragraphs = text.split('\n')
    chunks = []
    current_chunk = ""
    for para in paragraphs:
        if len(current_chunk) + len(para) < max_chunk_size:
            current_chunk += para + "\n"
        else:
            if current_chunk.strip(): chunks.append(current_chunk)
            current_chunk = para + "\n"
    if current_chunk.strip(): chunks.append(current_chunk)
    return chunks

# ======================================================================================
# 4. QUẢN LÝ SESSION STATE
# ======================================================================================
if 'quiz_batches' not in st.session_state: st.session_state.quiz_batches = []
if 'file_chunks' not in st.session_state: st.session_state.file_chunks = []
if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
if 'current_topic' not in st.session_state: st.session_state.current_topic = ""
if 'scroll_trigger' not in st.session_state: st.session_state.scroll_trigger = False
if 'total_generated' not in st.session_state: st.session_state.total_generated = 0
if 'mode' not in st.session_state: st.session_state.mode = "Luyện tập"
# Thêm biến đếm tổng quát cho Luyện tập để hiển thị cộng dồn
if 'practice_counter' not in st.session_state: st.session_state.practice_counter = 0

# ======================================================================================
# 5. LOGIC TẠO CÂU HỎI
# ======================================================================================
def generate_quiz(mode="topic", input_data=None, is_continue=False, source_name="", num_questions=10, quiz_type="practice"):
    
    if mode == "topic" and input_data is None:
        input_data = st.session_state.get("topic_input_main", "")

    if is_continue:
        input_data = st.session_state.current_topic
    
    if not input_data:
        st.warning("Vui lòng nhập chủ đề hoặc chọn file!")
        return

    # Logic Reset/Lưu lịch sử: GIỮ NGUYÊN DANH SÁCH BATCHES khi chuyển chế độ
    # Chỉ reset practice counter nếu cần thiết, không xóa quiz_batches trừ khi bấm nút Xóa
    
    st.session_state.current_topic = input_data

    display_topic = source_name if source_name else input_data
    # Cắt ngắn topic hiển thị nếu quá dài
    if len(display_topic) > 40: display_topic = display_topic[:40] + "..."
    
    # Định dạng tên hiển thị cho Thi thử
    if quiz_type == "exam" and not display_topic.startswith("Thi thử:"):
        pass # Sẽ thêm prefix lúc hiển thị hoặc export

    prompt = ""
    role_instruction = """
    Bạn là Trợ lý Giáo dục AI (AI Exam Maker).
    1. Nếu chủ đề spam/vô nghĩa -> Trả về [].
    2. Phải tự giải đề (Fact-Check) để đảm bảo đáp án ĐÚNG 100%.
    3. Trả về JSON Array thuần túy.
    """

    if quiz_type == "practice":
        # Lấy lịch sử để tránh trùng lặp
        recent_qs = []
        for batch in st.session_state.quiz_batches:
            if batch['type'] == 'practice': # Chỉ check trùng với câu luyện tập
                for item in batch['data']:
                    if 'data' in item and 'question' in item['data']:
                        recent_qs.append(item['data']['question'])
        avoid_str = json.dumps(recent_qs[-20:]) if recent_qs else ""

        prompt = f"""
        {role_instruction}
        CHỦ ĐỀ: '{input_data}' ({mode}).
        YÊU CẦU: Tạo 10 câu hỏi trắc nghiệm Tiếng Việt.
        TRÁNH CÁC CÂU: {avoid_str}
        JSON FORMAT: [{{ "question": "...", "options": ["A", "B", "C", "D"], "correct_index": 0, "explanation": "..." }}]
        """

    elif quiz_type == "exam":
        prompt = f"""
        {role_instruction}
        NGUỒN DỮ LIỆU: '''{input_data}'''
        YÊU CẦU: Tạo chính xác {num_questions} câu hỏi Tiếng Việt.
        JSON FORMAT: [{{ "question": "...", "options": ["A", "B", "C", "D"], "correct_index": 0, "explanation": "..." }}]
        """

    with st.spinner("🤖 AI đang tạo bộ đề..."):
        res = get_gemini_response(prompt)
        data = parse_json_response(res)
    
    if data:
        if len(data) == 0:
            st.error("Chủ đề không hợp lệ.")
            return

        batch_data = []
        for item in data:
            if 'options' not in item or 'correct_index' not in item: continue
            cleaned_options = [clean_option_text(opt) for opt in item['options']]
            item['options'] = cleaned_options
            batch_data.append({"data": item, "user_ans": None, "show_res": False})

        # Xác định phạm vi hiển thị cho Expander
        start_num = 0
        end_num = 0
        
        if quiz_type == "practice":
            start_num = st.session_state.practice_counter + 1
            st.session_state.practice_counter += len(batch_data)
            end_num = st.session_state.practice_counter
        else:
            # Thi thử không dùng counter cộng dồn
            start_num = 1
            end_num = len(batch_data)
        
        st.session_state.quiz_batches.append({
            "id": len(st.session_state.quiz_batches) + 1,
            "data": batch_data,
            "topic": display_topic,
            "type": quiz_type, 
            "is_submitted": False,
            "start_num": start_num, 
            "end_num": end_num,     
            "total_q": len(batch_data)
        })
        
        st.session_state.total_generated += len(batch_data)
        st.session_state.scroll_trigger = True 
    else:
        st.error("Lỗi dữ liệu AI.")

def handle_choice_practice(batch_idx, q_idx, opt_idx):
    st.session_state.quiz_batches[batch_idx]['data'][q_idx]['user_ans'] = opt_idx
    st.session_state.quiz_batches[batch_idx]['data'][q_idx]['show_res'] = True

def delete_all_questions():
    st.session_state.quiz_batches = []
    st.session_state.total_generated = 0
    st.session_state.practice_counter = 0
    st.session_state.current_topic = ""
    st.success("Đã xóa toàn bộ câu hỏi!")

def reset_metrics():
    # Chỉ reset thống kê làm bài (Đúng/Đã làm), giữ lại câu hỏi
    # Cần reset trạng thái làm bài của user
    for batch in st.session_state.quiz_batches:
        batch['is_submitted'] = False # Reset trạng thái nộp bài thi thử
        for item in batch['data']:
            item['user_ans'] = None
            item['show_res'] = False
    st.toast("Đã đặt lại thống kê làm bài!", icon="🔄")

def reset_system():
    st.session_state.clear()
    st.rerun()

# ======================================================================================
# 6. GIAO DIỆN CHÍNH
# ======================================================================================

if st.session_state.scroll_trigger:
    st.components.v1.html(js_scroll_to_latest, height=0)
    st.session_state.scroll_trigger = False

# --- SIDEBAR (SẮP XẾP THEO YÊU CẦU NGHIÊM NGẶT) ---
with st.sidebar:
    # 1. Thông tin sinh viên (Compact)
    st.markdown("""
    <div style="background-color: #e3f2fd; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
        <b>SV:</b> Lữ Nhật Trường<br>
        <b>MSSV:</b> 2252010042
    </div>
    """, unsafe_allow_html=True)
    
    # 2. Chế độ ôn tập
    st.markdown("**Chế độ ôn tập**")
    mode_select = st.radio("Chế độ", ["Luyện tập", "Thi thử"], label_visibility="collapsed")
    st.session_state.mode = mode_select
    
    # Ghi chú chế độ
    if st.session_state.mode == "Luyện tập":
        st.info("💡Luyện tập: Biết đúng sai ngay.")
    else:
        st.info("💡Thi thử: Làm hết mới biết điểm.")

    # 3. Thống kê (Correct/Done)
    correct_all = 0
    done_all = 0
    for batch in st.session_state.quiz_batches:
        for q in batch['data']:
            if q['user_ans'] is not None:
                done_all += 1
                if q['user_ans'] == q['data']['correct_index']: correct_all += 1
    
    c1, c2 = st.columns(2)
    c1.metric("Đúng", correct_all)
    c2.metric("Đã làm", done_all)
    
    # 4. Reset Button
    if st.button("Reset", help="Đặt lại kết quả làm bài về 0"):
        reset_metrics()
    
    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
    
    # 5. Số câu đã tạo + nút Xóa (cùng hàng)
    with st.container():
        col_left, col_right = st.columns([4, 1])

        with col_left:
            st.markdown(f"**Số câu đã tạo: {st.session_state.total_generated}**")

        with col_right:
            if st.button("🗑️", key="btn_del_1", help="Xóa hết câu hỏi trong số câu đã tạo"):
                delete_all_questions()

    # 6. Tải về (.txt)
    txt_data = create_full_txt_export()
    st.download_button("📥 Tải về (.txt)", txt_data, file_name="Bo_Cau_Hoi_On_Tap.txt", mime="text/plain")

    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
    
    # 7. Làm mới hệ thống
    if st.button("🔄 Làm mới hệ thống", type="primary"):
        reset_system()

# --- MAIN CONTENT ---
st.title(f"🤖 {st.session_state.mode} Trắc nghiệm")

tab1, tab2 = st.tabs(["📝 Theo Chủ đề", "📁 Từ Tài liệu"])

# Xử lý sự kiện Enter bằng on_change
def on_topic_submit():
    topic_in = st.session_state.topic_input_main
    if topic_in:
        q_type = "practice" if st.session_state.mode == "Luyện tập" else "exam"
        generate_quiz("topic", topic_in, quiz_type=q_type)

with tab1:
    c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
    # Sử dụng on_change để bắt sự kiện Enter
    topic_in = c1.text_input("Nhập chủ đề", key="topic_input_main", placeholder="Ví dụ: Lịch sử Việt Nam...", on_change=on_topic_submit)
    btn_label = "Tạo đề" if st.session_state.mode == "Luyện tập" else "Bắt đầu thi"
    
    if c2.button(btn_label, key="btn_topic", use_container_width=True):
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
                    st.session_state.file_chunks = split_text_smart(text)
                    st.success(f"Đã đọc file: {f.name}")
                else: st.error("Lỗi đọc file.")

    if st.session_state.file_chunks:
        chs = st.session_state.file_chunks
        chunk_options = [f"Phần {i+1} ({len(c)} ký tự)" for i, c in enumerate(chs)]
        idx = st.selectbox("Chọn phạm vi", range(len(chs)), format_func=lambda x: chunk_options[x])
        
        num_q = 10
        if st.session_state.mode == "Thi thử":
            num_q = st.slider("Số lượng câu hỏi:", 5, 30, 10)

        if st.button(f"{btn_label} từ file", key="btn_file"):
             file_topic_name = f"Phần {idx+1}: {f.name}"
             q_type = "practice" if st.session_state.mode == "Luyện tập" else "exam"
             generate_quiz("context", chs[idx], False, file_topic_name, num_questions=num_q, quiz_type=q_type)

st.divider()

# --- RENDER CÂU HỎI (HIỂN THỊ CHUNG CHO CẢ 2 CHẾ ĐỘ) ---
if st.session_state.quiz_batches:
    total_batches = len(st.session_state.quiz_batches)
    
    for b_idx, batch in enumerate(st.session_state.quiz_batches):
        batch_type = batch.get('type', 'practice')
        is_latest = (b_idx == total_batches - 1)
        
        # Neo scroll
        if is_latest: st.markdown('<div id="latest_quiz_batch"></div>', unsafe_allow_html=True)
        
        # === HIỂN THỊ BATCH DẠNG EXPANDER (CẢ 2 CHẾ ĐỘ) ===
        if batch_type == "practice":
            expander_title = f"{batch['topic']}: {batch['start_num']}-{batch['end_num']}"
        else: # exam
            expander_title = f"Thi thử: {batch['topic']} ({batch['total_q']} câu)"
            
        with st.expander(expander_title, expanded=is_latest):
            
            # --- LOGIC RENDER CHO LUYỆN TẬP ---
            if batch_type == "practice":
                for q_idx, item in enumerate(batch['data']):
                    q = item['data']
                    r_num = batch['start_num'] + q_idx
                    
                    st.markdown(f"**Câu {r_num}:** {q['question']}")
                    
                    cols = st.columns(2)
                    for j, opt in enumerate(q['options']):
                        dis = item['user_ans'] is not None
                        cols[j%2].button(
                            f"{['A','B','C','D'][j]}. {opt}", 
                            key=f"p_btn_{b_idx}_{q_idx}_{j}", 
                            disabled=dis, 
                            use_container_width=True,
                            on_click=handle_choice_practice, args=(b_idx, q_idx, j)
                        )
                    
                    # Hiện đáp án đã chọn và kết quả
                    if item['show_res']:
                        u, c = item['user_ans'], q['correct_index']
                        user_choice_text = q['options'][u] if u is not None else ""
                        st.write(f"👉 **Bạn chọn:** {['A','B','C','D'][u]}. {user_choice_text}")
                        
                        if u == c: 
                            st.success("✅ Chính xác!")
                        else: 
                            st.error(f"❌ Sai rồi. Đáp án đúng: {['A','B','C','D'][c]}")
                        st.markdown(f"<div class='explanation-box'><b>💡 Giải thích:</b> {q['explanation']}</div>", unsafe_allow_html=True)
                    
                    st.markdown("---")
                
                # Nút tạo tiếp chỉ hiện ở batch cuối cùng của Luyện tập
                if is_latest and st.button("⏩ Tạo tiếp 10 câu", key=f"more_{b_idx}"):
                    generate_quiz("topic", None, True, quiz_type="practice")

            # --- LOGIC RENDER CHO THI THỬ ---
            elif batch_type == "exam":
                is_sub = batch.get('is_submitted', False)
                
                # Dashboard Kết quả (Sau khi nộp)
                if is_sub:
                    correct_cnt = sum(1 for q in batch['data'] if q['user_ans'] == q['data']['correct_index'])
                    total_cnt = len(batch['data'])
                    score_10 = round((correct_cnt / total_cnt) * 10, 2)
                    
                    color = "#e74c3c"
                    if score_10 >= 8.0: color = "#27ae60"
                    elif score_10 >= 5.0: color = "#f39c12"

                    st.markdown(f"""
                    <div class="result-card" style="border: 2px solid {color}; background-color: {color}10;">
                        <h3 style="color: {color}; margin:0;">KẾT QUẢ: {score_10} / 10</h3>
                        <p>Số câu đúng: <b>{correct_cnt}/{total_cnt}</b></p>
                    </div>
                    """, unsafe_allow_html=True)

                with st.form(key=f"exam_form_{b_idx}"):
                    for q_idx, item in enumerate(batch['data']):
                        q = item['data']
                        r_num = q_idx + 1 # Reset về 1
                        
                        st.markdown(f"**Câu {r_num}:** {q['question']}")
                        
                        opts = [f"{['A','B','C','D'][i]}. {opt}" for i, opt in enumerate(q['options'])]
                        idx_select = item['user_ans'] if item['user_ans'] is not None else None
                        
                        st.radio(
                            "Lựa chọn:", opts, 
                            index=idx_select, 
                            key=f"rad_{b_idx}_{q_idx}",
                            disabled=is_sub,
                            label_visibility="collapsed"
                        )
                        
                        if is_sub:
                            c_idx = q['correct_index']
                            u_idx = item['user_ans']
                            
                            if u_idx is not None:
                                user_val = q['options'][u_idx]
                                st.write(f"👉 **Bạn chọn:** {['A','B','C','D'][u_idx]}. {user_val}")
                                
                                if u_idx == c_idx:
                                    st.markdown(f"<div class='exam-correct'>✅ Đúng!</div>", unsafe_allow_html=True)
                                else:
                                    st.markdown(f"<div class='exam-wrong'>❌ Sai. Đáp án đúng: {['A','B','C','D'][c_idx]}</div>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<div class='exam-wrong'>⚠️ Chưa chọn. Đáp án đúng: {['A','B','C','D'][c_idx]}</div>", unsafe_allow_html=True)
                                
                            st.markdown(f"<div class='explanation-box'><b>💡 Giải thích:</b> {q['explanation']}</div>", unsafe_allow_html=True)
                        
                        st.markdown("---")

                    if not is_sub:
                        if st.form_submit_button("NỘP BÀI THI", type="primary"):
                            for i in range(len(batch['data'])):
                                key = f"rad_{b_idx}_{i}"
                                val = st.session_state.get(key)
                                if val:
                                    try:
                                        current_opts = [f"{['A','B','C','D'][k]}. {o}" for k, o in enumerate(batch['data'][i]['data']['options'])]
                                        ans_idx = current_opts.index(val)
                                        batch['data'][i]['user_ans'] = ans_idx
                                    except: pass
                            batch['is_submitted'] = True
                            st.rerun()
                    else:
                        st.form_submit_button("Đã nộp bài", disabled=True)

elif not st.session_state.quiz_batches:
    st.info("👋 Chào mừng! Hãy chọn chế độ bên trái (Sidebar) và bắt đầu tạo câu hỏi.")
