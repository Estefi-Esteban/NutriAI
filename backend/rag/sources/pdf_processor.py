"""
pdf_processor.py
-----------------
Descarga y procesa las guías clínicas en formato PDF, dividiéndolas en chunks semánticos.
"""

import os
import tempfile
import logging
from typing import List, Dict, Any
import requests
import pdfplumber

logger = logging.getLogger(__name__)

GUIAS_CLINICAS = [
    {
        "nombre": "Guía SEEDO GIRO 2.0 — Obesidad",
        "url": "https://www.seedo.es/images/site/giro/GUIA-GIRO-2a-edicin_26NOV2024.pdf",
        "fuente": "SEEDO",
        "año": 2024,
    },
    {
        "nombre": "Abordaje integral de las personas con diabetes tipo 2",
        "url": "https://www.seen.es/",
        "fuente": "SEEN",
        "año": 2022,
    },
    {
        "nombre": "Actualización 2025 de la Guía ESC 2019 sobre el manejo de las dislipemias",
        "url": "https://secardiologia.es/images/2024/Gu%C3%ADas/Guia-ESC-2025-actualizacio%CC%81n-manejo-dislipemias.pdf",
        "fuente": "SEC",
        "año": 2025,
    },
]

class PDFProcessor:
    def __init__(self, chunk_words: int = 500, overlap_words: int = 50):
        self.chunk_words = chunk_words
        self.overlap_words = overlap_words

    def descargar_pdf(self, url: str) -> str:
        """Descarga el PDF a un archivo temporal y devuelve su ruta."""
        logger.info("Descargando PDF desde %s...", url)
        try:
            # Añadir User-Agent para evitar bloqueos
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            res = requests.get(url, headers=headers, timeout=30)
            res.raise_for_status()
            
            fd, temp_path = tempfile.mkstemp(suffix=".pdf")
            with os.fdopen(fd, "wb") as f:
                f.write(res.content)
            return temp_path
        except Exception as e:
            logger.warning("Error al descargar PDF desde %s: %s", url, e)
            raise e

    def extraer_texto(self, ruta_pdf: str) -> str:
        """Extrae todo el texto legible de un PDF local."""
        texto_completo = []
        try:
            with pdfplumber.open(ruta_pdf) as pdf:
                for idx, pagina in enumerate(pdf.pages):
                    texto_pag = pagina.extract_text()
                    if texto_pag:
                        texto_completo.append(texto_pag)
        except Exception as e:
            logger.error("Error al leer el PDF %s: %s", ruta_pdf, e)
        return "\n".join(texto_completo)

    def dividir_en_chunks(self, texto: str) -> List[str]:
        """Divide el texto en fragmentos (chunks) de palabras con solapamiento."""
        palabras = texto.split()
        total_palabras = len(palabras)
        
        chunks = []
        if total_palabras <= self.chunk_words:
            return [" ".join(palabras)] if palabras else []

        inicio = 0
        while inicio < total_palabras:
            fin = inicio + self.chunk_words
            chunk_palabras = palabras[inicio:fin]
            chunks.append(" ".join(chunk_palabras))
            
            # Mover el puntero hacia adelante restando el solapamiento
            inicio += (self.chunk_words - self.overlap_words)
            
        return chunks

    def procesar_guia(self, guia: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Descarga, lee y fragmenta una guía específica."""
        chunks_guia = []
        ruta_temp = None
        try:
            ruta_temp = self.descargar_pdf(guia["url"])
            texto = self.extraer_texto(ruta_temp)
            if not texto.strip():
                logger.warning("No se pudo extraer texto del PDF de la guía '%s'", guia["nombre"])
                return []
            
            chunks = self.dividir_en_chunks(texto)
            logger.info("Guía '%s' procesada exitosamente en %d chunks.", guia["nombre"], len(chunks))
            
            for idx, chunk in enumerate(chunks):
                chunks_guia.append({
                    "texto": chunk,
                    "metadata": {
                        "titulo": guia["nombre"],
                        "fuente": guia["fuente"],
                        "tipo": "guia_clinica",
                        "año": guia["año"],
                        "doi": "",
                        "autores": guia["fuente"],
                        "chunk_index": idx
                    }
                })
        except Exception as e:
            logger.error("No se pudo procesar la guía '%s': %s", guia["nombre"], e)
        finally:
            if ruta_temp and os.path.exists(ruta_temp):
                try:
                    os.unlink(ruta_temp)
                except Exception:
                    pass
        return chunks_guia

    def procesar_todas(self) -> List[Dict[str, Any]]:
        """Descarga e indexa todas las guías clínicas configuradas."""
        todos_chunks = []
        for guia in GUIAS_CLINICAS:
            logger.info("Procesando guía: %s", guia["nombre"])
            chunks = self.procesar_guia(guia)
            todos_chunks.extend(chunks)
        return todos_chunks


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    processor = PDFProcessor(chunk_words=100, overlap_words=10)
    # Probar con un PDF ligero si es posible, o simular
    print("Mapeado de guías clínicas listo.")
