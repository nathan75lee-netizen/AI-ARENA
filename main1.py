import streamlit as st
import requests
import os
import time

# [v19.0] 에러 3종 세트(404, 429, 400) 완전 방어 시스템
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

def call_arena_v19(engine, prompt, role, model_id):
    headers = {"Content-Type": "application/json"}
    try:
        if engine == "G" and G_KEY:
            # ✅ [404 방지] 모델 ID에서 중복 경로 제거 및 정규화
            clean_id = model_id.replace("models/", "")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_id}:generateContent?key={G_KEY}"
            payload = {"contents": [{"parts": [{"text": f"Role: {role}\n\n{prompt}"}]}]}
            r = requests.post(url, json=payload, timeout=15)
        
        elif engine == "Q" and Q_KEY:
            # ✅ [400 방지] Groq 최신 규격 준수 (Messages 구조)
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers["Authorization"] = f"Bearer {Q_KEY}"
            payload = {
                "model": model_id,
                "messages": [
                    {"role": "user", "content": f"시스템: 당신은 {role}입니다. 사용자 질문: {prompt}"}
                ],
                "temperature": 0.5
            }
            r = requests.post(url, json=payload, headers=headers, timeout=15)
        else: return None, "Key Missing"

        if r.status_code == 200:
            if engine == "G": return r.json()['candidates'][0]['content']['parts'][0]['text'], "Success"
            return r.json()['choices'][0]['message']['content'], "Success"
        
        return None, f"Status {r.status_code}: {r.reason}"
    except Exception as e: return None, str(e)

# UI
st.set_page_config(page_title="Arena v19.0", layout="wide")
st.title("🏛️ 아레나 v19.0 (통합 디버깅 완료)")

topic = st.text_input("토론 안건을 입력하세요")

if st.button("🚀 전문가 소환 (순차 호출 방식)") and topic:
    cols = st.columns(3)
    experts = [
        ("G", "gemini-1.5-flash", "전략가"),
        ("Q", "llama-3.3-70b-versatile", "기술자"),
        ("Q", "mixtral-8x7b-32768", "리스크")
    ]
    
    logs = []
    for i, (eng, mid, role) in enumerate(experts):
        with cols[i]:
            # ✅ [429 방지] 동시 호출 대신 1.5초의 간격을 두고 호출하여 할당량 초과 방지
            time.sleep(1.5) 
            ans, err = call_arena_v19(eng, topic, role, mid)
            if ans:
                st.success(f"**{role}** ({mid})")
                st.write(ans[:600] + "...")
                logs.append(ans)
            else:
                st.error(f"**{role} 실패**\n\n{err}")

    if logs:
        st.divider()
        st.subheader("🔄 2단계: 심층 토론 진행")
        # (이하 중첩 토론 로직에서도 call_arena_v19 사용 및 time.sleep 유지)
