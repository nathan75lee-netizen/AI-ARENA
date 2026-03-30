import streamlit as st
import requests
import os
import time

# [v22.0] 429(재시도) & 400(규격교정) 최종 병기
def get_key(name):
    if name in st.secrets: return st.secrets[name]
    if os.path.exists("api_key.txt"):
        with open("api_key.txt", "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    if k.strip().upper() == name: return v.strip()
    return None

G_KEY = get_key("GEMINI_KEY")
Q_KEY = get_key("GROQ_KEY")

def call_with_retry(engine, m_id, prompt, role, max_retries=3):
    """429 에러 발생 시 지수 백오프 재시도 로직"""
    headers = {"Content-Type": "application/json"}
    for attempt in range(max_retries):
        try:
            if engine == "G":
                # 400/404 방지: ID 정규화
                clean_id = m_id.split('/')[-1]
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_id}:generateContent?key={G_KEY}"
                payload = {"contents": [{"parts": [{"text": f"당신은 {role}입니다. 주제: {prompt}"}]}]}
                r = requests.post(url, json=payload, timeout=30)
            else:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers["Authorization"] = f"Bearer {Q_KEY}"
                # 400 방지: 가장 안전한 메시지 구조 (System 메시지 제거 후 합침)
                payload = {
                    "model": m_id,
                    "messages": [{"role": "user", "content": f"시스템 지시: 당신은 {role}입니다.\n\n사용자 요청: {prompt}"}],
                    "temperature": 0.2 # 안정성 우선
                }
                r = requests.post(url, json=payload, headers=headers, timeout=30)

            if r.status_code == 200:
                if engine == "G": return r.json()['candidates'][0]['content']['parts'][0]['text'], "Success"
                return r.json()['choices'][0]['message']['content'], "Success"
            
            # 429 에러 시 대기 후 재시도
            if r.status_code == 429:
                wait_time = (attempt + 1) * 5 # 5초, 10초, 15초 대기
                st.warning(f"⚠️ {role} 엔진 과부하(429). {wait_time}초 후 다시 시도합니다... ({attempt+1}/{max_retries})")
                time.sleep(wait_time)
                continue
            
            return None, f"Status {r.status_code}: {r.reason}"
        except Exception as e:
            if attempt == max_retries - 1: return None, str(e)
            time.sleep(2)
    return None, "재시도 횟수 초과"

# UI
st.set_page_config(page_title="Arena v22.0", layout="wide")
st.title("🏛️ 아레나 v22.0 (자동 복구 시스템)")

with st.sidebar:
    st.info("💡 429 에러가 나면 자동으로 기다렸다가 다시 호출합니다.")
    st.write(f"G: {'✅' if G_KEY else '❌'} | Q: {'✅' if Q_KEY else '❌'}")

topic = st.text_input("토론 주제 입력")

if st.button("🚀 아레나 가동 (재시도 모드)") and topic:
    # 수동 배정 (스캔 없이도 작동하도록 가장 확률 높은 모델 직접 지정)
    experts = [
        ("G", "gemini-1.5-flash", "전략가"),
        ("Q", "llama-3.3-70b-versatile", "기술자"),
        ("Q", "mixtral-8x7b-32768", "리스크")
    ]
    
    cols = st.columns(3)
    for i, (eng, mid, role) in enumerate(experts):
        with cols[i]:
            ans, err = call_with_retry(eng, mid, topic, role)
            if ans:
                st.success(f"**{role}** 입정")
                st.write(ans)
            else:
                st.error(f"**{role} 최종 실패**\n\n{err}")
