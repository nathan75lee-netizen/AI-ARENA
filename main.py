import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import json

# [v2.9.2 복원] 클라이언트 및 모델 리스트 설정
@st.cache_resource
def setup_clients():
    g_key = st.secrets.get("GEMINI_KEY")
    or_key = st.secrets.get("OR_KEY")
    gr_key = st.secrets.get("GR_KEY")
    valid_gemini = []
    if g_key:
        try:
            genai.configure(api_key=g_key)
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    valid_gemini.append(m.name.replace("models/", ""))
        except: pass
    if not valid_gemini: valid_gemini = ["gemini-2.0-flash", "gemini-1.5-pro"]
    return g_key, or_key, gr_key, valid_gemini

GEMINI_KEY, OR_KEY, GROQ_KEY, VALID_GEMINI = setup_clients()

PRIORITY_MAP = {
    "Gemini": VALID_GEMINI,
    "Groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
    "GPT": ["openai/gpt-4o", "openai/gpt-4o-mini"],
    "Claude": ["anthropic/claude-3.5-sonnet", "anthropic/claude-3-haiku"],
    "Llama": ["meta-llama/llama-3.3-70b-instruct", "meta-llama/llama-3.2-3b-instruct:free"],
    "DeepSeek": ["deepseek/deepseek-chat", "deepseek/deepseek-r1:free"],
    "Mistral": ["mistralai/pixtral-12b", "mistralai/mistral-nemo"],
    "Gemma": ["google/gemma-2-27b-it", "google/gemma-2-9b-it"]
}

def apply_style():
    st.markdown("""
        <style>
        .block-container { max-width: 100% !important; padding: 0.5rem 2% !important; background-color: #f8fafc; }
        .main-title { font-size: 1.1rem !important; font-weight: 800; text-align: center; margin-bottom: 10px; color: #1e293b; }
        .res-card {
            background: white; border: 1px solid #e2e8f0; border-radius: 12px; 
            padding: 12px; margin-bottom: 5px; min-height: 80px; max-height: 380px; 
            overflow-y: auto; font-size: 13px; border-left: 5px solid #3b82f6; color: #334155;
        }
        .model-info { font-size: 10px; font-weight: 800; color: #1e40af; margin-bottom: 3px; display: block; }
        .stButton button { width: 100%; height: 3.2rem !important; font-weight: bold !important; border-radius: 10px !important; }
        .summary-box { background: #f0fdf4; border: 2px solid #bbf7d0; border-radius: 12px; padding: 15px; border-left: 8px solid #22c55e; font-size: 14px; color: #166534; }
        </style>
    """, unsafe_allow_html=True)

# [엔진] API 호출 함수 (Groq 강화 버전 유지)
def sync_api_call(family, model_id, prompt):
    if not prompt.strip(): return ""
    session = requests.Session()
    candidates = [model_id] + [m for m in PRIORITY_MAP.get(family, []) if m != model_id]
    
    for current_model in candidates:
        try:
            if family == "Gemini":
                model = genai.GenerativeModel(model_name=current_model.split('/')[-1])
                res = model.generate_content(prompt)
                if res and res.text: return res.text
            elif family == "Groq":
                r = session.post("https://api.groq.com/openai/v1/chat/completions", 
                    headers={"Authorization": f"Bearer {GROQ_KEY}"}, 
                    json={"model": current_model, "messages": [{"role": "user", "content": prompt}]}, 
                    timeout=30)
                if r.status_code == 200: return r.json()['choices'][0]['message']['content']
                elif r.status_code == 429: continue
            else:
                r = session.post("https://openrouter.ai/api/v1/chat/completions", 
                    headers={"Authorization": f"Bearer {OR_KEY}", "HTTP-Referer": "http://localhost:8501"}, 
                    json={"model": current_model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1000}, 
                    timeout=35)
                if r.status_code == 200: return r.json()['choices'][0]['message']['content']
        except: continue
    return f"⚠️ {family} 호출 실패"

async def async_worker(index, family, model_id, prompt, placeholders):
    res = await asyncio.to_thread(sync_api_call, family, model_id, prompt)
    st.session_state.res_list[index] = res
    placeholders[index].markdown(f'''<div class="res-card"><span class="model-info">{index+1}. {family} • {model_id.split("/")[-1]}</span>{res}</div>''', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="AI Expert Center", layout="wide")
    apply_style()
    
    if 'res_list' not in st.session_state: st.session_state.res_list = [""] * 8
    if 'debate_history' not in st.session_state: st.session_state.debate_history = []

    st.markdown('<div class="main-title">⚡ AI Expert Multi-Solution Center</div>', unsafe_allow_html=True)

    # [v2.9.2 핵심] 전역 입력창
    main_q = st.text_area("Global Input", placeholder="질문을 입력하세요...", label_visibility="collapsed", key="g_input", height=80)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 Arena 모드 시작", key="arena_main_btn"):
            if main_q.strip():
                # [v2.9.2 패치] 취합 리포트 자동 초기화
                if 'summary_res' in st.session_state: del st.session_state.summary_res
                st.session_state.run_arena = True
                st.rerun()
    with col2:
        if st.button("🏛️ 원탁회의 시작", key="debate_main_btn"):
            if main_q.strip():
                st.session_state.run_debate = True
                st.rerun()

    st.divider()

    tabs = st.tabs(["📊 8-Arena (비교)", "🏛️ Debate (원탁회의)"])
    
    # --- [탭 1] 아레나 (v2.9.2 완전 복원) ---
    with tabs[0]:
        if st.session_state.get('run_arena', False):
            st.session_state.run_arena = False
            cols = st.columns(2)
            placeholders = [cols[i % 2].empty() for i in range(8)]
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(asyncio.gather(*(async_worker(i, list(PRIORITY_MAP.keys())[i], st.session_state.get(f"sel_{list(PRIORITY_MAP.keys())[i]}", PRIORITY_MAP[list(PRIORITY_MAP.keys())[i]][0]), main_q, placeholders) for i in range(8))))
            st.rerun()

        cols = st.columns(2)
        f_names = list(PRIORITY_MAP.keys())
        for i in range(8):
            with cols[i % 2]:
                st.markdown(f'''<div class="res-card"><span class="model-info">{i+1}. {f_names[i]}</span>{st.session_state.res_list[i] if st.session_state.res_list[i] else "..."}</div>''', unsafe_allow_html=True)
        
        # 아레나 전용 요약 버튼
        if any(st.session_state.res_list) and st.button("📝 전문가 교차 검증 요약"):
            valid_ans = "".join([f"[{f_names[i]}]: {st.session_state.res_list[i]}\n\n" for i in range(8) if st.session_state.res_list[i] and "⚠️" not in st.session_state.res_list[i]])
            st.session_state.summary_res = sync_api_call("Claude", st.session_state.get("sel_Claude", "anthropic/claude-3.5-sonnet"), f"요약 및 분석:\n\n{valid_ans}")
            st.rerun()

        if 'summary_res' in st.session_state:
            st.markdown(f'<div class="summary-box"><h4>💡 종합 분석 리포트</h4>{st.session_state.summary_res}</div>', unsafe_allow_html=True)

    # --- [탭 2] 원탁회의 (새로운 기능) ---
    with tabs[1]:
        if st.session_state.get('run_debate', False):
            st.session_state.run_debate = False
            with st.status("전문가 토론 진행 중...", expanded=True) as status:
                d1 = sync_api_call("Gemini", st.session_state.get("sel_Gemini", VALID_GEMINI[0]), f"상세 답변: {main_q}")
                d2 = sync_api_call("Claude", st.session_state.get("sel_Claude", "anthropic/claude-3.5-sonnet"), f"비판: {d1}")
                d3 = sync_api_call("GPT", st.session_state.get("sel_GPT", "openai/gpt-4o"), f"최종안 작성. 초안:{d1}, 비평:{d2}")
                st.session_state.debate_final = d3
                st.session_state.debate_history = [{"role": "assistant", "content": d3}]
                status.update(label="✅ 토론 완료!", state="complete")
            st.rerun()

        if 'debate_final' in st.session_state:
            for msg in st.session_state.debate_history:
                st.markdown(f'<div class="summary-box">{"<b>🏆 최종안</b>" if msg == st.session_state.debate_history[0] else "<b>💬 추가답변</b>"}<br>{msg["content"]}</div>', unsafe_allow_html=True)
            
            st.write("")
            follow_up = st.text_input("💡 추가 질문", key="f_input_debate")
            if st.button("전송", key="f_btn_debate"):
                if follow_up.strip():
                    with st.spinner("생성 중..."):
                        context = f"이전 답변: {st.session_state.debate_history[-1]['content']}\n\n질문: {follow_up}"
                        ans = sync_api_call("GPT", st.session_state.get("sel_GPT", "openai/gpt-4o"), context)
                        st.session_state.debate_history.append({"role": "user", "content": follow_up})
                        st.session_state.debate_history.append({"role": "assistant", "content": ans})
                        st.rerun()

    # [v2.9.2 핵심] 하단 설정
    with st.expander("⚙️ 모델 우선순위 설정"):
        for fam, cfg in PRIORITY_MAP.items():
            st.selectbox(f"{fam}", cfg, key=f"sel_{fam}")

if __name__ == "__main__":
    main()
