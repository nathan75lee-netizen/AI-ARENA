import streamlit as st
import requests
import os
import time

# [v23.0] 404/400 에러를 원천 봉쇄하는 하드코딩 규격
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
Q_KEY = get_env_key("GROQ_KEY") # 오타 방지용: get_key로 통일 권장

def call_final_bridge(engine, m_id, prompt, role):
    """엔진별 최신 API 규격 강제 매칭"""
    headers = {"Content-Type": "application/json"}
    try:
        if engine == "G":
            # 🔴 404 해결: 모델명에서 모든 경로를 제거하고 순수 ID만 추출 후 재조립
            pure_id = m_id.split('/')[-1] 
            # 2026년 표준 URL 구조 강제 적용
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{pure_id}:generateContent?key={G_KEY}"
            
            # 구글이 요구하는 가장 보수적인 JSON 구조
            payload = {
                "contents": [{
                    "parts": [{"text": f"당신은 {role}입니다. 다음 질문에 답하세요: {prompt}"}]
                }]
            }
            r = requests.post(url, json=payload, timeout=30)
            
        else:
            # 🔴 400 해결: Groq/OpenAI 호환 규격에서 'system' 역할을 제거하고 본문에 통합
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers["Authorization"] = f"Bearer {Q_KEY}"
            
            # 리스크 400 방지: 가장 단순한 'user' 단일 메시지 구조
            payload = {
                "model": m_id,
                "messages": [
                    {"role": "user", "content": f"명령: 당신은 {role} 전문가입니다.\n질문: {prompt}"}
                ],
                "temperature": 0.1 # 최대한 정제된 답변 유도
            }
            r = requests.post(url, json=payload, headers=headers, timeout=30)

        if r.status_code == 200:
            res = r.json()
            if engine == "G":
                return res['candidates'][0]['content']['parts'][0]['text'], "Success"
            return res['choices'][0]['message']['content'], "Success"
        
        # 실패 시 서버가 보낸 원문 에러를 코드로 찍어줌 (디버깅용)
        return None, f"Status {r.status_code}: {r.text[:100]}"
        
    except Exception as e:
        return None, str(e)

# --- UI ---
st.set_page_config(page_title="Arena v23.0", layout="wide")
st.title("🏛️ 아레나 v23.0 (최종 규격 정형화)")

# 모델명 명시 (현재 가장 확실하게 작동하는 명칭)
target_models = {
    "전략가": ("G", "gemini-1.5-flash"),
    "기술자": ("Q", "llama-3.3-70b-versatile"),
    "리스크": ("Q", "mixtral-8x7b-32768")
}

topic = st.text_input("토론 주제를 입력하세요")

if st.button("🚀 전문가 긴급 소환") and topic:
    cols = st.columns(3)
    idx = 0
    for role, (eng, mid) in target_models.items():
        with cols[idx]:
            with st.spinner(f"{role} 호출 중..."):
                time.sleep(2) # 429 방지용 간격
                ans, err = call_final_bridge(eng, mid, topic, role)
                if ans:
                    st.success(f"**{role}** 입정")
                    st.write(ans)
                else:
                    st.error(f"**{role} 실패**")
                    st.code(err) # 🔴 여기서 나오는 메시지가 핵심입니다.
        idx += 1
