import streamlit as st
import requests
import os
import time

# [v20.0] 아레나 스타일: 실시간 모델 스캔 및 3인 자동 배정 시스템
def get_env_key(name):
    if name in st.secrets: return st.secrets[name]
    if os.path.exists("api_key.txt"):
        with open("api_key.txt", "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    if k.strip().upper() == name: return v.strip()
    return None

G_KEY = get_env_key("GEMINI_KEY")
Q_KEY = get_env_key("GROQ_KEY")

def fetch_all_models():
    """서버에서 현재 사용 가능한 모든 모델 ID를 가져옴 (404 방지)"""
    available = {"G": [], "Q": []}
    # Gemini 스캔
    if G_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={G_KEY}"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                available["G"] = [m['name'] for m in r.json().get('models', []) 
                                  if 'generateContent' in m.get('supportedGenerationMethods', []) 
                                  and "flash" in m['name'].lower()]
        except: pass
    # Groq 스캔
    if Q_KEY:
        try:
            url = "https://api.groq.com/openai/v1/models"
            r = requests.get(url, headers={"Authorization": f"Bearer {Q_KEY}"}, timeout=5)
            if r.status_code == 200:
                available["Q"] = [m['id'] for m in r.json().get('data', []) if "llama" in m['id'].lower()]
        except: pass
    return available

def call_arena_api(engine, m_id, prompt, role):
    """표준화된 호출 프로토콜 (400 방지)"""
    headers = {"Content-Type": "application/json"}
    try:
        if engine == "G":
            # Gemini는 모델 전체 경로(models/...)를 URL에 포함해야 함
            url = f"https://generativelanguage.googleapis.com/v1beta/{m_id}:generateContent?key={G_KEY}"
            payload = {"contents": [{"parts": [{"text": f"당신은 {role}입니다. 주제: {prompt}"}]}]}
            r = requests.post(url, json=payload, timeout=15)
        else:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers["Authorization"] = f"Bearer {Q_KEY}"
            payload = {
                "model": m_id,
                "messages": [{"role": "user", "content": f"당신은 {role}입니다. {prompt}"}]
            }
            r = requests.post(url, json=payload, headers=headers, timeout=15)

        if r.status_code == 200:
            if engine == "G": return r.json()['candidates'][0]['content']['parts'][0]['text'], "Success"
            return r.json()['choices'][0]['message']['content'], "Success"
        return None, f"Status {r.status_code}"
    except Exception as e: return None, str(e)

# UI 구성
st.set_page_config(page_title="Arena v20.0", layout="wide")
st.title("🏛️ 아레나 v20.0 (실시간 모델 동적 배정)")

# 사이드바: 모델 스캔
with st.sidebar:
    if st.button("🔍 가용 모델 실시간 스캔", type="primary"):
        res = fetch_all_models()
        st.session_state.g_models = res["G"]
        st.session_state.q_models = res["Q"]
        st.success(f"스캔 완료: G({len(res['G'])}) Q({len(res['Q'])})")

topic = st.text_input("토론 주제 입력")

if st.button("🚀 아레나 가동 (3인 소환)") and topic:
    g_pool = st.session_state.get('g_models', [])
    q_pool = st.session_state.get('q_models', [])

    if not g_pool or not q_pool:
        st.warning("먼저 왼쪽 [모델 스캔] 버튼을 눌러주세요.")
        st.stop()

    # 상위 3개 모델 자동 배정 (아레나 방식)
    # 1. 전략가(Gemini 상위), 2. 기술자(Groq 상위), 3. 리스크(Groq 차순위 혹은 Gemini 차순위)
    m1 = g_pool[0]
    m2 = q_pool[0]
    m3 = q_pool[1] if len(q_pool) > 1 else g_pool[1]

    cols = st.columns(3)
    experts = [(m1, "G", "전략가"), (m2, "Q", "기술자"), (m3, "Q" if m3 in q_pool else "G", "리스크")]
    
    logs = []
    for i, (mid, eng, role) in enumerate(experts):
        with cols[i]:
            time.sleep(1) # 429 에러 방지용 간격
            ans, err = call_arena_api(eng, mid, topic, role)
            if ans:
                st.success(f"**{role}** 입정\n({mid})")
                st.write(ans[:600] + "...")
                logs.append(ans)
            else:
                st.error(f"**{role} 실패**\n\n{err}")

    if logs:
        st.divider()
        st.subheader("📝 종합 리포트 생성 중...")
        report, _ = call_arena_api("Q", q_pool[0], f"다음 토론을 요약하라: {' '.join(logs)}", "서기")
        st.markdown(report if report else "리포트 작성 실패")
