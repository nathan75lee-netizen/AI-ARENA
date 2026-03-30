import streamlit as st
import google.generativeai as genai
import requests
import asyncio
import time

# [v3.10.5] 클라이언트 설정
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
        .report-header { text-align: center; border-bottom: 3px double #334155; padding-bottom: 20px; margin-bottom: 30px; }
        .stButton button { width: 100%; border-radius: 12px !important; font-weight: bold !important; height: 3.5rem; transition: 0.3s; }
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
    return "⚠️ 엔진 오류 (할당량 확인 필요)"

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
    st.markdown("<p style='text-align: center; color: #64748b;'>8개 모델의 교차 검증을 통한 심층 리포트 생성기</p>", unsafe_allow_html=True)
    
    main_q = st.text_area("Global Input", placeholder="리포트 작성을 위한 질문을 입력하세요...", key="g_input", height=120)
    
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

    # --- [리포트 생성 섹션] ---
    if any(st.session_state.res_list):
        if st.button("📊 정식 심층 종합 리포트 발행"):
            with st.status("전문가 데이터 분석가가 리포트를 작성 중입니다...", expanded=True) as status:
                full_context = ""
                for i in range(num_models):
                    if st.session_state.res_list[i] and "⚠️" not in st.session_state.res_list[i]:
                        full_context += f"### [데이터 소스 {i+1}: {f_names[i]}]\n{st.session_state.res_list[i]}\n\n"
                
                if full_context:
                    report_prompt = f"""
                    당신은 수석 AI 전략가입니다. 제공된 8개 모델의 답변을 바탕으로 공식 **'AI 전문가 심층 종합 분석 리포트'**를 작성하세요.
                    
                    **[리포트 필수 구성 요소]**
                    1. **Executive Summary**: 전체 내용을 3줄 내외로 요약.
                    2. **Consensus (공통점)**: 모든 모델이 입을 모아 강조하는 핵심 사항들을 카테고리별로 정리.
                    3. **Gap Analysis (차이점/논쟁점)**: 모델마다 의견이 갈리는 부분, 수치적 차이, 혹은 특정 모델만 강조한 유니크한 통찰 분석.
                    4. **Critical Evaluation**: 어떤 답변이 가장 실무적이고 정확한지 근거와 함께 평가.
                    5. **Action Plan (결론 및 제언)**: 사용자가 이 정보를 바탕으로 바로 실행할 수 있는 구체적인 가이드라인.

                    * 주의: 답변은 매우 전문적이고 격조 있는 비즈니스 톤앤매너를 유지하세요. 마크다운 표(Table)를 사용하여 비교 데이터를 시각화하세요.
                    
                    **[원천 데이터]**
                    {full_context}
                    """
                    st.session_state.summary_res = persistent_call("Summary-Expert", "gemini-1.5-pro", report_prompt)
                    status.update(label="리포트 발행 완료!", state="complete", expanded=False)
                    st.rerun()

    # 리포트 출력 UI
    if st.session_state.summary_res:
        st.markdown(f"""
            <div class="report-container">
                <div class="report-header">
                    <h2 style='margin-bottom:5px;'>AI EXPERT ANALYSIS REPORT</h2>
                    <p style='color: #64748b; font-size: 14px;'>발행일: 2026-03-30 | 분석 엔진: Multi-Model Arena v3.10.5</p>
                </div>
                {st.session_state.summary_res}
                <div style='margin-top: 50px; text-align: center; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 20px;'>
                    본 리포트는 Gemini-1.5-Pro 및 Llama-3.3-70B 모델의 교차 분석을 통해 생성되었습니다.
                </div>
            </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
