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

def call_gemini_safe(m_id, prompt, role):
    """404 에러 방지를 위한 2단계 경로 테스트"""
    pure_id = m_id.split('/')[-1]
    # 시도 1: v1beta 표준 경로
    urls = [
        f"https://generativelanguage.googleapis.com/v1beta/models/{pure_id}:generateContent?key={G_KEY}",
        f"https://generativelanguage.googleapis.com/v1/models/{pure_id}:generateContent?key={G_KEY}"
    ]
    
    last_err = ""
    for url in urls:
        try:
            payload = {"contents": [{"parts": [{"text": f"당신은 {role}입니다. 질문: {prompt}"}]}]}
            r = requests.post(url, json=payload, timeout=30)
            if r.status_code == 200:
                return r.json()['candidates'][0]['content']['parts'][0]['text'], "Success"
            last_err = f"Status {r.status_code}: {r.text[:100]}"
        except Exception as e:
            last_err = str(e)
    return None, last_err

def call_groq_safe(m_id, prompt, role):
    """400 에러 방지를 위한 모델명 정규화"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {Q_KEY}", "Content-Type": "application/json"}
    
    # 400 에러가 났던 모델명들을 최신 명칭으로 강제 치환
    if "mixtral" in m_id.lower():
        m_id = "mixtral-8x7b-32768"
    elif "llama" in m_id.lower():
        m_id = "llama-3.3-70b-versatile"

    try:
        payload = {
            "model": m_id,
            "messages": [{"role": "user", "content": f"지시: 당신은 {role}입니다.\n질문: {prompt}"}],
            "temperature": 0.2
        }
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code == 200:
            return r.json()['choices'][0]['message']['content'], "Success"
        return None, f"Status {r.status_code}: {r.text[:100]}"
    except Exception as e:
        return None, str(e)

# --- UI ---
st.set_page_config(page_title="Arena v23.5", layout="wide")
st.title("🏛️ 아레나 v23.5 (에러 자동 우회 버전)")

# 전문가 설정
experts = [
    ("G", "gemini-1.5-flash", "전략가"),
    ("Q", "llama-3.3-70b-versatile", "기술자"),
    ("Q", "mixtral-8x7b-32768", "리스크")
]

topic = st.text_input("토론 주제")

if st.button("🚀 아레나 가동") and topic:
    cols = st.columns(3)
    logs = []
    
    for i, (eng, mid, role) in enumerate(experts):
        with cols[i]:
            time.sleep(2) # 429 방지
            if eng == "G":
                ans, err = call_gemini_safe(mid, topic, role)
            else:
                ans, err = call_groq_safe(mid, topic, role)
                
            if ans:
                st.success(f"**{role}** 입정")
                st.write(ans)
                logs.append(ans)
            else:
                st.error(f"**{role} 실패**")
                st.code(err)

    if logs:
        st.divider()
        st.subheader("📝 종합 결론")
        final, _ = call_groq_safe("llama-3.3-70b-versatile", f"요약하라: {' '.join(logs)}", "서기")
        st.write(final if final else "요약 실패")
