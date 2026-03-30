import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import time

# [v3.5.0] 클라이언트 설정
@st.cache_resource
def setup_clients():
    g_key = st.secrets.get("GEMINI_KEY")
    gr_key = st.secrets.get("GROQ_KEY")
    return g_key, gr_key

GEMINI_KEY, GROQ_KEY = setup_clients()

# [구성] Gemini와 Groq 모델 리스트
PRIORITY_MAP = {
    "1. Gemini-2.0-F": ["gemini-2.0-flash", "llama-3.3-70b-versatile"], # Gemini 안되면 Llama로!
    "2. Gemini-1.5-P": ["gemini-1.5-pro", "mixtral-8x7b-32768"],
    "3. Gemini-1.5-F": ["gemini-1.5-flash", "llama-3.1-8b-instant"],
    "4. Gemini-Exp": ["gemini-1.5-pro", "llama-3.3-70b-versatile"],
    "5. Groq-Llama-70B": ["llama-3.3-70b-versatile"],
    "6. Groq-Llama-8B": ["llama-3.1-8b-instant"],
    "7. Groq-Mixtral": ["mixtral-8x7b-32768"],
    "8. Groq-Expert": ["llama-3.3-70b-versatile"]
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

def sync_api_call(family, model_id, prompt):
    if not prompt.strip(): return ""
    
    # 후보 모델 (Gemini 실패 시 Groq 모델로 즉시 우회)
    candidates = PRIORITY_MAP.get(family, [model_id])
    
    for current_model in candidates:
        try:
            # 1. Gemini 호출 시도
            if "gemini" in current_model.lower():
                genai.configure(api_key=GEMINI_KEY)
                model = genai.GenerativeModel(model_name=current_model)
                res = model.generate_content(prompt)
                if res and res.text:
                    return res.text
            
            # 2. Groq 호출 시도 (Gemini 실패 시 혹은 원래 Groq 슬롯일 때)
            else:
                r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}"},
                    json={"model": current_model, "messages": [{"role": "user", "content": prompt}]}, timeout=25)
                if r.status_code == 200:
                    content = r.json()['choices'][0]['message']['content']
                    tag = "" if "Groq" in family else f"\n\n*(Gemini 할당량 초과로 {current_model}가 대신 답변함)*"
                    return content + tag
                elif r.status_code == 429: # Groq도 바쁘면 다음 시도
                    continue
        except:
            continue
            
    return f"⚠️ {family}: 모든 모델(Gemini/Groq) 호출 실패"

async def async_worker(index, family, model_id, prompt, placeholders):
    # 호출 간 시차를 줘서 동시 충돌 방지
    await asyncio.sleep(index * 1.0)
    res = await asyncio.to_thread(sync_api_call, family, model_id, prompt)
    st.session_state.res_list[index] = res
    placeholders[index].markdown(f'''<div class="res-card"><span class="model-info">{index+1}. {family} • {model_id}</span>{res}</div>''', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="AI Expert 8-Arena", layout="wide")
    apply_style()
    f_names = list(PRIORITY_MAP.keys())
    num_models = len(f_names)

    if 'res_list' not in st.session_state: st.session_state.res_list = [""] * num_models

    st.markdown("<h2 style='text-align: center;'>⚡ AI Expert 8-Arena (v3.5.0)</h2>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.write("### ⚙️ 모델 설정")
        selected = {fam: st.selectbox(f"{fam}", cfg, key=f"sel_{fam}") for fam, cfg in PRIORITY_MAP.items()}

    main_q = st.text_area("Global Input", placeholder="Gemini 할당량 초과 시 Groq 모델이 자동으로 지원합니다...", key="g_input", height=100)
    
    if st.button("🔍 8개 모델 통합 분석 시작", use_container_width=True) and main_q.strip():
        cols = st.columns(2)
        placeholders = [cols[i % 2].empty() for i in range(num_models)]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(asyncio.gather(*(async_worker(i, f_names[i], selected[f_names[i]], main_q, placeholders) for i in range(num_models))))
        st.rerun()

    st.divider()
    cols = st.columns(2)
    for i in range(num_models):
        with cols[i % 2]:
            st.markdown(f'''<div class="res-card"><span class="model-info">{i+1}. {f_names[i]}</span>{st.session_state.res_list[i] if st.session_state.res_list[i] else "..."}</div>''', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
