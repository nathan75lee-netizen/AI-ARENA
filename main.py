import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import time
import pandas as pd

# [v2.8.0] v2.5.5 기반 + 실시간 검색(Gemini) + 교차 검증 요약 + 다운로드 기능
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

MODEL_CONFIG = {
    "Gemini": VALID_GEMINI,
    "Groq": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
    "GPT": ["openai/gpt-4o-mini", "google/gemini-flash-1.5-8b:free"],
    "Claude": ["anthropic/claude-3-haiku:free", "anthropic/claude-3.5-sonnet:free"],
    "Llama": ["meta-llama/llama-3.3-70b-instruct:free", "meta-llama/llama-3.1-8b-instruct:free"],
    "Mistral": ["mistralai/mistral-7b-instruct-v0.1:free", "mistralai/pixtral-12b:free"],
    "DeepSeek": ["deepseek/deepseek-r1:free", "deepseek/deepseek-chat:free"],
    "Gemma": ["google/gemma-2-9b-it:free", "google/learnlm-1.5-pro-experimental:free"]
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
        .download-btn button { background-color: #64748b !important; height: 2.5rem !important; }
        </style>
    """, unsafe_allow_html=True)

def sync_api_call(family, model_id, prompt, use_search=False):
    if not prompt.strip(): return ""
    session = requests.Session()
    try:
        if family == "Gemini":
            # [기능 1] Gemini 실시간 구글 검색 도구 연동
            tools = "google_search" if use_search else None
            model = genai.GenerativeModel(model_name=model_id.split('/')[-1], tools=tools)
            return model.generate_content(prompt).text
        elif family == "Groq":
            r = session.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}"},
                json={"model": model_id, "messages": [{"role": "user", "content": prompt}], "max_tokens": 2048}, timeout=20)
            return r.json()['choices'][0]['message']['content']
        else:
            r = session.post("https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OR_KEY}", "HTTP-Referer": "http://localhost:8501"},
                json={"model": model_id, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1500}, timeout=45)
            data = r.json()
            return data['choices'][0]['message']['content'] if 'choices' in data else f"⚠️ {data.get('error', {}).get('message', '오류')}"
    except Exception as e:
        return f"⚠️ 연결 오류"

async def async_worker(index, family, model_id, prompt, placeholders, use_search=False):
    res = await asyncio.to_thread(sync_api_call, family, model_id, prompt, use_search)
    st.session_state.res_list[index] = res
    placeholders[index].markdown(f'''<div class="res-card"><span class="model-info">{index+1}. {family}</span>{res}</div>''', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="AI Expert 8-Arena v2.8", layout="wide")
    apply_style()
    
    f_names = list(MODEL_CONFIG.keys())
    num_models = len(f_names)

    if 'res_list' not in st.session_state: st.session_state.res_list = [""] * num_models
    if 'last_in' not in st.session_state: st.session_state.last_in = [""] * num_models

    st.markdown("<h2 style='text-align: center; margin-bottom:10px;'>⚡ AI Expert 8-Arena (검증 강화판)</h2>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.write("### ⚙️ 설정 및 도구")
        use_search = st.checkbox("🔍 Gemini 실시간 검색 사용", value=True)
        selected = {fam: st.selectbox(f"{fam}", cfg, key=f"sel_{fam}") for fam, cfg in MODEL_CONFIG.items()}
        st.divider()
        if any(st.session_state.res_list):
            # [기능 3] 리포트 다운로드 기능
            report_data = "\n\n".join([f"### {f_names[i]}\n{st.session_state.res_list[i]}" for i in range(8)])
            if 'summary_res' in st.session_state:
                report_data = f"## 종합 분석 보고서\n\n{st.session_state.summary_res}\n\n" + report_data
            st.download_button("📥 분석 리포트 다운로드 (.md)", data=report_data, file_name="ai_arena_report.md", use_container_width=True)

    main_q = st.text_area("Global Input", placeholder="검증이 필요한 질문을 입력하세요...", label_visibility="collapsed", key="g_input", height=100)
    
    if st.button("🔍 8개 AI 동시 검증 시작", use_container_width=True) and main_q.strip():
        cols = st.columns(2)
        placeholders = [cols[i % 2].empty() for i in range(num_models)]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tasks = [async_worker(i, f_names[i], selected[f_names[i]], main_q, placeholders, use_search if f_names[i]=="Gemini" else False) for i in range(num_models)]
        loop.run_until_complete(asyncio.gather(*tasks))
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

    # [기능 2] 교차 검증 요약 (Cross-Verification Summary)
    st.divider()
    if st.button("📝 8개 답변 교차 검증 및 최종 요약", use_container_width=True):
        combined = "".join([f"[{f_names[i]}]: {st.session_state.res_list[i]}\n\n" for i in range(8) if st.session_state.res_list[i]])
        if combined:
            with st.spinner("답변들 간의 일치 여부를 분석 중..."):
                # 교차 검증용 특화 프롬프트
                verify_prompt = (
                    "당신은 정보 검증 전문가입니다. 다음 8개 AI 답변을 바탕으로:\n"
                    "1. 모든 AI가 공통적으로 주장하는 '확실한 정보'를 추출하세요.\n"
                    "2. AI들 간에 서로 의견이 엇갈리는 '충돌 지점'을 명시하세요.\n"
                    "3. 실시간 검색 결과(Gemini 답변 참고)와 대조하여 최종 신뢰도를 평가하세요.\n"
                    f"답변 리스트:\n{combined}"
                )
                st.session_state.summary_res = sync_api_call("Claude", selected["Claude"], verify_prompt)
                st.rerun()

    if 'summary_res' in st.session_state:
        st.markdown(f'<div class="summary-box"><h4>💡 교차 분석 보고서</h4>{st.session_state.summary_res}</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
