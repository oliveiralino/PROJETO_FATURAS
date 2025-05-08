from paddleocr import PaddleOCR
import fitz
import cv2
import numpy as np
import re
from pathlib import Path
import logging
import io
import unicodedata
import os
import sys

# Quando empacotado pelo PyInstaller, tudo é extraído em sys._MEIPASS
bundle_dir = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))

# caminho bruto onde colocamos a pasta paddle_models via --add-data
raw_model_dir = os.path.join(bundle_dir, "paddle_models")

# corrige caso tenha ficado aninhado paddle_models/paddle_models
if os.path.isdir(os.path.join(raw_model_dir, "paddle_models")):
    model_dir = os.path.join(raw_model_dir, "paddle_models")
else:
    model_dir = raw_model_dir

# debug para verificação
print(f"[DEBUG] bundle_dir = {bundle_dir}")
print(f"[DEBUG] model_dir  = {model_dir}")
print(f"[DEBUG] exists?    = {os.path.isdir(model_dir)}")
print(f"[DEBUG] listing    = {os.listdir(model_dir) if os.path.isdir(model_dir) else 'N/A'}")


PDF_RESOLUTION_MATRIX = fitz.Matrix(3, 3)
OCR_LANG = 'latin'
USE_GPU = False


# === Funções Auxiliares
def remove_accents(input_str):
    if not isinstance(input_str, str): return ""
    try: nfkd_form = unicodedata.normalize('NFKD', input_str); return "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    except Exception as e: logging.error(f"[remove_accents] Erro: {e}"); return input_str

def clean_value(text):
    # Função EXATA do seu script funcional
    if text is None: return None
    text = str(text).strip().replace('€', '').strip() # Removido $ e moedas genéricas
    is_negative = False
    if text.startswith('-'): is_negative = True; text = text[1:].strip()
    elif text.endswith('-'): is_negative = True; text = text[:-1].strip()
    text = text.replace(" ", "")
    if ',' in text and '.' in text:
         if text.rfind('.') < text.rfind(','): text = text.replace('.', '').replace(',', '.')
         else: text = text.replace(',', '')
    elif ',' in text: text = text.replace(',', '.')
    cleaned_text = re.sub(r"[^\d.]", "", text)
    if is_negative: cleaned_text = "-" + cleaned_text
    try:
        if cleaned_text in ['.', '-.','-','']: return None # Adicionado '-' e ''
        float(cleaned_text)
        return cleaned_text
    except ValueError:
        # logging.warning(f"[OCR clean_value] Falha: '{text}' -> '{cleaned_text}'") # Log opcional
        return None

# === Funções OCR Pipeline
def pdf_to_img_ocr(pdf_path):
    # Função pdf_to_img_and_text adaptada para retornar só a imagem
    img_page_1 = None; doc = None
    try:
        doc = fitz.open(pdf_path)
        if doc.page_count > 0:
            page = doc.load_page(0); pix = page.get_pixmap(matrix=PDF_RESOLUTION_MATRIX, alpha=False)
            if pix.samples:
                img_page_1 = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                if img_page_1.shape[2] == 1: img_page_1 = cv2.cvtColor(img_page_1, cv2.COLOR_GRAY2BGR)
                elif img_page_1.shape[2] == 4: img_page_1 = cv2.cvtColor(img_page_1, cv2.COLOR_RGBA2BGR)
            else: logging.warning(f"[OCR] Pixmap vazio para {Path(pdf_path).name}")
        else: logging.warning(f"[OCR] PDF sem páginas: {Path(pdf_path).name}")
    except Exception as e: logging.error(f"[OCR] Erro pdf_to_img para {Path(pdf_path).name}: {e}"); img_page_1 = None
    finally:
         if doc:
             try: doc.close()
             except Exception as close_err: logging.error(f"[OCR] Erro ao fechar doc: {close_err}")
    return img_page_1

def run_ocr_task(img_array):
    # Função run_ocr do script funcional (renomeada task)
    lines = []
    if not OCR_ENGINE_OK: logging.error("[OCR] Engine não disponível para run_ocr_task."); return lines
    if img_array is None: logging.warning("[OCR] Imagem None para run_ocr_task."); return lines
    try:
        result = ocr_engine.ocr(img_array, cls=True)
        if result and isinstance(result, list) and len(result) > 0 and result[0] is not None:
             for line_info in result[0]:
                 if isinstance(line_info, list) and len(line_info) == 2: text_tuple = line_info[1]
                 if isinstance(text_tuple, tuple) and len(text_tuple) > 0: text = text_tuple[0]
                 if isinstance(text, str): lines.append(text.strip())
        if lines: full_ocr_text = "\n".join(lines); full_ocr_text = re.sub(r'\n\s*\n', '\n', full_ocr_text.strip()); full_ocr_text = re.sub(r' +', ' ', full_ocr_text); return full_ocr_text.splitlines()
        else: logging.warning("[OCR] run_ocr_task não extraiu linhas."); return []
    except Exception as e: logging.error(f"[OCR] Erro run_ocr_task: {e}", exc_info=True); return []

def extract_moeda_ocr(text):
    """
    Busca no texto completo a ocorrência de símbolos ou códigos de moeda mais comuns.
    Retorna, por exemplo, '€', 'EUR', 'USD' ou None.
    """
    m = re.search(r"\b(€|EUR|USD|US\$)\b", text)
    return m.group(1) if m else None


# --- Função de Extração Principal
def extract_fields_from_text(text_lines, arquivo_nome):
    result = {
        "ARQUIVO": arquivo_nome, "EMISOR": None, "Nº CLIENTE": None, "CLIENTE": None,
        "REFERENCIA FACTURA": None, "DESCRIPCIÓN": None, "BASE IMPONIBLE": None,
        "IMPUESTOS": None, "IMPORTE TOTAL": None, "FECHA FACTURA": None,
        "FECHA VENCIMIENTO": None, "OBSERVACIONES": None
    }
    full_text = "\n".join(text_lines)
    search_text_norm = remove_accents(full_text.lower())

    # **Extrai moeda**  
    result["MOEDA"] = extract_moeda_ocr(full_text)

    # --- Patterns ---
    num_pattern = r"([-+]?\s?\d{1,3}(?:[.,]?\d{3})*(?:[.,]\d{1,2}))\s*(-?)" # G1: Valor, G2: Sinal
    date_pattern = r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})"

    def combine_num_groups(match_obj):
        if not match_obj: return None
        val = match_obj.group(1).strip()
        sign = match_obj.group(2).strip()
        combined = (sign + val).replace("- ", "-")
        return combined

    # EMISOR, Nº CLIENTE, CLIENTE (Manter)
    if re.search(r"enel\s+green\s+power\s+espa[nñ]a", search_text_norm): result["EMISOR"] = "Enel Green Power España S.L."
    elif re.search(r"edistribucion\s+redes\s+digitales", search_text_norm): result["EMISOR"] = "EDISTRIBUCIÓN Redes Digitales S.L.U."
    elif re.search(r"endesa\s+x\s+way", search_text_norm):
        match = re.search(r"(ENDESA\s+X\s+WAY\s+SUC\.PORTUGAL)", full_text, re.IGNORECASE)
        result["EMISOR"] = match.group(1).strip() if match else "ENDESA X WAY SUC.PORTUGAL"
    elif re.search(r"\bendesa\b.*\bs\.a\.", search_text_norm): result["EMISOR"] = "ENDESA S.A."
    if not result["EMISOR"]:
         first_lines = [line for line in text_lines[:3] if line.strip()]
         if first_lines: result["EMISOR"] = first_lines[0].strip(); logging.warning(f"Emissor não identificado, usando fallback: {result['EMISOR']}")

    match = re.search(r"(?:n[ºo°]?\s*cliente|customer\s*no)\.?\s*:?\s*(\S+)", full_text, re.IGNORECASE)
    if match: result["Nº CLIENTE"] = match.group(1).strip()

    match = re.search(r"(?:nombre|name)\s*:?\s*(.+?)(?:\s*Direcci[oó]n Fiscal|\s*NIF/CIF|\s*N[ºo°]?\s*Factura|\n|$)", full_text, re.IGNORECASE | re.DOTALL)
    if match:
        client_name = match.group(1).strip().split('\n')[0]
        if len(client_name.split()) > 6 and re.search(r'\d', client_name):
             m_sl = re.search(r'(.+?\b(?:S\.L\.?U?|S\.A\.?)\b)', client_name, re.IGNORECASE)
             if m_sl: client_name = m_sl.group(1).strip()
        result["CLIENTE"] = client_name

    # REFERENCIA FACTURA (**REVERTENDO/AJUSTANDO Regex**)
    # Permite letras (FT), números, barras, e potencialmente espaços (removidos depois)
    match = re.search(r"(?:n[ºo°]?\s*factura|invoice\s*no)\.?\s*:?\s*([A-Z0-9/ -]+)", full_text, re.IGNORECASE)
    if match:
        # Limpa espaços e para antes de datas ou palavras-chave comuns que podem vir depois
        ref_text = match.group(1).strip()
        ref_text = re.split(r'\s+(?:Fecha|Issue|Date)', ref_text, 1)[0].strip() # Para antes de datas
        result["REFERENCIA FACTURA"] = ref_text.replace(" ", "") # Remove espaços internos restantes

    # FECHAS (Manter)
    match = re.search(fr"(?:Fecha\s*emisi[oó]n|Issue\s*Date)\s*:?\s*{date_pattern}", full_text, re.IGNORECASE)
    if match: result["FECHA FACTURA"] = match.group(1).strip()
    match = re.search(fr"(?:Fecha\s*vencimiento|Vencimiento|Due\s*Date|Hasta\s*el|Until)\s*:?\s*{date_pattern}", full_text, re.IGNORECASE)
    if match: result["FECHA VENCIMIENTO"] = match.group(1).strip()

    # DESCRIPCIÓN (Lógica Principal + **Fallback Ajustado**)
    desc_lines_collected = []
    in_description = False
    start_desc_keywords = ["concepto", "concept"]
    stop_desc_patterns = [
        r"detalle\s+de\s+la\s+factura", r"detalle\s+factura", r"invoice\s+detail",
        r"base\s+imponible", r"tax\s+base", r"total\s+importe", r"invoice\s+total",
        r"observaciones", r"observations", r"iban", r"swift",
        r"^\s*(cantidad|quantity|precio|price|importe|amount|mon|curr)",
        r"^\s*forma\s+de\s+pago", r"^\s*payment\s+method",
    ]
    for i, line in enumerate(text_lines): # Coleta via Concepto (igual antes)
        line_lower_norm = remove_accents(line.lower().strip())
        line_content = line.strip()
        if any(line_lower_norm.startswith(key) for key in start_desc_keywords):
            in_description = True
            potential_desc = line_content.split(":", 1)[1].strip() if ":" in line_content else ""
            if potential_desc: desc_lines_collected.append(potential_desc)
            continue
        if in_description:
            should_stop = False
            if not line_content: pass
            elif any(re.search(stop, line_lower_norm, re.IGNORECASE) for stop in stop_desc_patterns): should_stop = True
            if should_stop: in_description = False
            else: desc_lines_collected.append(line_content)

    if desc_lines_collected:
        result["DESCRIPCIÓN"] = " ".join(desc_lines_collected).strip()
    else: # Fallback via Detalle/Descripción
        logging.info(f"Descrição via 'Concepto' falhou para {arquivo_nome}. Tentando fallback via 'Detalle/Descripción'.")
        detail_match = re.search(r"(?:Detalle\s+de\s+la\s+Factura|Invoice\s+Detail)\s*\n", full_text, re.IGNORECASE)
        if detail_match:
            start_index = detail_match.end()
            text_after_detail = full_text[start_index:]
            desc_header_match = re.search(r"^\s*(?:Descripci[oó]n|Description)\s*\n", text_after_detail, re.IGNORECASE | re.MULTILINE)
            if desc_header_match:
                start_desc_index = desc_header_match.end()
                text_after_desc_header = text_after_detail[start_desc_index:]
                # **AJUSTE AQUI:** Loop nas próximas linhas ignorando cabeçalhos de tabela
                header_patterns = r"^\s*(cantidad|quantity|precio|price|importe|amount|mon|curr|value|impte)\b"
                found_desc_line = None
                for line in text_after_desc_header.split('\n'):
                    line_strip = line.strip()
                    if line_strip and not re.search(header_patterns, line_strip, re.IGNORECASE):
                        found_desc_line = line_strip
                        break # Pega a primeira linha significativa
                if found_desc_line:
                    result["DESCRIPCIÓN"] = found_desc_line

    # --- BASE IMPONIBLE & IMPORTE TOTAL
    base_value_clean = None
    total_value_clean = None

    match_base = re.search(fr"(?:BASE\s*IMPONIBLE|TAX\s*BASE)\s*€?\s*\n?.*?{num_pattern}", full_text, re.IGNORECASE | re.DOTALL)
    if match_base:
        base_value_clean = clean_value(combine_num_groups(match_base))
        result["BASE IMPONIBLE"] = base_value_clean

    match_total = re.search(fr"(?:TOTAL\s*Importe\s*Factura|Invoice\s*TOTAL\s*Value|TOTAL\s*A\s*PAGAR)\s*€?\s*\n?.*?{num_pattern}", full_text, re.IGNORECASE | re.DOTALL)
    if not match_total:
        matches = list(re.finditer(fr"\bTOTAL\b\s*€?\s*\n?.*?{num_pattern}", full_text, re.IGNORECASE | re.DOTALL))
        if matches: match_total = matches[-1]
    if match_total:
        total_value_clean = clean_value(combine_num_groups(match_total))
        result["IMPORTE TOTAL"] = total_value_clean

    # --- IMPUESTOS
    tax_value = None
    # 1. Verifica se Base e Total foram encontrados e são numéricos
    try:
        base_float = float(base_value_clean) if base_value_clean is not None else None
        total_float = float(total_value_clean) if total_value_clean is not None else None

        # 2. Tenta calcular o imposto: Total - Base
        if base_float is not None and total_float is not None:
            calculated_tax = total_float - base_float
            # Formata de volta para string com 2 casas decimais
            tax_value = "{:.2f}".format(calculated_tax)

            # 3. Sanity Check: O valor calculado é razoável?
            #    (Evita casos onde Base ou Total foram extraídos errados)
            #    - Se a base for 0, o imposto calculado deve ser igual ao total. Ok.
            #    - Se o imposto calculado for 0.00, verifica se o texto menciona 0%
            #    - Se o imposto calculado for muito diferente de (Base * taxa_padrão), pode ser erro.
            if abs(calculated_tax) < 0.005: # Praticamente zero
                 zero_tax_match = re.search(r"(?:iva|output\s*tax)[\s,]*0[,.]00\s*%", full_text, re.IGNORECASE)
                 if zero_tax_match:
                      tax_value = "0.00" # Confirma 0.00
                 else:
                      # Calculou zero, mas não viu 0%. Pode ser erro de extração Base/Total.
                      # Poderíamos invalidar aqui, mas por ora mantemos o cálculo.
                      pass
            # Outros sanity checks podem ser adicionados aqui (ex: verificar contra taxa de 21%)

        # 4. Se o cálculo falhou ou foi invalidado, tenta encontrar 0% explicitamente
        if tax_value is None:
            zero_tax_match = re.search(r"(?:iva|output\s*tax)[\s,]*0[,.]00\s*%", full_text, re.IGNORECASE)
            if zero_tax_match:
                 tax_value = "0.00"

    except (TypeError, ValueError):
        # Se Base ou Total não forem números válidos, o cálculo falha.
        logging.warning(f"Não foi possível calcular imposto para {arquivo_nome} pois Base ou Total não são numéricos.")
        # Tenta fallback para encontrar 0%
        zero_tax_match = re.search(r"(?:iva|output\s*tax)[\s,]*0[,.]00\s*%", full_text, re.IGNORECASE)
        if zero_tax_match:
             tax_value = "0.00"

    result["IMPUESTOS"] = tax_value

    # OBSERVACIONES
    stop_obs_patterns = [
        r"\n\n", r"Pag\.",
        r"ENDESA\s+X\s+WAY", r"Enel\s+Green\s+Power", r"\bENDESA\b.*\bS\.A\.",
        r"ESIP\d+", r"Registro\s+Mercantil", r"Inscrita\s+en\s+el\s+Registro"
    ]
    match = re.search(r"(?:Observaciones|Observations)\s*:?\s*(.*?)(?:" + "|".join(stop_obs_patterns) + r"|\Z)", full_text, re.IGNORECASE | re.DOTALL | re.S)
    if match:
        observations = match.group(1).strip()
        observations = "\n".join(line for line in observations.split('\n') if line.strip() and not line.startswith("ESIP"))
        result["OBSERVACIONES"] = observations.replace('\n', ' ').strip()

    # Log final
    for key, value in result.items():
        essential_keys = ["EMISOR", "Nº CLIENTE", "CLIENTE", "REFERENCIA FACTURA", "BASE IMPONIBLE", "IMPORTE TOTAL", "FECHA FACTURA"]
        if key in essential_keys and value is None:
             logging.warning(f"Campo essencial '{key}' não encontrado no arquivo '{arquivo_nome}'.")

     # ── Converte ponto para vírgula na saída numérica ────────────────
    for key in ["BASE IMPONIBLE", "IMPUESTOS", "IMPORTE TOTAL"]:
        val = result.get(key)
        if isinstance(val, str) and "." in val:
            result[key] = val.replace(".", ",")
    # ──────────────────────────────────────────────────────────────────
    
    return result
    

# --- Função Wrapper (a ser chamada pelo main_processor.py) ---
def processar_pdf_ocr(pdf_path):
    """Extrai dados de um PDF via OCR usando a lógica validada."""
    arquivo_nome = Path(pdf_path).name
    # Usa OCR_ENGINE_OK para verificar se o engine está pronto
    if not PADDLE_OK or not OCR_ENGINE_OK:
        logging.error(f"[OCR Wrapper] Tentativa de processar {arquivo_nome} falhou: OCR não está disponível/funcional.")
        return {"ARQUIVO": arquivo_nome, "ERRO": "OCR não disponível/funcional"}

    img = pdf_to_img_ocr(pdf_path)
    if img is None: return {"ARQUIVO": arquivo_nome, "ERRO": "Falha ao gerar imagem OCR"}

    logging.info(f"[OCR Wrapper] Executando OCR para {arquivo_nome}...")
    ocr_lines = run_ocr_task(img)
    if not ocr_lines: return {"ARQUIVO": arquivo_nome, "ERRO": "OCR não retornou texto"}

    logging.info(f"[OCR Wrapper] Extraindo campos do texto OCR para {arquivo_nome}...")
    # Chama a função principal de extração deste módulo
    extracted_data = extract_fields_from_text(ocr_lines, arquivo_nome)
    return extracted_data

# Remover ou comentar o if __name__ == "__main__": do script original
# if __name__ == "__main__":
#     main()
