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

def scan_all_engines():
    models = {"G": ["gemini-1.5-flash"], "Q": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]}
    try:
        if G_KEY:
            r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={G_KEY}", timeout=5)
            if r.status_code == 200:
                models["G"] = [m['name'] for m in r.json().get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', []) and "vision" not in m['name']]
        if Q_KEY:
            r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {Q_KEY}"}, timeout=5)
            if r.status_code == 200:
                models["Q"] = [m['id'] for m in r.json().get('data', []) if "guard" not in m['id'].lower()]
    except: pass
    return models

def execute_call(eng, m_id, prompt, role, context=""):
    """맥락(context)을 포함하여 호출"""
    full_prompt = f"당신은 {role}입니다.\n\n[이전 토론 내용]\n{context}\n\n[현재 지시]\n{prompt}"
    try:
        if eng == "G":
            url = f"https://generativelanguage.googleapis.com/v1beta/{m_id}:generateContent?key={G_KEY}"
            payload = {"contents": [{"parts": [{"text": full_prompt}]}]}
            r = requests.post(url, json=payload, timeout=25)
            if r.status_code == 200: return r.json()['candidates'][0]['content']['parts'][0]['text'], "Success"
        else:
            url = "https://api.groq.com/openai/v1/chat/completions"
            r = requests.post(url, headers={"Authorization": f"Bearer {Q_KEY}"}, 
                             json={"model": m_id, "messages": [{"role": "user", "content": full_prompt}]}, timeout=25)
            if r.status_code == 200: return r.json()['choices'][0]['message']['content'], "Success"
        return None, str(r.status_code)
    except: return None, "Error"

def safe_relay_call(role, prompt, primary_eng, pool, context=""):
    """실패 시 엔진을 바꿔서라도 답변을 받아냄"""
    engines = [primary_eng, "Q" if primary_eng == "G" else "G"]
    for eng in engines:
        for m_id in pool[eng][:3]:
            ans, status = execute_call(eng, m_id, prompt, role, context)
            if ans: return ans, f"{eng}({m_id})"
            if "429" in status: time.sleep(8)
    return None, "All Failed"

# --- UI ---
st.set_page_config(page_title="Arena v27.0", layout="wide")
st.title("🏛️ 아레나 v27.0 (3차 심화 토론 & 리포트)")

if 'pool' not in st.session_state:
    st.session_state.pool = scan_all_engines()

topic = st.text_input("토론 주제", placeholder="예: 필리핀 유망 사업 전략")

if st.button("🚀 무제한 끝장 토론 시작") and topic:
    pool = st.session_state.pool
    debate_history = f"주제: {topic}\n"
    
    # 1차 토론: 기본 입장
    st.subheader("Stage 1: 각 분야 전문가 기조 연설")
    cols1 = st.columns(3)
    roles = [("전략가", "G"), ("기술자", "Q"), ("리스크", "Q")]
    
    round1_logs = []
    for i, (role, eng) in enumerate(roles):
        with cols1[i]:
            ans, status = safe_relay_call(role, "이 주제에 대한 당신의 핵심 견해를 밝히십시오.", eng, pool, "")
            if ans:
                st.success(f"**{role}**")
                st.write(ans)
                round1_logs.append(f"[{role}]: {ans}")
                debate_history += f"[{role} 1차]: {ans}\n"
            else: st.error(f"{role} 소환 실패")

    # 2차 토론: 반박 및 심화
    if round1_logs:
        st.divider()
        st.subheader("Stage 2: 상호 반박 및 심화 토론")
        cols2 = st.columns(3)
        for i, (role, eng) in enumerate(roles):
            with cols2[i]:
                with st.spinner(f"{role} 반박 준비 중..."):
                    time.sleep(5)
                    ans, status = safe_relay_call(role, "다른 전문가들의 의견을 비판적으로 검토하고 보완책을 제시하십시오.", eng, pool, debate_history)
                    if ans:
                        st.info(f"**{role}의 반격**")
                        st.write(ans)
                        debate_history += f"[{role} 2차]: {ans}\n"

        # 최종 리포트 (서기)
        st.divider()
        st.subheader("📊 아레나 최종 종합 리포트")
        with st.spinner("모든 토론을 요약 중..."):
            summary, _ = safe_relay_call("서기", "지금까지의 모든 토론 내용을 바탕으로 실행 가능한 최종 결론과 로드맵을 작성하라.", "Q", pool, debate_history)
            if summary:
                st.markdown(f"### 📋 최종 실행 전략\n{summary}")
            else:
                st.error("리포트 작성에 실패했습니다.")
