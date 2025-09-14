
import pytesseract
from PIL import Image
import pypdf
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class OCRService:
    def __init__(self):
        # Configure tesseract path if needed (uncomment for Windows)
        # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        pass
    
    async def extract_text(self, file_path: str) -> str:
        """Extract text from PDF or image file"""
        file_extension = Path(file_path).suffix.lower()
        
        if file_extension == '.pdf':
            return await self._extract_from_pdf(file_path)
        elif file_extension in ['.jpg', '.jpeg', '.png']:
            return await self._extract_from_image(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")
    
    async def _extract_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF using pypdf"""
        try:
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            
            logger.info(f"Extracted text from PDF: {len(text)} characters")
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise
    
    async def _extract_from_image(self, file_path: str) -> str:
        """Extract text from image using pytesseract"""
        try:
            # Run OCR in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(
                None, 
                self._ocr_image, 
                file_path
            )
            
            logger.info(f"Extracted text from image: {len(text)} characters")
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting text from image: {str(e)}")
            raise
    
    def _ocr_image(self, file_path: str) -> str:
        """Perform OCR on image file"""
        image = Image.open(file_path)
        # Use custom config for better medical text recognition
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()[]/:- '
        text = pytesseract.image_to_string(image, config=custom_config)
        return text