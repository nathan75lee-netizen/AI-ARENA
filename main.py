import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import time

# [v3.1.0] 클라이언트 및 쿼터 관리 설정
@st.cache_resource
def setup_clients():
    g_key = st.secrets.get("GEMINI_KEY")
    gr_key = st.secrets.get("GROQ_KEY")
    valid_gemini = []
    if g_key:
        try:
            genai.configure(api_key=g_key)
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    valid_gemini.append(m.name.replace("models/", ""))
        except: pass
    if not valid_gemini: valid_gemini = ["gemini-2.0-flash", "gemini-1.5-flash"]
    return g_key, gr_key, valid_gemini

GEMINI_KEY, GROQ_KEY, VALID_GEMINI = setup_clients()

PRIORITY_MAP = {
    "Gemini-Pro": ["gemini-1.5-pro", "gemini-2.0-flash"],
    "Gemini-Flash": ["gemini-2.0-flash", "gemini-1.5-flash"],
    "Llama-Ultra": ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile"],
    "Llama-Speed": ["llama-3.1-8b-instant", "llama-3.2-3b-preview"],
    "Mixtral": ["mixtral-8x7b-32768"],
    "Gemini-Ref": ["gemini-1.5-pro", "gemini-1.5-flash"],
    "Llama-Ref": ["llama-3.3-70b-versatile"],
    "Final-Expert": ["gemini-2.0-flash", "llama-3.3-70b-versatile"]
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
        .stButton button { background-color: #3b82f6 !important; color: white !important; font-weight: bold !important; border-radius: 10px !important; height: 3.5rem; }
        </style>
    """, unsafe_allow_html=True)

# [핵심] 쿼터 초과 시 재시도하는 지능형 호출 함수
def sync_api_call(family, model_id, prompt, retry_count=3):
    if not prompt.strip(): return ""
    session = requests.Session()
    
    for attempt in range(retry_count):
        try:
            # 호출 간 미세 지연 (분당 호출 제한 방지)
            time.sleep(attempt * 2 + 0.5) 
            
            if "gemini" in model_id.lower() or "Gemini" in family:
                model = genai.GenerativeModel(model_name=model_id.split('/')[-1])
                res = model.generate_content(prompt)
                if res and res.text: return res.text
            
            else: # Groq 호출
                r = session.post("https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}"},
                    json={"model": model_id, "messages": [{"role": "user", "content": prompt}]}, timeout=25)
                
                if r.status_code == 200:
                    return r.json()['choices'][0]['message']['content']
                elif r.status_code == 429: # 쿼터 초과 시 다음 루프에서 재시도
                    continue
        except Exception as e:
            if attempt == retry_count - 1: return f"⚠️ 호출 실패: {str(e)}"
            continue
            
    return f"⚠️ {family}: 쿼터 제한으로 답변을 가져오지 못했습니다. (1분 후 시도하세요)"

async def async_worker(index, family, model_id, prompt, placeholders):
    # 각 작업 시작 시 미세한 시차를 줘서 동시 충돌 방지
    await asyncio.sleep(index * 0.8) 
    res = await asyncio.to_thread(sync_api_call, family, model_id, prompt)
    st.session_state.res_list[index] = res
    placeholders[index].markdown(f'''<div class="res-card"><span class="model-info">{index+1}. {family} • {model_id}</span>{res}</div>''', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="AI Expert 8-Arena", layout="wide")
    apply_style()
    f_names = list(PRIORITY_MAP.keys())
    num_models = len(f_names)

    if 'res_list' not in st.session_state: st.session_state.res_list = [""] * num_models

    st.markdown("<h2 style='text-align: center;'>⚡ AI Expert 8-Arena (v3.1.0)</h2>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.write("### ⚙️ 모델 설정")
        selected = {fam: st.selectbox(f"{fam}", cfg, key=f"sel_{fam}") for fam, cfg in PRIORITY_MAP.items()}

    main_q = st.text_area("Global Input", placeholder="쿼터 제한을 피하기 위해 순차적으로 호출합니다...", label_visibility="collapsed", key="g_input", height=100)
    
    if st.button("🔍 모든 AI 답변 동시 시작", use_container_width=True) and main_q.strip():
        cols = st.columns(2)
        placeholders = [cols[i % 2].empty() for i in range(num_models)]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(asyncio.gather(*(async_worker(i, f_names[i], selected[f_names[i]], main_q, placeholders) for i in range(num_models))))
        st.rerun()

    st.divider()
    cols = st.columns(2)
    for i in range(num_models):
        fam = f_names[i]
        with cols[i % 2]:
            st.markdown(f'''<div class="res-card"><span class="model-info">{i+1}. {fam} • {selected[fam]}</span>{st.session_state.res_list[i] if st.session_state.res_list[i] else "..."}</div>''', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
