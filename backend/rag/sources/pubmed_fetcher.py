"""
pubmed_fetcher.py
------------------
Busca y extrae artículos científicos desde la API de PubMed (NCBI Entrez).
"""

import os
import time
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import requests

logger = logging.getLogger(__name__)

# Términos sugeridos para las búsquedas de NutriAI
TERMINOS_BUSQUEDA = [
    # Macronutrientes y composición corporal
    "protein requirements muscle hypertrophy",
    "caloric deficit fat loss muscle preservation",
    "carbohydrate intake athletic performance",
    "dietary fat omega-3 health effects",

    # Patologías que soportamos
    "mediterranean diet type 2 diabetes management",
    "DASH diet hypertension blood pressure",
    "hypothyroidism diet nutrition",
    "polycystic ovary syndrome diet",
    "gout diet purine restriction",
    "celiac disease gluten free nutrition",
    "iron deficiency anemia diet",
    "high cholesterol dietary intervention",

    # Micronutrientes críticos
    "vitamin D deficiency supplementation",
    "vitamin B12 vegan vegetarian",
    "iron absorption plant based diet",
    "magnesium deficiency symptoms diet",

    # Estrategias dietéticas
    "intermittent fasting weight loss evidence",
    "ketogenic diet clinical evidence",
    "plant based diet health outcomes",
    "caloric restriction longevity",

    # Población española y mediterránea
    "mediterranean diet Spain health",
    "Spanish population nutritional habits",

    # Suplementación con evidencia
    "creatine supplementation resistance training",
    "protein supplementation muscle synthesis",
    "omega-3 supplementation cardiovascular",

    # Términos nuevos añadidos para ampliar a 500+ artículos
    "gut microbiome diet nutrition",
    "sleep quality nutrition diet",
    "anti inflammatory diet chronic disease",
    "zinc deficiency immune function",
    "selenium thyroid function diet",
    "probiotics digestive health evidence",
    "fiber intake cardiovascular disease",
    "antioxidants diet prevention",
    "intermittent fasting metabolic health",
    "muscle protein synthesis leucine",
    "omega 3 brain health cognition",
    "calcium bone density osteoporosis diet",
    "hydration athletes performance",
    "weight loss plateau caloric adaptation",
    "emotional eating psychology nutrition",
    "menstrual cycle nutrition iron",
    "pregnancy nutrition requirements",
    "elderly nutrition sarcopenia",
    "children adolescents nutrition growth",
    "vegan diet complete protein sources",
]


class PubMedFetcher:
    def __init__(self, api_key: str = None):
        # Usar la API Key pasada o la del .env (si existe)
        self.api_key = api_key or os.getenv("PUBMED_API_KEY", "")
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def _get_headers_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Añade la API Key a los parámetros si está disponible."""
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def buscar_articulos(self, query: str, max_resultados: int = 20) -> List[str]:
        """
        Busca IDs de PubMed para un término dado.
        Filtra por los últimos 5 años (2021-2026).
        """
        url = f"{self.base_url}/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": max_resultados,
            "mindate": "2021",
            "maxdate": "2026",
            "datetype": "pdat"  # Publication date
        }
        params = self._get_headers_params(params)

        try:
            res = requests.get(url, params=params, timeout=15)
            res.raise_for_status()
            data = res.json()
            id_list = data.get("esearchresult", {}).get("idlist", [])
            return id_list
        except Exception as e:
            logger.error("Error al buscar en PubMed para '%s': %s", query, e)
            return []

    def descargar_detalles(self, id_list: List[str]) -> List[Dict[str, Any]]:
        """Descarga abstracts y metadatos de una lista de PMIDs."""
        if not id_list:
            return []

        url = f"{self.base_url}/efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml"
        }
        params = self._get_headers_params(params)

        articulos = []
        try:
            res = requests.get(url, params=params, timeout=20)
            res.raise_for_status()
            
            # Parsear XML
            root = ET.fromstring(res.content)
            
            for article_xml in root.findall(".//PubmedArticle"):
                try:
                    # 1. PMID
                    pmid = article_xml.findtext(".//PMID") or ""
                    
                    # 2. Título
                    titulo = article_xml.findtext(".//ArticleTitle") or ""
                    
                    # 3. Abstract
                    abstract_texts = article_xml.findall(".//AbstractText")
                    abstract = " ".join([t.text for t in abstract_texts if t.text])
                    
                    if not abstract.strip():
                        # Si no hay abstract, omitimos el artículo ya que el RAG necesita el texto
                        continue

                    # 4. Revista
                    revista = article_xml.findtext(".//Journal/Title") or ""
                    
                    # 5. Año de publicación
                    año = None
                    year_elem = article_xml.find(".//JournalIssue/PubDate/Year")
                    if year_elem is not None and year_elem.text:
                        try:
                            año = int(year_elem.text)
                        except ValueError:
                            pass
                    
                    if not año:
                        medline_date = article_xml.findtext(".//JournalIssue/PubDate/MedlineDate")
                        if medline_date:
                            # Intentar buscar un año de 4 dígitos en el texto
                            import re
                            match = re.search(r"\b(20\d{2})\b", medline_date)
                            if match:
                                año = int(match.group(1))
                    
                    if not año:
                        año = 2023  # Fallback razonable
                    
                    # 6. DOI
                    doi = ""
                    for article_id in article_xml.findall(".//ArticleIdList/ArticleId"):
                        if article_id.attrib.get("IdType") == "doi":
                            doi = article_id.text or ""
                            break

                    # 7. Autores
                    autores_list = []
                    for author in article_xml.findall(".//AuthorList/Author"):
                        ln = author.findtext("LastName") or ""
                        fn = author.findtext("ForeName") or ""
                        if ln:
                            autores_list.append(f"{ln} {fn}".strip())
                    autores = ", ".join(autores_list[:5])  # guardar hasta 5 autores
                    if len(autores_list) > 5:
                        autores += " et al."

                    articulos.append({
                        "pmid": pmid,
                        "titulo": titulo,
                        "abstract": abstract,
                        "revista": revista,
                        "año": año,
                        "doi": doi,
                        "autores": autores
                    })
                except Exception as parse_error:
                    logger.debug("Error al parsear artículo XML: %s", parse_error)
                    continue

        except Exception as e:
            logger.error("Error al descargar detalles de PubMed: %s", e)
            
        return articulos

    def fetch_todo(self, max_por_termino: int = 20) -> List[Dict[str, Any]]:
        """
        Orquesta la descarga completa para todos los términos de búsqueda sugeridos.
        Retorna la lista de artículos mapeados y listos para indexar.
        """
        todos_articulos = {}
        logger.info("Iniciando descarga de PubMed para %d términos...", len(TERMINOS_BUSQUEDA))
        
        # Si no hay API Key, NCBI aplica rate limits severos. Hacemos pausas más largas.
        delay = 0.1 if self.api_key else 0.5
        
        for idx, termino in enumerate(TERMINOS_BUSQUEDA):
            logger.info("[%d/%d] Buscando '%s'...", idx + 1, len(TERMINOS_BUSQUEDA), termino)
            ids = self.buscar_articulos(termino, max_resultados=max_por_termino)
            
            # Filtrar IDs que ya hayamos descargado
            nuevos_ids = [i for i in ids if i not in todos_articulos]
            
            if nuevos_ids:
                logger.info("  Descargando %d artículos nuevos...", len(nuevos_ids))
                detalles = self.descargar_detalles(nuevos_ids)
                for art in detalles:
                    art["termino_origen"] = termino
                    todos_articulos[art["pmid"]] = art
                time.sleep(delay)
                
        logger.info("Descarga de PubMed completada. %d artículos válidos recuperados.", len(todos_articulos))
        return list(todos_articulos.values())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    fetcher = PubMedFetcher()
    # Prueba rápida con un término
    ids = fetcher.buscar_articulos("creatine supplementation resistance training", max_resultados=3)
    print("IDs encontrados:", ids)
    if ids:
        detalles = fetcher.descargar_detalles(ids)
        print("Primer artículo descargado:")
        print(detalles[0] if detalles else "Ninguno")
