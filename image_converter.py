import os
from PIL import Image
import io
from config import TEMP_DIR
import uuid

class ImageConverter:
    @staticmethod
    def convert_to_pdf(image_path):
        try:
            # Generate unique filename for the PDF
            pdf_filename = f"{str(uuid.uuid4())}.pdf"
            pdf_path = os.path.join(TEMP_DIR, pdf_filename)

            # Open and convert image to PDF
            image = Image.open(image_path)

            # Convert image to RGB if it's in RGBA mode
            if image.mode == 'RGBA':
                image = image.convert('RGB')

            # Save as PDF
            image.save(pdf_path, "PDF", resolution=100.0)

            return pdf_path
        except Exception as e:
            raise Exception(f"Error converting image to PDF: {str(e)}")

    @staticmethod
    def cleanup_files(file_paths):
        """Remove temporary files after processing"""
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass
