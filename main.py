import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import time

# [v3.4.0] 클라이언트 설정 (Gemini & Groq 전용)
@st.cache_resource
def setup_clients():
    g_key = st.secrets.get("GEMINI_KEY")
    gr_key = st.secrets.get("GROQ_KEY")
    
    # Gemini 모델 목록 초기화
    valid_gemini = []
    if g_key:
        try:
            genai.configure(api_key=g_key)
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    valid_gemini.append(m.name.replace("models/", ""))
        except: pass
    
    # 목록이 비어있을 경우 기본값 강제 할당
    if not valid_gemini:
        valid_gemini = ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash"]
        
    return g_key, gr_key, valid_gemini

GEMINI_KEY, GROQ_KEY, VALID_GEMINI = setup_clients()

# [구성] 8개 슬롯 모델 배치 (Gemini 4개 / Groq 4개)
PRIORITY_MAP = {
    "1. Gemini-2.0-F": ["gemini-2.0-flash", "gemini-1.5-flash"],
    "2. Gemini-1.5-P": ["gemini-1.5-pro", "gemini-2.0-flash"],
    "3. Gemini-1.5-F": ["gemini-1.5-flash", "gemini-2.0-flash"],
    "4. Gemini-Exp": ["gemini-1.5-pro", "gemini-1.5-flash"],
    "5. Groq-Llama-70B": ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile"],
    "6. Groq-Llama-8B": ["llama-3.1-8b-instant", "llama-3.2-3b-preview"],
    "7. Groq-Mixtral": ["mixtral-8x7b-32768"],
    "8. Groq-Backup": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"]
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
        .summary-box { background: #f0fdf4; border: 2px solid #bbf7d0; border-radius: 15px; padding: 20px; margin-top: 20px; border-left: 10px solid #22c55e; }
        </style>
    """, unsafe_allow_html=True)

def sync_api_call(family, model_id, prompt):
    if not prompt.strip(): return ""
    
    # 후보 모델 리스트 (현재 모델 실패 시 자동 우회용)
    candidates = [model_id] + [m for m in PRIORITY_MAP.get(family, []) if m != model_id]
    
    for current_model in candidates:
        try:
            # Gemini 호출부
            if "Gemini" in family:
                genai.configure(api_key=GEMINI_KEY)
                model = genai.GenerativeModel(model_name=current_model)
                res = model.generate_content(prompt)
                if res and res.text:
                    tag = "" if current_model == model_id else f"\n\n*(우회: {current_model})*"
                    return res.text + tag
            
            # Groq 호출부
            else:
                r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}"},
                    json={"model": current_model, "messages": [{"role": "user", "content": prompt}]}, timeout=25)
                if r.status_code == 200:
                    tag = "" if current_model == model_id else f"\n\n*(우회: {current_model})*"
                    return r.json()['choices'][0]['message']['content'] + tag
                elif r.status_code == 429: # 속도 제한 시 다음 모델로
                    continue
        except:
            continue
    return f"⚠️ {family}: 호출 실패 (쿼터 초과)"

async def async_worker(index, family, model_id, prompt, placeholders):
    # 호출 간 미세 시차 (index 0~7 순차적 지연)
    await asyncio.sleep(index * 1.2)
    res = await asyncio.to_thread(sync_api_call, family, model_id, prompt)
    st.session_state.res_list[index] = res
    placeholders[index].markdown(f'''<div class="res-card"><span class="model-info">{index+1}. {family} • {model_id}</span>{res}</div>''', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="AI Expert 8-Arena", layout="wide")
    apply_style()
    f_names = list(PRIORITY_MAP.keys())
    num_models = len(f_names)

    if 'res_list' not in st.session_state: st.session_state.res_list = [""] * num_models

    st.markdown("<h2 style='text-align: center;'>⚡ AI Expert 8-Arena (v3.4.0)</h2>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.write("### ⚙️ 모델 설정 (Gemini/Groq)")
        selected = {fam: st.selectbox(f"{fam}", cfg, key=f"sel_{fam}") for fam, cfg in PRIORITY_MAP.items()}

    main_q = st.text_area("Global Input", placeholder="Gemini와 Groq API만 사용하여 분석합니다...", label_visibility="collapsed", key="g_input", height=100)
    
    if st.button("🔍 8개 모델 동시 분석 시작", use_container_width=True) and main_q.strip():
        if 'summary_res' in st.session_state: del st.session_state.summary_res
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

    if any(st.session_state.res_list) and st.button("📝 전문가 요약", use_container_width=True):
        valid_ans = "".join([f"[{f_names[i]}]: {st.session_state.res_list[i]}\n\n" for i in range(num_models) if st.session_state.res_list[i] and "⚠️" not in st.session_state.res_list[i]])
        if valid_ans:
            st.session_state.summary_res = sync_api_call("Gemini-Flash", "gemini-1.5-flash", f"요약해줘:\n\n{valid_ans}")
            st.rerun()

    if 'summary_res' in st.session_state:
        st.markdown(f'<div class="summary-box"><h4>💡 종합 분석 리포트</h4>{st.session_state.summary_res}</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
