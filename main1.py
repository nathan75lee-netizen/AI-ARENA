import streamlit as st
import requests
import os
import time

def get_key(name):
    if name in st.secrets: return st.secrets[name]
    if os.path.exists("api_key.txt"):
        try:
            with open("api_key.txt", "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        if k.strip().upper() == name: return v.strip()
        except: pass
    return None

G_KEY = get_key("GEMINI_KEY")
Q_KEY = get_key("GROQ_KEY")

def scan_clean_models():
    """숫자만 뱉는 모델을 제거하고 실제 답변 모델만 추출"""
    models = {"G": [], "Q": []}
    try:
        if G_KEY:
            r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={G_KEY}", timeout=5)
            if r.status_code == 200:
                # 'flash'나 'pro'가 포함된 실제 텍스트 모델만 선택
                models["G"] = [m['name'] for m in r.json().get('models', []) 
                             if any(x in m['name'].lower() for x in ['flash', 'pro']) and "vision" not in m['name']]
        if Q_KEY:
            r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {Q_KEY}"}, timeout=5)
            if r.status_code == 200:
                # 'guard', 'speculative', '8b' 미만 소형 모델 제외 (실제 답변용만)
                models["Q"] = [m['id'] for m in r.json().get('data', []) 
                             if not any(x in m['id'].lower() for x in ['guard', 'speculative', 'preview'])
                             and any(x in m['id'].lower() for x in ['llama', 'mixtral', '70b'])]
    except: pass
    return models

def call_text_only(eng, m_id, prompt, role, history=""):
    """텍스트 답변이 보장되는 호출"""
    full_p = f"당신은 {role}입니다. 한국어로 풍부하게 설명하세요.\n\n[맥락]\n{history}\n\n[질문]\n{prompt}"
    try:
        if eng == "G":
            url = f"https://generativelanguage.googleapis.com/v1beta/{m_id}:generateContent?key={G_KEY}"
            payload = {"contents": [{"parts": [{"text": full_p}]}]}
            r = requests.post(url, json=payload, timeout=30)
            if r.status_code == 200: return r.json()['candidates'][0]['content']['parts'][0]['text'], "Success"
        else:
            url = "https://api.groq.com/openai/v1/chat/completions"
            r = requests.post(url, headers={"Authorization": f"Bearer {Q_KEY}"}, 
                             json={"model": m_id, "messages": [{"role": "user", "content": full_p}], "temperature": 0.7}, timeout=30)
            if r.status_code == 200: return r.json()['choices'][0]['message']['content'], "Success"
        return None, f"Error {r.status_code}"
    except: return None, "Exception"

# --- UI ---
st.set_page_config(page_title="Arena v28.0", layout="wide")
st.title("🏛️ 아레나 v28.0 (텍스트 답변 정교화)")

if 'clean_pool' not in st.session_state:
    st.session_state.clean_pool = scan_clean_models()

topic = st.text_input("토론 주제", "필리핀 유망 사업 전략")

if st.button("🚀 전문가 소환 및 토론 시작") and topic:
    pool = st.session_state.clean_pool
    # 모델이 부족할 경우를 대비한 하드코딩 백업 (스캔 실패 시)
    if not pool["G"]: pool["G"] = ["models/gemini-1.5-flash"]
    if not pool["Q"]: pool["Q"] = ["llama-3.3-70b-versatile"]

    debate_history = ""
    
    # 1차 토론
    st.subheader("📢 1차: 전문가별 핵심 제안")
    cols = st.columns(3)
    roles = [("전략가", "G"), ("기술자", "Q"), ("리스크", "Q")]
    
    round1_results = []
    for i, (role, eng) in enumerate(roles):
        with cols[i]:
            m_id = pool[eng][0] if eng == "G" else pool[eng][i % len(pool[eng])]
            ans, _ = call_text_only(eng, m_id, "당신의 전문 분야에서 이 사업의 성공 가능성을 분석하세요.", role, "")
            if ans and len(ans) > 10: # 숫자가 아닌 실제 텍스트인지 확인
                st.success(f"**{role}**")
                st.write(ans)
                round1_results.append(f"{role}: {ans}")
                debate_history += f"[{role}]: {ans}\n"
            else:
                st.error(f"{role} 호출 실패 또는 무효한 답변")

    # 종합 리포트
    if round1_results:
        st.divider()
        st.subheader("📊 아레나 최종 종합 리포트")
        summary_id = pool["Q"][0] if pool["Q"] else pool["G"][0]
        summary_eng = "Q" if pool["Q"] else "G"
        
        with st.spinner("최종 전략 보고서 작성 중..."):
            time.sleep(3)
            final_report, _ = call_text_only(summary_eng, summary_id, 
                                           "위의 모든 전문가 의견을 종합하여, 필리핀 시장에서 즉시 실행 가능한 '필승 로드맵'을 작성하라.", 
                                           "수석 컨설턴트", debate_history)
            if final_report:
                st.markdown(final_report)
