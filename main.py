import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import time

# [v2.5.5 연결부 완전 복구] 모델 리스트 및 설정 유지
@st.cache_resource
def setup_clients():
    g_key = st.secrets.get("GEMINI_KEY")
    or_key = st.secrets.get("OR_KEY")
    gr_key = st.secrets.get("GROQ_KEY")
    valid_gemini = []
    if g_key:
        try:
            genai.configure(api_key=g_key)
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    valid_gemini.append(m.name.replace("models/", ""))
        except: pass
    if not valid_gemini: valid_gemini = ["gemini-1.5-flash", "gemini-1.5-pro"]
    return g_key, or_key, gr_key, valid_gemini

GEMINI_KEY, OR_KEY, GROQ_KEY, VALID_GEMINI = setup_clients()

# v2.5.5에서 잘 작동하던 모델 라인업 그대로 고정
MODEL_CONFIG = {
    "Gemini": VALID_GEMINI,
    "Groq": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
    "GPT": ["openai/gpt-4o-mini", "openai/gpt-4o"],
    "Claude": ["anthropic/claude-3-haiku", "anthropic/claude-3.5-sonnet"],
    "Llama": ["meta-llama/llama-3.3-70b-instruct", "meta-llama/llama-3.2-3b-instruct:free"],
    "Mistral": ["mistralai/mistral-nemo", "mistralai/pixtral-12b"],
    "DeepSeek": ["deepseek/deepseek-r1:free", "deepseek/deepseek-chat"],
    "Gemma": ["google/gemma-2-9b-it", "google/gemma-2-27b-it"]
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
        .summary-box {
            background: #f0fdf4; border: 2px solid #bbf7d0; border-radius: 15px;
            padding: 20px; margin-top: 20px; border-left: 10px solid #22c55e;
        }
        .model-info { font-size: 11px; font-weight: 800; color: #1e40af; margin-bottom: 5px; display: block; }
        .stButton button { background-color: #3b82f6 !important; color: white !important; font-weight: bold !important; border-radius: 10px !important; height: 3.5rem; }
        </style>
    """, unsafe_allow_html=True)

# [v2.5.5 방식] API 호출 함수 (검색 옵션만 안전하게 추가)
def sync_api_call(family, model_id, prompt, use_search=False):
    if not prompt.strip(): return ""
    session = requests.Session()
    try:
        if family == "Gemini":
            # Gemini 실시간 검색 도구 (API 지원 시에만 작동하도록 안전 장치)
            tools = [{"google_search_retrieval": {}}] if use_search else None
            model = genai.GenerativeModel(model_name=model_id.split('/')[-1], tools=tools)
            return model.generate_content(prompt).text
        elif family == "Groq":
            r = session.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}"},
                json={"model": model_id, "messages": [{"role": "user", "content": prompt}]}, timeout=20)
            return r.json()['choices'][0]['message']['content']
        else:
            r = session.post("https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OR_KEY}", "HTTP-Referer": "http://localhost:8501"},
                json={"model": model_id, "messages": [{"role": "user", "content": prompt}]}, timeout=45)
            return r.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"⚠️ 에러: {str(e)[:40]}"

async def async_worker(index, family, model_id, prompt, placeholders, use_search=False):
    res = await asyncio.to_thread(sync_api_call, family, model_id, prompt, use_search)
    st.session_state.res_list[index] = res
    placeholders[index].markdown(f'''<div class="res-card"><span class="model-info">{index+1}. {family} • {model_id.split("/")[-1]}</span>{res}</div>''', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="AI Arena 8", layout="wide")
    apply_style()
    f_names = list(MODEL_CONFIG.keys())
    num_models = len(f_names)

    if 'res_list' not in st.session_state: st.session_state.res_list = [""] * num_models
    if 'last_in' not in st.session_state: st.session_state.last_in = [""] * num_models

    st.markdown("<h2 style='text-align: center;'>⚡ AI Expert 8-Arena</h2>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.write("### ⚙️ 설정 및 도구")
        use_search = st.checkbox("🔍 Gemini 실시간 검색 활성화", value=False)
        selected = {fam: st.selectbox(f"{fam}", cfg, key=f"sel_{fam}") for fam, cfg in MODEL_CONFIG.items()}
        st.divider()
        # [추가] 리포트 다운로드
        if any(st.session_state.res_list):
            report_text = f"## AI Arena 검증 리포트\n\n"
            if 'summary_res' in st.session_state: report_text += f"### 종합 분석\n{st.session_state.summary_res}\n\n"
            for i in range(num_models): report_text += f"#### {f_names[i]}\n{st.session_state.res_list[i]}\n\n"
            st.download_button("📥 리포트 다운로드 (.md)", data=report_text, file_name="arena_report.md", use_container_width=True)

    main_q = st.text_area("Global Input", placeholder="질문을 입력하세요...", label_visibility="collapsed", key="g_input", height=100)
    
    if st.button("🔍 모든 AI 답변 듣기", use_container_width=True) and main_q.strip():
        cols = st.columns(2)
        placeholders = [cols[i % 2].empty() for i in range(num_models)]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(asyncio.gather(*(async_worker(i, f_names[i], selected[f_names[i]], main_q, placeholders, use_search if f_names[i]=="Gemini" else False) for i in range(num_models))))
        st.rerun()

    st.divider()
    cols = st.columns(2)
    for i in range(num_models):
        fam = f_names[i]
        with cols[i % 2]:
            st.markdown(f'''<div class="res-card"><span class="model-info">{i+1}. {fam} • {selected[fam].split("/")[-1]}</span>{st.session_state.res_list[i] if st.session_state.res_list[i] else "..."}</div>''', unsafe_allow_html=True)
            ind_q = st.text_input(f"q_{i}", key=f"ind_{i}", placeholder=f"{fam} 개별 질문", label_visibility="collapsed")
            if ind_q.strip() and ind_q != st.session_state.last_in[i]:
                st.session_state.last_in[i] = ind_q
                st.session_state.res_list[i] = sync_api_call(fam, selected[fam], ind_q, use_search if fam=="Gemini" else False)
                st.rerun()

    # [추가] 교차 검증 요약 기능
    st.divider()
    if st.button("📝 모든 답변 교차 검증 및 최종 요약", use_container_width=True):
        combined = "".join([f"[{f_names[i]}]: {st.session_state.res_list[i]}\n\n" for i in range(num_models) if st.session_state.res_list[i]])
        if combined:
            with st.spinner("정보의 일관성을 검증 중..."):
                v_prompt = f"다음 8개 AI 답변을 대조하여, 공통된 팩트와 서로 충돌하는 지점을 나누어 전문가 수준으로 요약해줘:\n\n{combined}"
                st.session_state.summary_res = sync_api_call("Claude", selected["Claude"], v_prompt)
                st.rerun()

    if 'summary_res' in st.session_state:
        st.markdown(f'<div class="summary-box"><h4>💡 교차 분석 결과</h4>{st.session_state.summary_res}</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
