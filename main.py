import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import time

# [v3.6.0] 클라이언트 설정
@st.cache_resource
def setup_clients():
    return st.secrets.get("GEMINI_KEY"), st.secrets.get("GROQ_KEY")

GEMINI_KEY, GROQ_KEY = setup_clients()

# [구성] Gemini 실패 시 Groq로, Groq 실패 시 Gemini로 서로 교차 백업
PRIORITY_MAP = {
    "1. Gemini-2.0-F": ["gemini-2.0-flash", "llama-3.3-70b-versatile"],
    "2. Gemini-1.5-P": ["gemini-1.5-pro", "mixtral-8x7b-32768"],
    "3. Gemini-1.5-F": ["gemini-1.5-flash", "llama-3.1-8b-instant"],
    "4. Gemini-Exp": ["gemini-1.5-pro", "llama-3.3-70b-versatile"],
    "5. Groq-Llama-70B": ["llama-3.3-70b-versatile", "gemini-1.5-flash"],
    "6. Groq-Llama-8B": ["llama-3.1-8b-instant", "gemini-2.0-flash"],
    "7. Groq-Mixtral": ["mixtral-8x7b-32768", "gemini-1.5-flash"],
    "8. Groq-Expert": ["llama-3.3-70b-versatile", "gemini-1.5-pro"]
}

def apply_style():
    st.markdown("""
        <style>
        .block-container { max-width: 100% !important; padding: 1rem 2% !important; background-color: #f8fafc; }
        .res-card {
            background: white; border: 1px solid #e2e8f0; border-radius: 12px; 
            padding: 16px; margin-bottom: 5px; min-height: 120px; max-height: 400px; 
            overflow-y: auto; font-size: 14px; border-left: 6px solid #3b82f6;
        }
        .model-info { font-size: 11px; font-weight: 800; color: #1e40af; margin-bottom: 5px; display: block; }
        .stButton button { background-color: #ef4444 !important; color: white !important; font-weight: bold !important; border-radius: 10px !important; height: 3.5rem; }
        </style>
    """, unsafe_allow_html=True)

# [핵심] 끈질긴 재시도 로직 (Exponential Backoff)
def persistent_call(family, model_id, prompt):
    if not prompt.strip(): return ""
    candidates = PRIORITY_MAP.get(family, [model_id])
    
    for current_model in candidates:
        for attempt in range(3): # 모델당 3번 재시도
            try:
                # 1. Gemini 호출
                if "gemini" in current_model.lower():
                    genai.configure(api_key=GEMINI_KEY)
                    model = genai.GenerativeModel(model_name=current_model)
                    res = model.generate_content(prompt)
                    if res and res.text: return res.text
                
                # 2. Groq 호출
                else:
                    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {GROQ_KEY}"},
                        json={"model": current_model, "messages": [{"role": "user", "content": prompt}]}, timeout=30)
                    if r.status_code == 200:
                        return r.json()['choices'][0]['message']['content']
                    elif r.status_code == 429: # 속도 제한 시 대기 후 재시도
                        time.sleep(attempt * 5 + 3) # 3초, 8초, 13초 점점 길게 대기
                        continue
            except:
                time.sleep(2)
                continue
    return "⚠️ 모든 엔진 응답 거부 (할당량 초기화 대기 필요)"

async def async_worker(index, family, model_id, prompt, placeholders):
    # 호출 간격을 대폭 늘려 (2초씩) 서버 부하 분산
    await asyncio.sleep(index * 2.0)
    res = await asyncio.to_thread(persistent_call, family, model_id, prompt)
    st.session_state.res_list[index] = res
    placeholders[index].markdown(f'''<div class="res-card"><span class="model-info">{index+1}. {family}</span>{res}</div>''', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="AI Expert 8-Arena", layout="wide")
    apply_style()
    f_names = list(PRIORITY_MAP.keys())
    num_models = len(f_names)

    if 'res_list' not in st.session_state: st.session_state.res_list = [""] * num_models

    st.markdown("<h2 style='text-align: center;'>⚡ AI Expert 8-Arena (v3.6.0)</h2>", unsafe_allow_html=True)
    st.warning("⚠️ 현재 API 할당량이 매우 부족합니다. '저속 안전 모드'로 하나씩 천천히 불러옵니다.")
    
    main_q = st.text_area("Global Input", placeholder="입력 후 잠시 기다려 주세요. 끈질기게 답변을 시도합니다...", key="g_input", height=100)
    
    if st.button("🔥 할당량 뚫기: 강제 호출 시작", use_container_width=True) and main_q.strip():
        cols = st.columns(2)
        placeholders = [cols[i % 2].empty() for i in range(num_models)]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(asyncio.gather(*(async_worker(i, f_names[i], PRIORITY_MAP[f_names[i]][0], main_q, placeholders) for i in range(num_models))))
        st.rerun()

    st.divider()
    cols = st.columns(2)
    for i in range(num_models):
        with cols[i % 2]:
            st.markdown(f'''<div class="res-card"><span class="model-info">{i+1}. {f_names[i]}</span>{st.session_state.res_list[i] if st.session_state.res_list[i] else "대기 중..."}</div>''', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
