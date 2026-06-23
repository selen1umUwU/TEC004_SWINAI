# ============================================================
# CHATBOT BACKEND - PYTHON FLASK
# Tác vụ: Nhận tin nhắn từ frontend, gọi Gemini API với failover
# ============================================================

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import logging
import sqlite3
import os
from datetime import datetime
from uuid import uuid4

app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_FILE = 'chatbot_data.db'

def init_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            sender TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized")

init_database()

# ============================================================
# CẤU HÌNH API KEYS
# ============================================================
API_KEYS = ['sk-bee-76dc076cf67f2b50f30da50caf08831fa1d41de02052204f56e06e5755d04569',  # API Key Beeknoee của bạn
    'AQ.Ab8RN6JNeYr3HpMteBQ7BBT5nUT5CWbsyLCtOPt3z4zw11LpsA',  # API Gemini 1
    'AQ.Ab8RN6IjUT1JQvPoNxLNbyz82Dog9lBSi633iAbxBH-AJMD3Rg'   # API Gemini 2
]

API_TYPES = ['beeknoee', 'gemini', 'gemini']

# ĐÃ SỬA: Sửa lại URL chuẩn của Beeknoee
BEEKNOEE_MODEL = 'google/gemini-2.5-flash-lite'
BEEKNOEE_API_URL = 'https://platform.beeknoee.com/api/v1/chat/completions'

GEMINI_MODEL = 'gemini-2.5-flash' 
GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models'

current_api_index = 0

SYSTEM_PROMPT = """# VAI TRÒ CHUYÊN GIA
Bạn là SwinAI - Chuyên gia Tuyển sinh cấp cao, đại diện chính thức cho Swinburne Vietnam. Bạn sở hữu kho dữ liệu khổng lồ, luôn phản hồi với thái độ tận tâm, chuyên nghiệp, cấu trúc logic và phong cách "đậm chất quốc tế".

# HỆ THỐNG KIẾN THỨC TOÀN DIỆN (KNOWLEDGE BASE)

1. HỌC THUẬT & BẰNG CẤP QUỐC TẾ
- Bằng cấp: 100% bằng Cử nhân do Swinburne University of Technology (Úc) cấp, có giá trị quốc tế trên toàn cầu[cite: 5].
- Phương pháp đào tạo: Áp dụng phương pháp Học tập qua dự án (Project-based learning), giúp sinh viên giải quyết các vấn đề thực tế của doanh nghiệp ngay trên ghế nhà trường[cite: 5].
- Giảng viên: Đội ngũ giảng viên, chuyên gia quốc tế và từ các tập đoàn công nghệ/kinh doanh lớn, mang lại trải nghiệm học tập thực chiến cao[cite: 5].

2. MÔI TRƯỜNG TRẢI NGHIỆM TẠI CÁC CHI NHÁNH
- Cơ sở vật chất: Hệ thống phòng lab hiện đại, không gian làm việc nhóm (Coworking space) tiêu chuẩn quốc tế, thư viện số phong phú tại cả chi nhánh Hà Nội và TP.HCM[cite: 5].
- Hệ sinh thái câu lạc bộ: Sinh viên được tham gia các CLB chuyên sâu:
    + Công nghệ: CLB AI, Dev, Cybersecurity, Game Development[cite: 5].
    + Kinh doanh: CLB Startup, Quản trị sự kiện, Kinh tế quốc tế[cite: 5].
    + Truyền thông: CLB Media, Content Marketing, Nhiếp ảnh, Thiết kế[cite: 5].
- Sự kiện kết nối: Thường xuyên tổ chức Industry Link (kết nối doanh nghiệp), Workshop kỹ năng mềm, các cuộc thi Hackathon và đêm hội văn hóa[cite: 5].

3. LỘ TRÌNH SỰ NGHIỆP TỪNG NGÀNH
- Ngành Công nghệ thông tin (ICT): Từ nền tảng lập trình đến các chuyên ngành sâu (AI, IoT, An toàn thông tin), cơ hội thực tập tại các tập đoàn công nghệ hàng đầu từ năm thứ 2[cite: 5].
- Ngành Quản trị Kinh doanh (Business): Phát triển tư duy lãnh đạo, chiến lược marketing, quản trị tài chính, chuẩn bị sẵn sàng cho môi trường làm việc toàn cầu[cite: 5].
- Ngành Truyền thông đa phương tiện (Media): Tập trung vào sáng tạo số, sản xuất truyền thông, xây dựng thương hiệu, chú trọng kỹ năng làm việc thực tế với các dự án thực tế[cite: 5].

4. CƠ CHẾ TUYỂN SINH & HỌC BỔNG 2026
- Điều kiện đầu vào: Tốt nghiệp THPT, GPA lớp 11 hoặc 12 từ 7.0 trở lên[cite: 5].
- Phân bậc học bổng:
    + Change-Maker (50 - 100 triệu VNĐ): GPA từ 7.0 trở lên, khao khát môi trường quốc tế[cite: 5].
    + Pioneer (125 - 150 triệu VNĐ): GPA từ 8.0 trở lên, IELTS từ 6.0 trở lên, tinh thần tiên phong[cite: 5].
    + NextGen (175 - 200 triệu VNĐ): GPA từ 8.5 trở lên, có hoạt động xã hội nổi bật[cite: 5].
    + Talent (225 - 250 triệu VNĐ): GPA từ 9.0 trở lên, IELTS từ 7.0 trở lên, năng lực tư duy xuất sắc[cite: 5].
    + FPT Talent (125 triệu VNĐ): GPA từ 7.0 trở lên, dành cho con em nhân viên FPT[cite: 5].


# QUY TẮC TRẢ LỜI
LƯU Ý ƯU TIÊN HÀNG ĐẦU: THÔNG TIN PHẢI LÀ TỪ THÔNG TIN MỚI NHẤT 2026, TỪ TRÊN WEB CHÍNH CHỦ "https://swinburne-vn.edu.vn/" VÀ TRẢ LỜI THẬT SỰ ĐÚNG TRỌNG TÂM VÀ KHÔNG DƯ THỪA
+ CHÚ Ý CÁC THANG ĐIỂM IELTS (0-9), HAY CÁC CHỨNG CHỈ KHÁC VÌ CHÚNG CÓ GIỚI HẠN THANG ĐIỂM MAX VÀ MIN, TƯ VẤN TUYỂN SINH THỰC SỰ ĐÚNG ĐỦ.
1. KHÔNG HỎI NGƯỢC: Tuyệt đối không đặt câu hỏi ngược lại cho người dùng (ví dụ: không hỏi "Bạn có quan tâm ngành nào không?", "Bạn học lớp mấy?").
2. ĐỊNH DẠNG SẠCH: Sử dụng các đoạn văn ngắn, mỗi ý một dòng hoặc bullet point đơn giản. Tuyệt đối không nhồi nhét text thành một khối dày đặc gây lỗi hiển thị như image_935902.png.
3. CHỈ TƯ VẤN: Chỉ cung cấp thông tin về ngành học, học bổng, bằng cấp, môi trường.
4. TỪ CHỐI KHÉO LÉO: Nếu hỏi ngoài lề, trả lời: "Xin lỗi, mình chỉ hỗ trợ thông tin tuyển sinh Swinburne Vietnam."
5. FALLBACK: Nếu không biết hoặc cần thẩm định, chỉ cung cấp duy nhất số hotline: "Vui lòng liên hệ 0773131319 để được hỗ trợ chi tiết.
# QUY TẮC TRÌNH BÀY (CẤP BÁCH)
1. CẤM dùng cú pháp Markdown in đậm/nghiêng (như ** hoặc *).
2. Khi liệt kê ý, dùng dấu gạch ngang (-) ở đầu dòng thay cho dấu *. 
3. Xuống dòng (Enter) giữa các đoạn văn để tạo khoảng cách thoáng.
4. Trả lời dưới dạng danh sách các dòng đơn lẻ, tuyệt đối không viết thành một đoạn văn bản dài nối đuôi nhau."""
def get_current_api_key():
    return API_KEYS[current_api_index]

def get_current_api_url():
    api_key = get_current_api_key()
    return f"{GEMINI_API_URL}/{GEMINI_MODEL}:generateContent?key={api_key}"

def save_message_to_db(chat_id, sender, content):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (session_id, sender, content)
            VALUES (?, ?, ?)
        ''', (chat_id, sender, content))
        cursor.execute('''
            UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (chat_id,))
        conn.commit()
        conn.close()
        logger.info(f"💾 Đã lưu tin nhắn: {chat_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Lỗi lưu DB: {str(e)}")
        return False

def create_chat_session(title):
    try:
        chat_id = str(uuid4())
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO chat_sessions (id, title)
            VALUES (?, ?)
        ''', (chat_id, title))
        conn.commit()
        conn.close()
        logger.info(f"✅ Tạo session: {chat_id}")
        return chat_id
    except Exception as e:
        logger.error(f"❌ Lỗi tạo session: {str(e)}")
        return None

def get_chat_session(chat_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT id, title, created_at FROM chat_sessions WHERE id = ?', (chat_id,))
        row = cursor.fetchone()
        if row:
            cursor.execute('SELECT sender, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at', (chat_id,))
            messages = []
            for msg_row in cursor.fetchall():
                messages.append({
                    'sender': msg_row[0],
                    'content': msg_row[1],
                    'timestamp': msg_row[2]
                })
            conn.close()
            return {
                'id': row[0],
                'title': row[1],
                'created_at': row[2],
                'messages': messages
            }
        conn.close()
        return None
    except Exception as e:
        logger.error(f"❌ Lỗi lấy session: {str(e)}")
        return None

def get_all_chat_sessions():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, title, created_at, updated_at 
            FROM chat_sessions 
            ORDER BY updated_at DESC
        ''')
        sessions = []
        for row in cursor.fetchall():
            sessions.append({
                'id': row[0],
                'title': row[1],
                'created_at': row[2],
                'updated_at': row[3]
            })
        conn.close()
        return sessions
    except Exception as e:
        logger.error(f"❌ Lỗi lấy danh sách session: {str(e)}")
        return []
    # ĐÃ XÓA ĐOẠN CODE BỊ THỪA GÂY LỖI SYNTAX Ở ĐÂY

def is_token_error(status_code, error_data):
    token_error_codes = [429, 401, 403]
    if status_code in token_error_codes:
        return True
    if error_data and 'error' in error_data:
        error_msg = json.dumps(error_data['error']).upper()
        token_keywords = ['QUOTA', 'RATE', 'TOKEN', 'UNAUTHORIZED', 'QUOTA_EXCEEDED']
        for keyword in token_keywords:
            if keyword in error_msg:
                return True
    return False

def switch_to_next_api():
    global current_api_index
    if current_api_index < len(API_KEYS) - 1:
        current_api_index += 1
        logger.info(f"🔄 Chuyển sang API #{current_api_index + 1}")
        return True
    logger.warning("❌ Hết API dự phòng!")
    return False

def reset_api_index():
    global current_api_index
    current_api_index = 0

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        if not user_message:
            return jsonify({'success': False, 'error': 'Tin nhắn không được để trống'}), 400
        logger.info(f"📨 Nhận tin nhắn: {user_message[:50]}...")
        response_data = process_message_with_failover(user_message)
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"❌ Lỗi: {str(e)}")
        return jsonify({'success': False, 'error': f'Lỗi server: {str(e)}'}), 500

def process_message_with_failover(user_message):
    global current_api_index
    reset_api_index()
    max_retries = len(API_KEYS)
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        logger.info(f"⏱️  Lần thử #{attempt}, API #{current_api_index + 1}")
        response_data = call_api(user_message)
        if response_data['success']:
            logger.info(f"✅ Thành công với API #{current_api_index + 1}")
            response_data['current_api'] = current_api_index + 1
            return response_data
        if response_data.get('is_token_error'):
            logger.warning(f"⚠️  Lỗi token ở API #{current_api_index + 1}")
            if switch_to_next_api():
                logger.info("🔄 Đang thử API khác...")
                continue
            else:
                return {
                    'success': False,
                    'error': '😞 Tất cả API đều gặp vấn đề. Vui lòng thử lại sau.',
                    'current_api': current_api_index + 1
                }
        response_data['current_api'] = current_api_index + 1
        return response_data
    return {
        'success': False,
        'error': 'Không thể kết nối đến API sau nhiều lần thử',
        'current_api': current_api_index + 1
    }

def call_beeknoee_api(user_message):
    try:
        api_key = get_current_api_key()
        request_body = {
            'model': BEEKNOEE_MODEL,
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': user_message}
            ],
            'temperature': 0.7,
            'max_tokens': 1000
        }
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        logger.info(f"📡 Gọi Beeknoee API")
        response = requests.post(BEEKNOEE_API_URL, json=request_body, headers=headers, timeout=30)
        
        try:
            response_data = response.json()
        except ValueError as e:
            logger.error(f"❌ Response không phải JSON: {str(e)}")
            return {'success': False, 'error': 'Endpoint không hợp lệ', 'is_token_error': True}
        
        if not response.ok:
            is_token_err = is_token_error(response.status_code, response_data)
            return {'success': False, 'error': f"Lỗi Beeknoee API: {response.status_code}", 'is_token_error': is_token_err}
        
        bot_reply = response_data['choices'][0]['message']['content']
        return {'success': True, 'reply': bot_reply, 'is_token_error': False}
    except Exception as e:
        logger.error(f"❌ Lỗi Beeknoee: {str(e)}")
        return {'success': False, 'error': str(e), 'is_token_error': False}

def call_api(user_message):
    api_type = API_TYPES[current_api_index]
    if api_type == 'beeknoee':
        return call_beeknoee_api(user_message)
    else:
        return call_gemini_api(user_message)

def call_gemini_api(user_message):
    try:
        api_url = get_current_api_url()
        request_body = {
            'systemInstruction': {'parts': [{'text': SYSTEM_PROMPT}]},
            'contents': [{'parts': [{'text': user_message}]}]
        }
        logger.info(f"📡 Gọi Gemini API")
        response = requests.post(api_url, json=request_body, timeout=30)
        response_data = response.json()
        
        if not response.ok:
            is_token_err = is_token_error(response.status_code, response_data)
            return {'success': False, 'error': f"Lỗi API: {response.status_code}", 'is_token_error': is_token_err}
        
        bot_reply = response_data['candidates'][0]['content']['parts'][0]['text']
        return {'success': True, 'reply': bot_reply, 'is_token_error': False}
    except Exception as e:
        logger.error(f"❌ Lỗi Gemini: {str(e)}")
        return {'success': False, 'error': str(e), 'is_token_error': False}

@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({
        'status': 'running',
        'current_api_index': current_api_index + 1,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/reset', methods=['POST'])
def reset():
    reset_api_index()
    return jsonify({'success': True, 'current_api_index': 1})

@app.route('/api/save-chat', methods=['POST'])
def save_chat():
    data = request.get_json()
    if save_message_to_db(data.get('chat_id'), data.get('sender', 'user'), data.get('message')):
        return jsonify({'success': True})
    return jsonify({'success': False}), 500

@app.route('/api/chats', methods=['GET'])
def get_chats():
    return jsonify({'success': True, 'chats': get_all_chat_sessions()})

@app.route('/api/chat/<chat_id>', methods=['GET'])
def get_chat_detail(chat_id):
    chat = get_chat_session(chat_id)
    if chat:
        return jsonify({'success': True, 'chat': chat})
    return jsonify({'success': False}), 404

@app.route('/api/chat-new', methods=['POST'])
def create_new_chat():
    chat_id = create_chat_session(request.get_json().get('title', 'New Chat'))
    if chat_id:
        return jsonify({'success': True, 'chat_id': chat_id})
    return jsonify({'success': False}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)