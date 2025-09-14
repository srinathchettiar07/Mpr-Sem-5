from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import shutil
from pathlib import Path
import logging
from services.ocr_service import OCRService
from services.gemini_service import GeminiService
from services.vector_service import VectorService
from services.kg_service import KGService
from pydantic import BaseModel
from typing import Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Medical Report Analyzer", version="1.0.0")

# Resolve important paths relative to this file
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = (BASE_DIR.parent / "Frontend").resolve()
STATIC_DIR = (FRONTEND_DIR / "static").resolve()
UPLOADS_DIR = (BASE_DIR / "uploads").resolve()

# Create directories
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# Mount static files and templates
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(FRONTEND_DIR))

# Initialize services
ocr_service = OCRService()
gemini_service = GeminiService()
vector_service = VectorService()
kg_service = KGService()


class QueryRequest(BaseModel):
    patient_id: Optional[str] = None
    question: str
    top_k: int = 5

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main upload page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/results", response_class=HTMLResponse)
async def results_page(request: Request):
    """Serve the results page"""
    return templates.TemplateResponse("results.html", {"request": request})

@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """Handle file upload and processing"""
    try:
        # Validate file type
        allowed_types = [
            "application/pdf", 
            "image/jpeg", 
            "image/png", 
            "image/jpg"
        ]
        
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail="Only PDF, JPEG, and PNG files are allowed"
            )
        
        # Save uploaded file
        file_path = f"uploads/{file.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"File saved: {file_path}")
        
        # Extract text using OCR
        extracted_text = await ocr_service.extract_text(file_path)
        
        if not extracted_text.strip():
            raise HTTPException(
                status_code=400, 
                detail="No text could be extracted from the file"
            )
        
        logger.info(f"Text extracted: {len(extracted_text)} characters")
        
        # Optional: patient_id from query string or headers/form
        patient_id = request.query_params.get('patient_id') or request.headers.get('X-Patient-Id')

        # Vector DB: add current doc (chunked) and retrieve similar for context
        similar = []
        try:
            vector_service.add_document_chunks(patient_id, extracted_text, filename=file.filename)
            similar = vector_service.query_similar(patient_id, extracted_text, top_k=3)
        except Exception as _:
            pass

        # KG: extract entities and upsert visit
        try:
            entities = kg_service.extract_entities(extracted_text)
            if patient_id:
                kg_service.upsert_visit(
                    patient_id=patient_id,
                    extracted_text=extracted_text,
                    meds=entities.get('medications', []),
                    labs=entities.get('labs', []),
                    conditions=entities.get('conditions', []),
                )
        except Exception as _:
            entities = {"medications": [], "labs": [], "conditions": []}

        # Build context for Gemini
        context_snippets = []
        if similar:
            for item in similar:
                meta = item.get('metadata', {})
                context_snippets.append(f"[Prev:{meta.get('filename','unknown')}] {item.get('text','')}")
        context_text = "\n\n".join(context_snippets) if context_snippets else ""

        # Analyze with Gemini (include context if present)
        analysis_input = extracted_text if not context_text else f"Context from prior reports:\n{context_text}\n\nCurrent report:\n{extracted_text}"
        analysis = await gemini_service.analyze_report(analysis_input)
        
        # Generate insights
        insights = generate_insights(extracted_text)
        
        # Clean up uploaded file
        os.remove(file_path)
        
        return JSONResponse({
            "success": True,
            "extracted_text": extracted_text,
            "analysis": analysis,
            "insights": insights,
            "filename": file.filename,
            "patient_id": patient_id,
            "context_used": len(context_snippets) > 0,
            "entities": entities
        })
        
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        # Clean up file if it exists
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        
        raise HTTPException(status_code=500, detail=str(e))

def generate_insights(text: str) -> list:
    """Generate hardcoded insights based on text analysis"""
    insights = []
    text_lower = text.lower()
    
    # Cholesterol insights
    if "cholesterol" in text_lower:
        if any(word in text_lower for word in ["high", "elevated", "200", "220", "240"]):
            insights.append({
                "category": "Cholesterol",
                "recommendation": "Consider a heart-healthy diet low in saturated fats. Include more fiber-rich foods like oats, beans, and vegetables.",
                "priority": "High"
            })
    
    # Blood pressure insights
    if any(word in text_lower for word in ["blood pressure", "hypertension", "bp"]):
        if any(word in text_lower for word in ["high", "elevated", "140", "150", "160"]):
            insights.append({
                "category": "Blood Pressure",
                "recommendation": "Reduce sodium intake, increase physical activity, and consider stress management techniques.",
                "priority": "High"
            })
    
    # Blood sugar/diabetes insights
    if any(word in text_lower for word in ["glucose", "diabetes", "blood sugar", "hba1c"]):
        if any(word in text_lower for word in ["high", "elevated", "diabetes", "pre-diabetic"]):
            insights.append({
                "category": "Blood Sugar",
                "recommendation": "Monitor carbohydrate intake, maintain regular meal times, and increase physical activity.",
                "priority": "High"
            })
    
    # Weight insights
    if any(word in text_lower for word in ["weight", "bmi", "obesity", "overweight"]):
        insights.append({
            "category": "Weight Management",
            "recommendation": "Consider a balanced diet with portion control and regular exercise routine.",
            "priority": "Medium"
        })
    
    # Default insight if none found
    if not insights:
        insights.append({
            "category": "General Health",
            "recommendation": "Maintain a balanced diet, regular exercise, and follow up with your healthcare provider.",
            "priority": "Low"
        })
    
    return insights

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Medical Report Analyzer"}


@app.post("/query")
async def query_patient(request: QueryRequest):
    """Patient-specific Q&A using vector retrieval context."""
    if not vector_service.enabled:
        raise HTTPException(status_code=503, detail="Vector service not available")

    snippets = []
    try:
        # Use recent patient docs as context, biased by similarity to question if patient_id present
        if request.patient_id:
            # Retrieve by similarity to the question, constrained to patient
            similar = vector_service.query_similar(request.patient_id, request.question, top_k=request.top_k)
            if not similar:
                # fallback to all texts for patient
                items = vector_service.list_texts_by_patient(request.patient_id, limit=50)
                snippets = [it.get("text", "") for it in items][:request.top_k]
            else:
                snippets = [s.get("text", "") for s in similar]
        else:
            # No patient context; answer will likely say insufficient context
            snippets = []
    except Exception as e:
        logger.error(f"/query retrieval error: {str(e)}")
        snippets = []

    context_text = "\n---\n".join(snippets)
    answer = await gemini_service.answer_with_context(request.question, context_text)

    return {
        "patient_id": request.patient_id,
        "question": request.question,
        "snippets_used": len(snippets),
        "answer": answer
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)