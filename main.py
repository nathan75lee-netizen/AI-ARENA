import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import time

# [v2.5.5 엔진 기반] 클라이언트 설정
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
    # Gemini 모델이 하나도 안 잡힐 경우를 대비한 기본값
    if not valid_gemini: valid_gemini = ["gemini-1.5-flash", "gemini-1.5-pro"]
    return g_key, or_key, gr_key, valid_gemini

GEMINI_KEY, OR_KEY, GROQ_KEY, VALID_GEMINI = setup_clients()

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
        .model-info { font-size: 11px; font-weight: 800; color: #1e40af; margin-bottom: 5px; display: block; }
        .stButton button { background-color: #3b82f6 !important; color: white !important; font-weight: bold !important; border-radius: 10px !important; height: 3.5rem; }
        .summary-box { background: #f0fdf4; border: 2px solid #bbf7d0; border-radius: 15px; padding: 20px; margin-top: 20px; border-left: 10px solid #22c55e; }
        </style>
    """, unsafe_allow_html=True)

# [핵심] 429 에러 및 Credits 부족 에러를 방어하는 정교한 연결부
def sync_api_call(family, model_id, prompt):
    if not prompt.strip(): return ""
    session = requests.Session()
    try:
        if family == "Gemini":
            # 429 에러 발생 시 최대 2번 재시도 (간격 5초)
            for i in range(2):
                try:
                    model = genai.GenerativeModel(model_name=model_id.split('/')[-1])
                    return model.generate_content(prompt).text
                except Exception as ge:
                    if "429" in str(ge):
                        time.sleep(5) # 할당량 회복을 위한 대기
                        continue
                    raise ge
        
        elif family == "Groq":
            r = session.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}"},
                json={"model": model_id, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1024}, timeout=20)
            res = r.json()
            return res['choices'][0]['message']['content'] if 'choices' in res else f"⚠️ Groq: {res.get('error', {}).get('message', 'Error')}"
            
        else: # OpenRouter 계열 (GPT, Claude 등)
            r = session.post("https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OR_KEY}", "HTTP-Referer": "http://localhost:8501"},
                json={
                    "model": model_id, 
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 800 # 잔액 부족 방지를 위해 토큰 요청값 하향 조정
                }, timeout=45)
            res = r.json()
            # [수정] 응답 객체에 choices가 없을 경우의 처리 강화
            if 'choices' in res:
                return res['choices'][0]['message']['content']
            else:
                err_msg = res.get('error', {}).get('message', 'Unknown Error')
                if "credits" in err_msg.lower():
                    return "⚠️ 크레딧 부족: OpenRouter 잔액을 확인하거나 무료(:free) 모델을 사용하세요."
                return f"⚠️ API 에러: {err_msg}"
            
    except Exception as e:
        return f"⚠️ 연결 지연: 인터넷 상태나 API 키를 확인하세요."

async def async_worker(index, family, model_id, prompt, placeholders):
    res = await asyncio.to_thread(sync_api_call, family, model_id, prompt)
    st.session_state.res_list[index] = res
    placeholders[index].markdown(f'''<div class="res-card"><span class="model-info">{index+1}. {family} • {model_id.split("/")[-1]}</span>{res}</div>''', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="AI Expert 8-Arena", layout="wide")
    apply_style()
    f_names = list(MODEL_CONFIG.keys())
    num_models = len(f_names)

    if 'res_list' not in st.session_state: st.session_state.res_list = [""] * num_models
    if 'last_in' not in st.session_state: st.session_state.last_in = [""] * num_models

    st.markdown("<h2 style='text-align: center;'>⚡ AI Expert 8-Arena</h2>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.write("### ⚙️ 모델 설정")
        selected = {fam: st.selectbox(f"{fam}", cfg, key=f"sel_{fam}") for fam, cfg in MODEL_CONFIG.items()}
        st.divider()
        if any(st.session_state.res_list):
            report_text = "## AI Arena 분석 리포트\n\n"
            for i in range(num_models): report_text += f"### {f_names[i]}\n{st.session_state.res_list[i]}\n\n"
            st.download_button("📥 결과 다운로드 (.md)", data=report_text, file_name="arena_report.md", use_container_width=True)

    main_q = st.text_area("Global Input", placeholder="여기에 질문을 입력하면 8개 AI가 동시에 답합니다.", label_visibility="collapsed", key="g_input", height=100)
    
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
            st.markdown(f'''<div class="res-card"><span class="model-info">{i+1}. {fam} • {selected[fam].split("/")[-1]}</span>{st.session_state.res_list[i] if st.session_state.res_list[i] else "..."}</div>''', unsafe_allow_html=True)
            ind_q = st.text_input(f"q_{i}", key=f"ind_{i}", placeholder=f"{fam} 전용 질문", label_visibility="collapsed")
            if ind_q.strip() and ind_q != st.session_state.last_in[i]:
                st.session_state.last_in[i] = ind_q
                st.session_state.res_list[i] = sync_api_call(fam, selected[fam], ind_q)
                st.rerun()

    # 교차 검증 요약 (v2.5.5 구조에 완전 통합)
    st.divider()
    if st.button("📝 모든 답변 교차 검증 및 취합 요약", use_container_width=True):
        valid_ans = [f"[{f_names[i]}]: {st.session_state.res_list[i]}" for i in range(num_models) if st.session_state.res_list[i] and "⚠️" not in st.session_state.res_list[i]]
        if valid_ans:
            with st.spinner("정보의 일관성을 분석 중..."):
                v_prompt = f"다음은 여러 전문가 AI의 답변들입니다. 팩트 중심의 공통점과 상충되는 지점을 정리하고 최종 결론을 도출해줘:\n\n" + "\n\n".join(valid_ans)
                st.session_state.summary_res = sync_api_call("Claude", selected["Claude"], v_prompt)
                st.rerun()

    if 'summary_res' in st.session_state:
        st.markdown(f'<div class="summary-box"><h4>💡 교차 검증 요약 리포트</h4>{st.session_state.summary_res}</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
