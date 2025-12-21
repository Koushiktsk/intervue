"""
WebInterviewAgent - bridge between Flask API and Gemini + Voice system
Runs as a backend for the browser UI (app.py + index.html/script.js).

Key points:
- Uses Windows SAPI for TTS, but wrapped in SafeSpeaker so COM is properly
  initialized per thread (fixes 'CoInitialize has not been called' error).
- Exposes exactly what app.py expects:
    - ROLES, EXPERIENCE_LEVELS
    - .speaker.Speak(text)
    - .recognizer (SpeechRecognition object)
    - .interview_data dict
    - generate_question(role_key, experience_key, question_num)
    - evaluate(question, answer, role_key)
    - final_feedback(responses)
"""
import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv
import google.generativeai as genai

try:
    import speech_recognition as sr
    import win32com.client
    import pythoncom
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False
    print("Voice libraries not available. Install:")
    print("  pip install SpeechRecognition pywin32 pyaudio")

load_dotenv()
GEMINI_API_KEY = "Enter_your_API"

if not GEMINI_API_KEY:
    print("You need to set environment variables GEMINI_API_KEY")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)

class SafeSpeaker:
    """
    Wrapper around SAPI.SpVoice that:
    - Calls pythoncom.CoInitialize() in the current thread
    - Lazily creates the COM voice object
    So it's safe to use inside Flask (threaded) without CoInitialize errors.
    """
    def __init__(self, rate: int = 3):
        self._voice = None
        self._rate = rate

    def _ensure_voice(self):
        if self._voice is None:
            # Initialize COM in this thread
            pythoncom.CoInitialize()
            self._voice = win32com.client.Dispatch("SAPI.SpVoice")
            self._voice.Rate = self._rate

    def Speak(self, text: str, async_mode: bool = False):
        """
        Speak text.
        - async_mode = False → wait until speaking is finished (blocking)
        - async_mode = True → fire and forget
        """
        try:
            self._ensure_voice()
            flag = 1 if async_mode else 0  # 1 = async, 0 = sync
            print(f"[SPEECH] Speaking: {text[:50]}...")
            self._voice.Speak(text, flag)
            print(f"[SPEECH] Success!")
        except Exception as e:
            print(f"[SPEECH ERROR] {e}")

    def stop(self):
        """Stop speaking immediately"""
        try:
            self._ensure_voice()
            # Flag 3 = SVSFPurgeBeforeSpeak (clears the queue and stops current speech)
            self._voice.Speak("", 3)
            print("[SPEECH] Stopped successfully")
        except Exception as e:
            print(f"[SPEECH STOP ERROR] {e}")

class WebInterviewAgent:
    """Interview Agent designed to work with the Flask web backend."""

    EXPERIENCE_LEVELS = {
        "1": {
            "name": "Fresher or Entry Level",
            "description": "0-2 years experience",
            "difficulty": "basic concepts, definitions, simple scenarios"
        },
        "2": {
            "name": "Mid-Level",
            "description": "2-5 years experience",
            "difficulty": "practical application, problem-solving, some design"
        },
        "3": {
            "name": "Senior",
            "description": "5+ years experience",
            "difficulty": "complex design, architecture, trade-offs, leadership"
        }
    }

    ROLES = {
        "1": {
            "name": "Software Engineer",
            "focus": "technical skills, problem-solving, coding concepts, system design, algorithms, data structures",
            "topics": [
                "data structures and algorithms",
                "system design and architecture",
                "databases (SQL and NoSQL)",
                "API design and REST principles",
                "code optimization and performance",
                "version control and Git",
                "debugging and troubleshooting",
                "object-oriented programming",
                "testing and quality assurance",
                "cloud computing and deployment"
            ]
        },
        "2": {
            "name": "Sales Representative",
            "focus": "communication, persuasion, customer handling, closing techniques",
            "topics": [
                "handling rejection and objections",
                "sales process and methodology",
                "building client relationships",
                "closing techniques",
                "pipeline management",
                "negotiation skills",
                "customer needs analysis",
                "sales metrics and KPIs",
                "competitive positioning",
                "account management"
            ]
        },
        "3": {
            "name": "Retail Associate",
            "focus": "customer service, problem-solving, teamwork, handling difficult situations",
            "topics": [
                "customer service excellence",
                "handling difficult customers",
                "teamwork and collaboration",
                "time management during busy periods",
                "upselling and cross-selling",
                "product knowledge",
                "conflict resolution",
                "store presentation and merchandising",
                "cash handling and transactions",
                "problem-solving on the spot"
            ]
        },
        "4": {
            "name": "Product Manager",
            "focus": "product strategy, stakeholder management, prioritization, metrics, technical understanding",
            "topics": [
                "product roadmap and prioritization",
                "stakeholder management",
                "product metrics and KPIs",
            "user research and validation",
                "working with engineering teams",
                "product launch strategy",
                "competitive analysis",
                "technical debt management",
                "feature scoping and trade-offs",
                "data-driven decision making"
            ]
        },
        "5": {
            "name": "Data Analyst",
            "focus": "analytical thinking, data interpretation, tools/technologies, business impact, SQL, statistics",
            "topics": [
                "SQL and database querying",
                "statistical analysis methods",
                "data cleaning and preparation",
                "data visualization techniques",
                "A/B testing and experimentation",
                "business intelligence tools",
                "communicating insights to stakeholders",
                "predictive modeling",
                "data quality and validation",
                "analytical problem-solving"
            ]
        }
    }

    def __init__(self):
        if not VOICE_AVAILABLE:
            raise RuntimeError(
                "Voice libraries not installed. Install SpeechRecognition, pywin32, pyaudio."
            )

        # Gemini model
        self.model = genai.GenerativeModel("gemini-2.5-flash-lite")

        # Mic / recognizer used by /api/record-answer
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 4000
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 2.0
        self.recognizer.phrase_time_limit = None

        # Safe speaker wrapper used by app.py via agent.speaker.Speak(...)
        self.speaker = SafeSpeaker(rate=2)  # Slower, more natural pace

        # State to track interview
        self.covered_topics: List[str] = []
        self.current_role_key: Optional[str] = None
        self.current_exp_key: Optional[str] = None
        self.candidate_name: str = ""

        self.interview_data = {
            "role": None,
            "experience_level": None,
            "responses": [],
            "start_time": datetime.now(),
            "end_time": None,
        }

    def _generate_interview_question(
            self,
            role_name: str,
            focus_areas: str,
            topics: List[str],
            question_num: int,
            previous_topics: List[str],
            experience_level: str,
            difficulty: str,
            asked_questions: List[str] = None
    ) -> str:
        """Internal: generate a dynamic interview question with Gemini."""

        if question_num == 1:
            return f"Tell me about yourself and your experience as a {role_name}."

        available_topics = [t for t in topics if t not in previous_topics]
        if not available_topics:
            available_topics = topics

        # Build context of previous topics to avoid repetition
        previous_context = ""
        if previous_topics:
            previous_context = f"\nPrevious topics covered: {', '.join(previous_topics)}\nAVOID repeating these topics. Choose a DIFFERENT topic from the available list."

        # Add context about previously asked questions
        asked_context = ""
        if asked_questions and len(asked_questions) > 1:
            recent_questions = asked_questions[-3:]  # Last 3 questions
            asked_context = f"\n\nPreviously asked questions:\n" + "\n".join([f"- {q}" for q in recent_questions])
            asked_context += "\n\nIMPORTANT: Generate a COMPLETELY DIFFERENT question. Do NOT ask similar or related questions. Choose a NEW topic and angle."

        prompt = f"""You are an experienced interviewer conducting a {role_name} interview for a {experience_level} candidate.

        Focus areas: {focus_areas}
        Available topics: {', '.join(available_topics[:5])}
        Experience level: {experience_level}
        Question difficulty: {difficulty}
        This is question #{question_num} of the interview.{previous_context}{asked_context}

        Generate ONE interview question that:
        1. Is appropriate for {experience_level} level ({difficulty})
        2. Is relevant to the {role_name} role
        3. Covers ONE of the available topics (pick a DIFFERENT one each time)
        4. Is clear, direct, and specific
        5. Would be asked in a real interview
        6. Is COMPLETELY UNIQUE - must be different from all previously asked questions
        7. Explores a NEW aspect or angle of the role

        CRITICAL: Ensure maximum diversity. Each question should feel fresh and cover different ground.

        Return ONLY the question, nothing else. Keep it natural and conversational."""

        try:
            response = self.model.generate_content(prompt)
            question = response.text.strip().strip('"').strip("'")
            return question
        except Exception as e:
            print(f"Error generating question: {e}")
            return f"Can you describe your experience with {available_topics[0] if available_topics else 'this role'}?"

    def generate_question(self, role_key: str, experience_key: str, question_num: int,
                          asked_questions: List[str] = None) -> str:

        # Remember current role/experience for later feedback
        self.current_role_key = role_key
        self.current_exp_key = experience_key

        role_info = self.ROLES.get(role_key, self.ROLES["1"])
        exp_info = self.EXPERIENCE_LEVELS.get(experience_key, self.EXPERIENCE_LEVELS["1"])

        self.interview_data["role"] = role_info["name"]
        self.interview_data["experience_level"] = exp_info["name"]

        # Track topics used
        if question_num > 1 and len(self.covered_topics) < len(role_info["topics"]):
            next_topic = role_info["topics"][(question_num - 2) % len(role_info["topics"])]
            if next_topic not in self.covered_topics:
                self.covered_topics.append(next_topic)

        question = self._generate_interview_question(
            role_info["name"],
            role_info["focus"],
            role_info["topics"],
            question_num,
            self.covered_topics,
            exp_info["name"],
            exp_info["difficulty"],
            asked_questions or []
        )

        return question

    # ---------- Evaluation ----------

    def evaluate(self, question: str, answer: str, role_key: str) -> Dict:

        role_info = self.ROLES.get(role_key, self.ROLES["1"])
        role_context = role_info["name"]

        prompt = f"""You are an expert interview coach evaluating a candidate's response for a {role_context} position.

Question: {question}
Answer: {answer}

Provide a brief evaluation in JSON format:
{{
        "strengths": ["strength1", "strength2"],
        "weaknesses": ["weakness1", "weakness2"],
        "score": 7,
        "suggestion": "one specific improvement tip"
}}

Score from 1-10. Be constructive but honest."""

        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"},
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"Evaluation error: {e}")
            return {
                "strengths": ["Provided an answer"],
                "weaknesses": ["Could not evaluate"],
                "score": 5,
                "suggestion": "Try to be more specific and structured in your response.",
            }
    # ---------- Conversational Response ----------

    def generate_conversational_response(self, answer: str, question_num: int, candidate_name: str = "") -> str:
        # You can mention name once, but don't force it
        name = candidate_name or self.candidate_name or ""
        name_instruction = (
            f"The candidate's name is {name}. You may use their name ONCE at the beginning if it feels natural, but avoid repeating it."
            if name else
            "You don't need to mention the candidate's name."
        )

        prompt = f"""You are a realistic but kind interview coach.

        The candidate just answered:
        \"\"\"{answer}\"\"\" 
        This is question #{question_num}.

        Your job:
        - Be honest but not harsh.
        - Always mix:
          - One short positive observation (what was good, even if small)
          - One short improvement point (what is missing or weak)
        - If the answer is very off-topic, say clearly that they are far from the expected answer, but still stay respectful.
        - DO NOT give a long paragraph.
        - DO NOT overpraise.
        - Format:
          - Reply in ONLY 1–2 sentences.
          - Keep the tone calm and practical.

        {str(name_instruction)}

        Examples of the tone:
        - "You had a nice starting point, but you stayed very high-level — try adding a concrete example next time."
        - "This is quite far from the expected answer; focus more on the core concept and give a specific scenario."
        - "You made a good attempt, but you didn't really address the main part of the question."

        Return ONLY your short feedback text, nothing else."""

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip().strip('"').strip("'")
        except Exception as e:
            print(f"Error generating conversational response: {e}")
            return "Good effort, but try to be more specific and closer to what the question is actually asking."

    # ---------- Final Feedback ----------

    def final_feedback_formatted(self, responses: List[Dict]) -> str:
        """
        Generate formatted final feedback (HTML-friendly, no markdown symbols)
        """
        if not responses:
            return "No responses were recorded."

        role_name = self.interview_data.get("role", "the selected role")

        responses_summary = "\n".join(
            [
                f"Q: {r['question']}\nA: {r['answer']}\nScore: {r['score']}/10"
                for r in responses
            ]
        )

        prompt = f"""You are an expert interview coach providing final feedback for a {role_name} interview.

Interview Summary:
{responses_summary}

Provide comprehensive feedback in PLAIN TEXT format (NO markdown, NO asterisks, NO special formatting):

1. Overall Performance (2-3 sentences)
2. Key Strengths (list 2-3 points, use simple dashes)
3. Areas for Improvement (list 2-3 specific points, use simple dashes)
4. Communication Style Assessment (1-2 sentences)
5. Final Recommendation (what to focus on for next interview)

Use simple formatting:
- Use line breaks for sections
- Use simple dashes (-) for lists
- NO asterisks, NO bold, NO markdown
- Be encouraging but honest"""

        try:
            response = self.model.generate_content(prompt)
            # Clean up any markdown that might slip through
            text = response.text
            text = text.replace('**', '')
            text = text.replace('*', '')
            text = text.replace('###', '')
            text = text.replace('##', '')
            text = text.replace('#', '')
            return text
        except Exception as e:
            return f"Error generating feedback: {e}"

