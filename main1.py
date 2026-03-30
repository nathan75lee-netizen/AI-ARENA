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
    """가용 모델을 긁어오되, 실패를 대비해 하드코딩된 백업 리스트를 병합"""
    models = {"G": ["gemini-1.5-flash", "gemini-1.5-pro"], "Q": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]}
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

def universal_call(prompt, role, primary_engine, model_pool):
    """지정한 엔진이 실패하면 다른 엔진의 모델로 즉시 전환하여 답변 사수"""
    # 1차 시도: 기본 지정 엔진
    for m_id in model_pool[primary_engine][:3]:
        ans, err = execute_request(primary_engine, m_id, prompt, role)
        if ans: return ans, f"{primary_engine} ({m_id})"
        if "429" in err: time.sleep(10) # 429일 경우만 조금 더 대기

    # 2차 시도: 다른 엔진으로 교체 (Cross-Engine Failover)
    backup_engine = "Q" if primary_engine == "G" else "G"
    for m_id in model_pool[backup_engine][:2]:
        ans, err = execute_request(backup_engine, m_id, prompt, role)
        if ans: return ans, f"Backup: {backup_engine} ({m_id})"
    
    return None, "모든 엔진 및 모델 호출 실패"

def execute_request(eng, m_id, prompt, role):
    try:
        if eng == "G":
            url = f"https://generativelanguage.googleapis.com/v1beta/{m_id}:generateContent?key={G_KEY}"
            payload = {"contents": [{"parts": [{"text": f"Role: {role}\nTopic: {prompt}"}]}]}
            r = requests.post(url, json=payload, timeout=20)
        else:
            url = "https://api.groq.com/openai/v1/chat/completions"
            r = requests.post(url, headers={"Authorization": f"Bearer {Q_KEY}"}, json={"model": m_id, "messages": [{"role": "user", "content": f"As {role}, answer: {prompt}"}]}, timeout=20)
        
        if r.status_code == 200:
            if eng == "G": return r.json()['candidates'][0]['content']['parts'][0]['text'], "Success"
            return r.json()['choices'][0]['message']['content'], "Success"
        return None, str(r.status_code)
    except: return None, "Error"

# --- UI ---
st.set_page_config(page_title="Arena v26.0", layout="wide")
st.title("🏛️ 아레나 v26.0 (엔진 크로스 페일오버)")

if 'full_pool' not in st.session_state:
    st.session_state.full_pool = scan_all_engines()

with st.sidebar:
    if st.button("🔄 엔진 상태 새로고침"):
        st.session_state.full_pool = scan_all_engines()
        st.success("새로고침 완료")

topic = st.text_input("토론 주제")

if st.button("🚀 아레나 강제 가동") and topic:
    pool = st.session_state.full_pool
    experts = [("전략가", "G"), ("기술자", "Q"), ("리스크", "Q")]
    cols = st.columns(3)
    logs = []

    for i, (role, eng) in enumerate(experts):
        with cols[i]:
            with st.spinner(f"{role} 소환 시도 중..."):
                time.sleep(5) # 엔진 부하 방지용 강제 휴식
                ans, status = universal_call(topic, role, eng, pool)
                if ans:
                    st.success(f"**{role}** 입정")
                    st.caption(status)
                    st.write(ans[:800] + "...")
                    logs.append(ans)
                else:
                    st.error(f"**{role} 최종 실패**")
