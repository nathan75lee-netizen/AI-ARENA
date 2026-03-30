import streamlit as st
import requests
import os
import time

# [v23.1] NameError 수정 및 404/400 에러 최종 대응 규격
def get_key(name):
    """배포 환경(Secrets) 및 로컬(api_key.txt) 통합 키 로드"""
    if name in st.secrets: 
        return st.secrets[name]
    if os.path.exists("api_key.txt"):
        try:
            with open("api_key.txt", "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        if k.strip().upper() == name: return v.strip()
        except: pass
    return None

# 키 로드 (함수명 get_key로 통일 완료)
G_KEY = get_key("GEMINI_KEY")
Q_KEY = get_key("GROQ_KEY")

def call_final_bridge(engine, m_id, prompt, role):
    """엔진별 최신 API 규격 강제 매칭"""
    headers = {"Content-Type": "application/json"}
    try:
        if engine == "G" and G_KEY:
            # 404 방지: 모델명에서 모든 경로를 제거하고 순수 ID만 추출
            pure_id = m_id.split('/')[-1] 
            # 2026년 Gemini API 표준 엔드포인트
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{pure_id}:generateContent?key={G_KEY}"
            
            payload = {
                "contents": [{
                    "parts": [{"text": f"당신은 {role}입니다. 다음 질문에 전문적으로 답하세요: {prompt}"}]
                }]
            }
            r = requests.post(url, json=payload, timeout=30)
            
        elif engine == "Q" and Q_KEY:
            # 400 방지: Groq 최신 규격 (System 역할 통합)
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers["Authorization"] = f"Bearer {Q_KEY}"
            
            payload = {
                "model": m_id,
                "messages": [
                    {"role": "user", "content": f"지시: 당신은 {role} 전문가입니다.\n질문: {prompt}"}
                ],
                "temperature": 0.3
            }
            r = requests.post(url, json=payload, headers=headers, timeout=30)
        else:
            return None, "API Key Missing"

        if r.status_code == 200:
            res = r.json()
            if engine == "G":
                return res['candidates'][0]['content']['parts'][0]['text'], "Success"
            return res['choices'][0]['message']['content'], "Success"
        
        # 상세 에러 원인 반환
        return None, f"Status {r.status_code}: {r.text[:150]}"
        
    except Exception as e:
        return None, str(e)

# --- Streamlit UI ---
st.set_page_config(page_title="Arena v23.1", layout="wide")
st.title("🏛️ 아레나 v23.1 (최종 안정화 버전)")

# 모델 설정 (가장 검증된 리스트)
target_models = [
    ("G", "gemini-1.5-flash", "전략가"),
    ("Q", "llama-3.3-70b-versatile", "기술자"),
    ("Q", "mixtral-8x7b-32768", "리스크")
]

topic = st.text_input("토론 주제를 입력하세요", placeholder="예: 미래 AI 산업의 핵심 전략은?")

if st.button("🚀 전문가 소환 시작") and topic:
    cols = st.columns(3)
    
    logs = []
    for i, (eng, mid, role) in enumerate(target_models):
        with cols[i]:
            with st.spinner(f"{role} 소환 중..."):
                # 429 에러 방지용 순차 대기
                if i > 0: time.sleep(2)
                ans, err = call_final_bridge(eng, mid, topic, role)
                if ans:
                    st.success(f"**{role}** 입정")
                    st.info(f"모델: {mid}")
                    st.write(ans)
                    logs.append(f"[{role}]: {ans}")
                else:
                    st.error(f"**{role} 호출 실패**")
                    st.code(err) # 에러 메시지 상세 출력

    if logs:
        st.divider()
        st.subheader("📝 종합 리포트")
        summary_prompt = "위 전문가들의 의견을 종합하여 결론을 도출하라: " + " ".join(logs)
        final_ans, _ = call_final_bridge("Q", "llama-3.3-70b-versatile", summary_prompt, "서기")
        if final_ans:
            st.markdown(final_ans)
