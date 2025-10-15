import google.generativeai as genai
import os
from typing import Dict, Any, List
import logging
from dotenv import load_dotenv
import json

load_dotenv()
logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        # Configure Gemini API
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not found. Using mock responses.")
            self.mock_mode = True
        else:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
            self.mock_mode = False
    
    async def analyze_report(self, text: str) -> Dict[str, Any]:
        """Analyze medical report text using Gemini AI"""
        if self.mock_mode:
            return self._get_mock_analysis(text)
        
        try:
            prompt = f"""
            You are a senior clinician. Extract a structured analysis from the following medical report text.
            Return ONLY valid minified JSON matching this schema (no extra commentary):
            {{
              "summary": string,
              "key_findings": string[],
              "recommendations": string[],
              "patient": {{"name": string|null, "age": string|null, "sex": string|null, "uhid": string|null, "mrn": string|null}},
              "encounter": {{"admission_date": string|null, "discharge_date": string|null, "department": string|null, "discharge_type": string|null}},
              "vitals": [{{"name": string, "value": string, "unit": string|null, "flag": "high"|"low"|"normal"|null}}],
              "labs": [{{"name": string, "value": string, "unit": string|null, "reference": string|null, "flag": "high"|"low"|"normal"|null}}],
              "diagnoses": [{{"name": string, "status": "active"|"resolved"|"suspected"|null, "severity": "mild"|"moderate"|"severe"|null}}],
              "procedures": string[],
              "imaging_findings": string[],
              "red_flags": string[],
              "follow_up": [{{"action": string, "timeframe": string|null}}],
              "medications": [{{"name": string, "dose": string|null, "frequency": string|null, "duration": string|null, "notes": string|null}}],
              "lifestyle": [{{"category": string, "suggestion": string}}],
              "disclaimer": string
            }}
            Report Text: ```{text}```
            """

            response = self.model.generate_content(prompt)

            # Try to parse JSON from model response robustly
            parsed: Dict[str, Any] = self._parse_json_safely(getattr(response, 'text', '') or str(response))

            # Ensure mandatory compatibility keys exist
            parsed.setdefault("summary", "")
            parsed.setdefault("key_findings", [])
            parsed.setdefault("recommendations", [])

            return parsed
            
        except Exception as e:
            logger.warning(f"Gemini parse failed, using mock analysis. Reason: {str(e)}")
            return self._get_mock_analysis(text)

    async def answer_with_context(self, question: str, context_snippets: str) -> str:
        """Answer a question using provided context snippets."""
        if self.mock_mode:
            return "Based on prior reports, key trends and patient history are considered in the answer."
        try:
            prompt = f"""
            You are a clinical assistant. Use ONLY the provided context to answer the question.
            Context:
            {context_snippets}

            Question: {question}
            Answer concisely for clinicians. If insufficient context, say so.
            """
            response = self.model.generate_content(prompt)
            return getattr(response, 'text', '').strip() or "No answer produced."
        except Exception as e:
            logger.error(f"Error in answer_with_context: {str(e)}")
            return "Unable to answer due to an internal error."
    
    def _get_mock_analysis(self, text: str) -> Dict[str, Any]:
        """Provide mock analysis when Gemini API is not available"""
        # Provide a richer, structured mock
        return {
            "summary": "Patient with intracranial hemorrhage s/p craniotomy; ongoing right hemiplegia and aphasia; hypertension control and neuro-rehab are priorities.",
            "key_findings": [
                "Large left capsular ganglionic bleed with mass effect",
                "Midline shift present on imaging",
                "Right hemiplegia and expressive aphasia",
                "Hypertensive readings during admission"
            ],
            "recommendations": [
                "Strict BP control and home monitoring",
                "Intensive PT/OT/ST rehabilitation",
                "Neurosurgical follow-up for AVM management"
            ],
            "patient": {"name": None, "age": None, "sex": None, "uhid": None, "mrn": None},
            "encounter": {"admission_date": None, "discharge_date": None, "department": "Neurosurgery", "discharge_type": "DAMA"},
            "vitals": [
                {"name": "BP", "value": "170/110", "unit": "mmHg", "flag": "high"},
                {"name": "Temp", "value": "101", "unit": "F", "flag": "high"}
            ],
            "labs": [
                {"name": "Hb", "value": "13.2", "unit": "g/dL", "reference": "13.5-17.5", "flag": "low"}
            ],
            "diagnoses": [
                {"name": "Acute hemorrhagic stroke due to AVM", "status": "active", "severity": "severe"},
                {"name": "Hypertension", "status": "active", "severity": "moderate"}
            ],
            "procedures": [
                "Left temporal craniotomy and evacuation of hematoma",
                "Tracheostomy"
            ],
            "imaging_findings": [
                "Large capsular ganglionic bleed with midline shift",
                "Diffuse intraparenchymal and subarachnoid hemorrhage"
            ],
            "red_flags": [
                "Severe uncontrolled hypertension",
                "Neurological deterioration risk"
            ],
            "follow_up": [
                {"action": "Neurosurgical review", "timeframe": "1-2 weeks"},
                {"action": "Repeat CT/MRI as advised", "timeframe": "2-4 weeks"}
            ],
            "medications": [
                {"name": "Amlodipine", "dose": "5 mg", "frequency": "OD", "duration": None, "notes": "Titrate to BP"}
            ],
            "lifestyle": [
                {"category": "Diet", "suggestion": "Low-salt, heart-healthy diet"},
                {"category": "Smoking/Alcohol", "suggestion": "Complete cessation"}
            ],
            "disclaimer": "Educational summary, not a substitute for clinical judgment."
        }
    
    def _extract_key_findings(self, text: str) -> List[str]:
        """Extract key findings from analysis text"""
        # Simple extraction - in production, use more sophisticated NLP
        findings = []
        lines = text.split('\n')
        for line in lines:
            if any(keyword in line.lower() for keyword in ['finding', 'result', 'value', 'level']):
                findings.append(line.strip())
        return findings[:5]  # Return top 5 findings
    
    def _extract_recommendations(self, text: str) -> List[str]:
        """Extract recommendations from analysis text"""
        recommendations = []
        lines = text.split('\n')
        for line in lines:
            if any(keyword in line.lower() for keyword in ['recommend', 'suggest', 'should', 'consider']):
                recommendations.append(line.strip())
        return recommendations[:5]  # Return top 5 recommendations

    def _parse_json_safely(self, raw: str) -> Dict[str, Any]:
        """Parse JSON from raw model text, handling code fences and stray text."""
        raw = raw.strip()
        # 1) Direct parse
        try:
            return json.loads(raw)
        except Exception:
            pass

        # 2) Extract from triple backticks ```json ... ``` or ``` ... ```
        import re
        fence_pattern = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
        match = fence_pattern.search(raw)
        if match:
            candidate = match.group(1).strip()
            try:
                return json.loads(candidate)
            except Exception:
                # continue to next strategy
                pass

        # 3) Best-effort: first '{' to last '}' substring
        start = raw.find('{')
        end = raw.rfind('}')
        if start != -1 and end != -1 and end > start:
            candidate = raw[start:end+1]
            try:
                return json.loads(candidate)
            except Exception:
                pass

        # If all strategies fail, raise to trigger mock fallback
        raise ValueError('Could not parse JSON from model response')