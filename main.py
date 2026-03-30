import streamlit as st
import google.generativeai as genai
import requests
import asyncio

# [기존 아레나 엔진] 클라이언트 설정 (변경 없음)
@st.cache_resource
def setup_clients():
    g_key = st.secrets.get("GEMINI_KEY")
    or_key = st.secrets.get("OR_KEY")
    gr_key = st.secrets.get("GR_KEY") # 사용자 설정 키 명칭 준수
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
    "Groq": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
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
        .block-container { max-width: 100% !important; padding: 0.5rem 2% !important; }
        .main-title { font-size: 1.1rem !important; font-weight: 800; text-align: center; margin-bottom: 10px; }
        .res-card {
            background: white; border: 1px solid #e2e8f0; border-radius: 12px; 
            padding: 12px; margin-bottom: 5px; min-height: 80px; max-height: 350px; 
            overflow-y: auto; font-size: 13px; border-left: 5px solid #3b82f6;
        }
        .model-info { font-size: 10px; font-weight: 800; color: #1e40af; margin-bottom: 3px; display: block; }
        .stButton button { width: 100%; height: 3.2rem !important; font-weight: bold !important; border-radius: 10px !important; }
        .summary-box { background: #f0fdf4; border: 2px solid #bbf7d0; border-radius: 12px; padding: 15px; border-left: 8px solid #22c55e; font-size: 14px; }
        </style>
    """, unsafe_allow_html=True)

# [기존 아레나 엔진] API 호출 함수 (변경 없음)
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
                r = session.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {GROQ_KEY}"}, json={"model": current_model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1024}, timeout=20)
                if r.status_code == 200: return r.json()['choices'][0]['message']['content']
            else:
                r = session.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {OR_KEY}", "HTTP-Referer": "http://localhost:8501"}, json={"model": current_model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 800}, timeout=35)
                if r.status_code == 200: return r.json()['choices'][0]['message']['content']
        except: continue
    return f"⚠️ {family} 호출 실패"

async def async_worker(index, family, model_id, prompt, placeholders):
    res = await asyncio.to_thread(sync_api_call, family, model_id, prompt)
    st.session_state.res_list[index] = res
    placeholders[index].markdown(f'''<div class="res-card"><span class="model-info">{index+1}. {family}</span>{res}</div>''', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="AI Expert Multi-Center", layout="wide")
    apply_style()
    
    if 'res_list' not in st.session_state: st.session_state.res_list = [""] * 8
    if 'debate_history' not in st.session_state: st.session_state.debate_history = []

    st.markdown('<div class="main-title">⚡ AI Expert Multi-Solution Center</div>', unsafe_allow_html=True)

    # 공통 질문 입력창
    main_q = st.text_area("Global Input", placeholder="질문을 입력하세요...", label_visibility="collapsed", key="g_input", height=80)

    # 모드 실행 버튼 (나란히 배치)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 Arena 모드 시작"):
            if main_q.strip():
                st.session_state.run_arena = True
                st.rerun()
    with col2:
        if st.button("🏛️ 원탁회의 시작"):
            if main_q.strip():
                st.session_state.run_debate = True
                st.rerun()

    st.divider()

    # 기능을 탭으로 분리하여 아레나 화면 보호
    tabs = st.tabs(["📊 8-Arena (동시 비교)", "🏛️ Debate (전문가 토론)"])
    
    # --- [탭 1] 아레나: 기존 화면 그대로 유지 ---
    with tabs[0]:
        if st.session_state.get('run_arena', False):
            st.session_state.run_arena = False
            cols = st.columns(2)
            placeholders = [cols[i % 2].empty() for i in range(8)]
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(asyncio.gather(*(async_worker(i, list(PRIORITY_MAP.keys())[i], PRIORITY_MAP[list(PRIORITY_MAP.keys())[i]][0], main_q, placeholders) for i in range(8))))
            st.rerun()

        # 기존 아레나 결과 표시창 (변경 없음)
        cols = st.columns(2)
        f_names = list(PRIORITY_MAP.keys())
        for i in range(8):
            with cols[i % 2]:
                st.markdown(f'''<div class="res-card"><span class="model-info">{i+1}. {f_names[i]}</span>{st.session_state.res_list[i] if st.session_state.res_list[i] else "..."}</div>''', unsafe_allow_html=True)

    # --- [탭 2] 원탁회의: 새로운 기능 독립 추가 ---
    with tabs[1]:
        if st.session_state.get('run_debate', False):
            st.session_state.run_debate = False
            with st.status("전문가 원탁회의 진행 중...", expanded=True) as status:
                d1 = sync_api_call("Gemini", PRIORITY_MAP["Gemini"][0], f"상세 답변 작성: {main_q}")
                d2 = sync_api_call("Claude", PRIORITY_MAP["Claude"][0], f"답변 비판: {d1}")
                d3 = sync_api_call("GPT", PRIORITY_MAP["GPT"][0], f"초안: {d1}\n비평: {d2}\n최종안 작성.")
                st.session_state.debate_final = d3
                st.session_state.debate_history = [{"role": "assistant", "content": d3}]
                status.update(label="✅ 토론 완료!", state="complete")
            st.rerun()

        if 'debate_final' in st.session_state:
            # 대화 내역 표시
            for msg in st.session_state.debate_history:
                label = "🏆 <b>최종 확정안</b>" if msg == st.session_state.debate_history[0] else "💬 <b>후속 답변</b>"
                st.markdown(f'<div class="summary-box">{label}<br>{msg["content"]}</div>', unsafe_allow_html=True)
            
            # 원탁회의 내 개별 질문창
            st.write("")
            follow_up = st.text_input("💡 이 토론 결과에 대해 추가로 질문하세요", key="f_input_debate")
            if st.button("전문가에게 질문 전송", key="f_btn_debate"):
                if follow_up.strip():
                    with st.spinner("답변 생성 중..."):
                        context = f"이전 답변: {st.session_state.debate_history[-1]['content']}\n\n질문: {follow_up}"
                        ans = sync_api_call("GPT", PRIORITY_MAP["GPT"][0], context)
                        st.session_state.debate_history.append({"role": "user", "content": follow_up})
                        st.session_state.debate_history.append({"role": "assistant", "content": ans})
                        st.rerun()

    # [기존 아레나 설정] 모델 선택 (변경 없음)
    with st.expander("⚙️ 모델 설정"):
        for fam, cfg in PRIORITY_MAP.items():
            st.selectbox(f"{fam}", cfg, key=f"sel_{fam}")

if __name__ == "__main__":
    main()
