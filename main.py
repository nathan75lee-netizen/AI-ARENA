import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import time

# [v3.10.6] 클라이언트 설정
@st.cache_resource
def setup_clients():
    return st.secrets.get("GEMINI_KEY"), st.secrets.get("GROQ_KEY")

GEMINI_KEY, GROQ_KEY = setup_clients()

# 모델 배치 (Gemini & Groq)
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
        .block-container { max-width: 100% !important; padding: 1rem 2% !important; background-color: #f1f5f9; }
        .res-card {
            background: white; border: 1px solid #e2e8f0; border-radius: 12px; 
            padding: 18px; margin-bottom: 8px; min-height: 150px; max-height: 500px; 
            overflow-y: auto; font-size: 13.5px; border-left: 6px solid #2563eb;
            box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1);
        }
        .model-info { font-size: 11px; font-weight: 900; color: #1e40af; margin-bottom: 8px; display: block; text-transform: uppercase; }
        .report-container {
            background: #ffffff; border: 1px solid #cbd5e1; border-radius: 20px; 
            padding: 40px; margin-top: 30px; line-height: 1.7; color: #1e293b;
            box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1);
        }
        /* 리포트 내 테이블 스타일 강화 */
        .report-container table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        .report-container th { background-color: #f8fafc; color: #1e3a8a; padding: 12px; border: 1px solid #e2e8f0; }
        .report-container td { padding: 12px; border: 1px solid #e2e8f0; font-size: 14px; }
        .stButton button { width: 100%; border-radius: 12px !important; font-weight: bold !important; height: 3.5rem; }
        </style>
    """, unsafe_allow_html=True)

def persistent_call(family, model_id, prompt):
    if not prompt.strip(): return ""
    candidates = ["gemini-1.5-pro", "llama-3.3-70b-versatile", "gemini-2.0-flash"] if "Summary" in family else PRIORITY_MAP.get(family, [model_id])
    for current_model in candidates:
        try:
            if "gemini" in current_model.lower():
                genai.configure(api_key=GEMINI_KEY)
                model = genai.GenerativeModel(model_name=current_model)
                res = model.generate_content(prompt)
                if res and res.text: return res.text
            else:
                r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}"},
                    json={"model": current_model, "messages": [{"role": "user", "content": prompt}]}, timeout=45)
                if r.status_code == 200: return r.json()['choices'][0]['message']['content']
        except: continue
    return "⚠️ 엔진 오류"

async def async_worker(index, family, model_id, prompt, placeholders):
    await asyncio.sleep(index * 1.5)
    res = await asyncio.to_thread(persistent_call, family, model_id, prompt)
    st.session_state.res_list[index] = res
    placeholders[index].markdown(f'''<div class="res-card"><span class="model-info">{index+1}. {family}</span>{res}</div>''', unsafe_allow_html=True)

def main():
    st.set_page_config(page_title="AI Expert 8-Arena", layout="wide")
    apply_style()
    f_names = list(PRIORITY_MAP.keys())
    num_models = len(f_names)

    if 'res_list' not in st.session_state: st.session_state.res_list = [""] * num_models
    if 'summary_res' not in st.session_state: st.session_state.summary_res = None

    st.markdown("<h1 style='text-align: center; color: #1e3a8a;'>⚡ AI Expert 8-Arena</h1>", unsafe_allow_html=True)
    
    main_q = st.text_area("Global Input", placeholder="분석 질문을 입력하세요...", key="g_input", height=100)
    
    if st.button("🔍 전 모델 분석 시작", type="primary") and main_q.strip():
        st.session_state.summary_res = None
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
            st.markdown(f'''<div class="res-card"><span class="model-info">{i+1}. {f_names[i]}</span>{st.session_state.res_list[i] if st.session_state.res_list[i] else "..."}</div>''', unsafe_allow_html=True)

    if any(st.session_state.res_list):
        if st.button("📊 모델명 포함 심층 리포트 발행"):
            with st.status("모델별 데이터를 대조하여 리포트를 구성 중입니다...", expanded=True) as status:
                full_context = ""
                for i in range(num_models):
                    if st.session_state.res_list[i] and "⚠️" not in st.session_state.res_list[i]:
                        full_context += f"### [Source: {f_names[i]} / Model: {PRIORITY_MAP[f_names[i]][0]}]\n{st.session_state.res_list[i]}\n\n"
                
                if full_context:
                    # [핵심] 비교표에 모델명을 넣도록 프롬프트 강화
                    report_prompt = f"""
                    당신은 수석 AI 전략 분석가입니다. 아래 8개 모델의 답변을 바탕으로 공식 리포트를 작성하세요.
                    
                    **[리포트 작성 지침]**
                    1. **Executive Summary**: 핵심 요약.
                    2. **Model Comparison Table (필수)**: 마크다운 표를 생성하세요. 
                       - 표의 열(Column)에 반드시 **'모델명(Model Name)'**을 명시하고, 각 모델이 제시한 핵심 답변 내용과 특징을 대조하세요.
                    3. **Gap Analysis**: 모델 간의 의견 차이가 가장 극명한 지점을 모델명을 언급하며 분석하세요.
                    4. **Strategic Recommendation**: 가장 신뢰도 높은 모델의 의견을 바탕으로 한 최종 제언.

                    * 모든 분석에서 '모델 A' 같은 익명 대신, 제공된 **실제 모델 이름**을 사용하세요.
                    
                    **[분석 데이터]**
                    {full_context}
                    """
                    st.session_state.summary_res = persistent_call("Summary-Expert", "gemini-1.5-pro", report_prompt)
                    status.update(label="리포트 발행 완료!", state="complete", expanded=False)
                    st.rerun()

    if st.session_state.summary_res:
        st.markdown(f'<div class="report-container">{st.session_state.summary_res}</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
