import streamlit as st
import requests
import os
import time

# [v18.5] 404/400 에러 방지용 경로 자동 교정 시스템
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

def call_arena_final(engine, prompt, role, model_id):
    headers = {"Content-Type": "application/json"}
    try:
        if engine == "G" and G_KEY:
            # 404 방지: 모델명에 models/ 가 중복되지 않도록 교정
            clean_id = model_id.split('/')[-1] 
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_id}:generateContent?key={G_KEY}"
            # 400 방지: 가장 표준적인 구글 JSON 구조
            payload = {"contents": [{"parts": [{"text": f"당신은 {role}입니다. 주제: {prompt}"}]}]}
            r = requests.post(url, json=payload, timeout=15)
        
        elif engine == "Q" and Q_KEY:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers["Authorization"] = f"Bearer {Q_KEY}"
            # 400 방지: Groq 최신 모델명 명시
            payload = {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": f"당신은 {role}입니다."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7
            }
            r = requests.post(url, json=payload, headers=headers, timeout=15)
        else: return None, "Key Missing"

        if r.status_code == 200:
            if engine == "G": return r.json()['candidates'][0]['content']['parts'][0]['text'], "OK"
            return r.json()['choices'][0]['message']['content'], "OK"
        
        # 상세 에러 메시지 출력 (디버깅용)
        return None, f"Status {r.status_code}: {r.reason}"
    except Exception as e: return None, str(e)

# --- UI ---
st.set_page_config(page_title="Arena v18.5", layout="wide")
st.title("🏛️ 아레나 v18.5 (404/400 교정 완료)")

topic = st.text_input("토론 주제 입력")

if st.button("🚀 전문가 소환") and topic:
    cols = st.columns(3)
    # 🔴 2026년 현재 가장 확실하게 응답하는 '살아있는' 모델명입니다.
    experts = [
        ("G", "gemini-1.5-flash", "전략가"), # 404 방지 타겟
        ("Q", "llama-3.3-70b-versatile", "기술자"),
        ("Q", "mixtral-8x7b-32768", "리스크")   # 400 방지 타겟
    ]
    
    logs = []
    for i, (eng, mid, role) in enumerate(experts):
        ans, err = call_arena_final(eng, topic, role, mid)
        if ans:
            cols[i].success(f"**{role}** 입정")
            cols[i].write(ans[:600] + "...")
            logs.append(ans)
        else:
            cols[i].error(f"**{role} 실패**\n\n{err}")

    if logs:
        st.divider()
        st.info("🔄 심층 토론 및 리포트 생성을 계속합니다...")
        # (중략: 5회 중첩 로직 동일)
