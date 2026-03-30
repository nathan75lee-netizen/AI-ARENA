import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import time

# [v2.9.2] 클라이언트 설정 및 초기화
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
    if not valid_gemini: valid_gemini = ["gemini-2.0-flash", "gemini-1.5-pro"]
    return g_key, or_key, gr_key, valid_gemini

GEMINI_KEY, OR_KEY, GROQ_KEY, VALID_GEMINI = setup_clients()

# 서비스별 우선순위 (고성능 -> 무료 모델 순으로 자동 우회)
PRIORITY_MAP = {
    "Gemini": VALID_GEMINI,
    "Groq": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
    "GPT": ["openai/gpt-4o", "openai/gpt-4o-mini", "google/gemini-2.0-flash-001"],
    "Claude": ["anthropic/claude-3.5-sonnet", "anthropic/claude-3-haiku:free"],
    "Llama": ["meta-llama/llama-3.3-70b-instruct", "meta-llama/llama-3.3-70b-instruct:free", "meta-llama/llama-3.2-3b-instruct:free"],
    "DeepSeek": ["deepseek/deepseek-chat", "deepseek/deepseek-r1:free", "deepseek/deepseek-chat:free"],
    "Mistral": ["mistralai/pixtral-12b", "mistralai/mistral-nemo:free"],
    "Gemma": ["google/gemma-2-27b-it", "google/gemma-2-9b-it:free"]
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

# [수정 핵심] 3,4,5,6번 호출 실패를 방지하는 강화된 통신 엔진
def sync_api_call(family, model_id, prompt):
    if not prompt.strip(): return ""
    session = requests.Session()
    candidates = [model_id] + [m for m in PRIORITY_MAP.get(family, []) if m != model_id]
    
    for current_model in candidates:
        try:
            if family == "Gemini":
                model = genai.GenerativeModel(model_name=current_model.split('/')[-1])
                res = model.generate_content(prompt)
                if res and res.text:
                    tag = "" if current_model == model_id else f"\n\n*(자동우회: {current_model})*"
                    return res.text + tag
            elif family == "Groq":
                r = session.post("https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}"},
                    json={"model": current_model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1024}, timeout=25)
                if r.status_code == 200:
                    tag = "" if current_model == model_id else f"\n\n*(자동우회: {current_model})*"
                    return r.json()['choices'][0]['message']['content'] + tag
            else: # [여기서 3,4,5,6번 처리] OpenRouter 호출부 정밀 수정
                r = session.post("https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OR_KEY}",
                        "HTTP-Referer": "https://streamlit.io", # 리퍼러 정상화
                        "X-Title": "AI Expert Arena"
                    },
                    json={
                        "model": current_model, 
                        "messages": [{"role": "user", "content": prompt}],
                        "route": "fallback" # 유료 실패 시 자동 우회
                    }, timeout=60) # 타임아웃 60초로 연장
                
                if r.status_code == 200:
                    res = r.json()
                    tag = "" if current_model == model_id else f"\n\n*(자동우회: {current_model})*"
                    return res['choices'][0]['message']['content'] + tag
                
                # 402(잔액부족), 429(속도제한) 등 발생 시 다음 후보(무료모델)로 계속 시도
                continue 
        except Exception:
            continue
    return f"⚠️ {family}: 모든 후보 모델 호출 실패"

async def async_worker(index, family, model_id, prompt, placeholders):
    res = await asyncio.to_thread(sync_api_call, family, model_id, prompt)
    st.session_state.res_list[index] = res
    placeholders[index].markdown(f'''<div class="res-card"><span class="model-info">{index+1}. {family} • {model_id.split("/")[-1]}</span>{res}</div>''', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="AI Expert 8-Arena", layout="wide")
    apply_style()
    f_names = list(PRIORITY_MAP.keys())
    num_models = len(f_names)

    if 'res_list' not in st.session_state: st.session_state.res_list = [""] * num_models
    if 'last_in' not in st.session_state: st.session_state.last_in = [""] * num_models

    st.markdown("<h2 style='text-align: center;'>⚡ AI Expert 8-Arena (v2.9.2-Rev)</h2>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.write("### ⚙️ 모델 설정")
        selected = {fam: st.selectbox(f"{fam}", cfg, key=f"sel_{fam}") for fam, cfg in PRIORITY_MAP.items()}
        st.divider()
        if any(st.session_state.res_list):
            report_text = "## AI Arena 분석 리포트\n\n"
            for i in range(num_models): report_text += f"#### {f_names[i]}\n{st.session_state.res_list[i]}\n\n"
            st.download_button("📥 결과 다운로드 (.md)", data=report_text, file_name="arena_report.md", use_container_width=True)

    main_q = st.text_area("Global Input", placeholder="고성능 모델부터 순차적으로 시도합니다...", label_visibility="collapsed", key="g_input", height=100)
    
    if st.button("🔍 모든 AI 답변 동시 시작", use_container_width=True) and main_q.strip():
        if 'summary_res' in st.session_state:
            del st.session_state.summary_res
        
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
            st.markdown(f'''<div class="res-card"><span class="model-info">{i+1}. {fam} • {selected[fam].split("/")[-1]}</span>{st.session_state.res_list[i] if st.session_state.res_list[i] else "..."}</div>''', unsafe_allow_html=True)
            ind_q = st.text_input(f"q_{i}", key=f"ind_{i}", placeholder=f"{fam} 전용 질문", label_visibility="collapsed")
            if ind_q.strip() and ind_q != st.session_state.last_in[i]:
                st.session_state.last_in[i] = ind_q
                st.session_state.res_list[i] = sync_api_call(fam, selected[fam], ind_q)
                st.rerun()

    st.divider()
    if st.button("📝 모든 답변 교차 검증 및 전문가 요약", use_container_width=True):
        valid_ans = "".join([f"[{f_names[i]}]: {st.session_state.res_list[i]}\n\n" for i in range(num_models) if st.session_state.res_list[i] and "⚠️" not in st.session_state.res_list[i]])
        if valid_ans:
            with st.spinner("정보의 일관성을 정밀 분석 중..."):
                v_prompt = f"다음 답변들을 종합해서 결론 도출해줘:\n\n{valid_ans}"
                st.session_state.summary_res = sync_api_call("Gemini", selected["Gemini"], v_prompt)
                st.rerun()

    if 'summary_res' in st.session_state:
        st.markdown(f'<div class="summary-box"><h4>💡 종합 분석 리포트</h4>{st.session_state.summary_res}</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
