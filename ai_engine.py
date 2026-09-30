import json
import re
from typing import Dict, Any, List

class AIEngine:
    def __init__(self, gemini_api_key: str = None):
        self.gemini_api_key = gemini_api_key

    def set_api_key(self, api_key: str):
        self.gemini_api_key = api_key

    def generate_summary(self, transcript: str, title: str = "Training Program") -> Dict[str, Any]:
        """Generates a structured summary dictionary from the transcript."""
        if self.gemini_api_key and self.gemini_api_key.strip():
            try:
                summary = self._summary_with_gemini(transcript, title)
                if summary:
                    return summary
            except Exception as e:
                print(f"Gemini summary error: {e}. Using intelligent fallback.")

        return self._summary_fallback(transcript, title)

    def _summary_with_gemini(self, transcript: str, title: str) -> Dict[str, Any]:
        """Generates structured JSON summary using Google Gemini API."""
        import google.generativeai as genai
        genai.configure(api_key=self.gemini_api_key.strip())
        
        prompt = f"""
You are an expert AI Training Summarizer and Executive Notes Generator.
Analyze the following transcript of a training session / meeting titled "{title}":

TRANSCRIPT:
{transcript}

Please output ONLY a valid JSON object with the following exact keys and structure:
{{
  "executive_summary": "A concise 2-3 sentence high level summary of the overall session.",
  "topics": [
    {{
      "timestamp": "[00:15]",
      "topic": "Topic Name",
      "details": "Clear 2-sentence summary of what was covered here."
    }}
  ],
  "key_takeaways": [
    "Important takeaway bullet point 1",
    "Important takeaway bullet point 2",
    "Important takeaway bullet point 3"
  ],
  "action_items": [
    "Actionable task or assignment 1",
    "Actionable task or assignment 2"
  ],
  "qna_highlights": [
    {{
      "question": "Question asked during training",
      "answer": "Answer provided in the session"
    }}
  ]
}}
Do not wrap in markdown ```json blocks if possible, return raw JSON string.
"""
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Remove potential markdown fences
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        return json.loads(text)

    def _summary_fallback(self, transcript: str, title: str) -> Dict[str, Any]:
        """Local rule-based NLP summary generator when offline or no API key."""
        lines = [line.strip() for line in transcript.split("\n") if line.strip()]
        
        topics = []
        takeaways = []
        action_items = []
        
        for line in lines:
            # Extract timestamp
            match = re.match(r"\[(\d{2}:\d{2}(?::\d{2})?)\]\s*(.*)", line)
            if match:
                ts, text = match.group(1), match.group(2)
                if len(text) > 5:
                    topic_title = text.split(".")[0][:60]
                    topics.append({
                        "timestamp": f"[{ts}]",
                        "topic": topic_title,
                        "details": text
                    })
                    if len(takeaways) < 5:
                        takeaways.append(text)
            else:
                if len(line) > 10 and len(takeaways) < 5:
                    takeaways.append(line)
                    
        if not takeaways:
            takeaways = [
                "Comprehensive screen and audio recording captured successfully.",
                "Review the timestamped transcript for detailed conversation analysis.",
                "Use the AI Q&A Assistant to ask specific questions about session content."
            ]

        action_items = [
            "Review session key takeaways and complete assigned practice tasks.",
            "Export summary notes to PDF or PowerPoint presentation for future reference."
        ]

        exec_summary = (
            f"The training session '{title}' focused on practical demonstrations and instruction. "
            f"Key concepts were presented across {len(topics)} timestamped segments, detailing step-by-step procedures and key discussion points."
        )

        return {
            "executive_summary": exec_summary,
            "topics": topics[:8],
            "key_takeaways": takeaways[:5],
            "action_items": action_items,
            "qna_highlights": [
                {
                    "question": "What were the main objectives of this training?",
                    "answer": exec_summary
                }
            ]
        }

    def answer_question(self, transcript: str, summary: Dict[str, Any], question: str, chat_history: List[Dict[str, Any]] = None) -> str:
        """Answers questions raised by user about the training session."""
        if self.gemini_api_key and self.gemini_api_key.strip():
            try:
                ans = self._answer_with_gemini(transcript, summary, question, chat_history)
                if ans:
                    return ans
            except Exception as e:
                print(f"Gemini Q&A error: {e}. Using local search fallback.")

        return self._answer_fallback(transcript, summary, question)

    def _answer_with_gemini(self, transcript: str, summary: Dict[str, Any], question: str, chat_history: List[Dict[str, Any]]) -> str:
        """Answers questions using Gemini API with full transcript context."""
        import google.generativeai as genai
        genai.configure(api_key=self.gemini_api_key.strip())
        
        hist_text = ""
        if chat_history:
            for item in chat_history[-4:]:
                hist_text += f"{item.get('sender', 'User')}: {item.get('message', '')}\n"
                
        prompt = f"""
You are TrainIQ Assistant, an intelligent AI tutor and meeting analyst.
Answer the user's question based strictly on the following training session content.

EXECUTIVE SUMMARY:
{summary.get('executive_summary', '')}

TRANSCRIPT:
{transcript}

RECENT CHAT HISTORY:
{hist_text}

USER QUESTION:
{question}

Provide a direct, helpful, and professional answer. Include timestamp references (e.g. [02:15]) whenever referring to specific parts of the training recording so the user knows where to look!
"""
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip() if response and response.text else "I could not generate an answer at this time."

    def _answer_fallback(self, transcript: str, summary: Dict[str, Any], question: str) -> str:
        """Local keyword & sentence matcher fallback when offline."""
        q_words = [w.lower() for w in re.findall(r"\w+", question) if len(w) > 2]
        
        best_matches = []
        lines = transcript.split("\n")
        
        for line in lines:
            line_lower = line.lower()
            score = sum(1 for w in q_words if w in line_lower)
            if score > 0:
                best_matches.append((score, line))
                
        best_matches.sort(key=lambda x: x[0], reverse=True)
        
        if best_matches:
            matched_lines = [item[1] for item in best_matches[:3]]
            matched_str = "\n".join(matched_lines)
            return f"Based on the session transcript:\n\n{matched_str}\n\n(Tip: Provide a Gemini API Key in Settings for deeper AI reasoning and instant semantic answers!)"
        
        # Check summary topics
        for topic in summary.get("topics", []):
            topic_str = f"{topic.get('topic', '')} {topic.get('details', '')}"
            if any(w in topic_str.lower() for w in q_words):
                return f"At timestamp {topic.get('timestamp', '[00:00]')}, the session covered: **{topic.get('topic')}**.\nDetails: {topic.get('details')}"
                
        return f"Regarding '{question}': Based on the recorded session summary:\n{summary.get('executive_summary', 'No specific context match found in transcript.')}\n\n(For interactive AI analysis, add your Gemini API Key in Settings!)"
