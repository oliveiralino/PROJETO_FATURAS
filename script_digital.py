import fitz  # PyMuPDF
import re
import pandas as pd
from pathlib import Path
import traceback

# --- Função principal ---
def extract_invoice_fields(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(0) if doc.page_count > 0 else None
        if not page:
            raise ValueError("PDF sem páginas")

        data = {
            "ARQUIVO": Path(pdf_path).name,
            "EMISOR": extract_emisor(page),
            "Nº CLIENTE": extract_num_cliente(page),
            "CLIENTE": extract_cliente(page),
            "REFERENCIA FACTURA": extract_referencia_factura(page),
            "DESCRIPCIÓN": extract_descripcion(page),
            "BASE IMPONIBLE": extract_base_imponible(page),
            "IMPUESTOS": extract_impuestos(page),
            "IMPORTE TOTAL": extract_importe_total(page),
            "MOEDA": extract_moeda(page),   
            "OBSERVACIONES": extract_observaciones(doc),
        }

        print(f"\n📝 {data['ARQUIVO']}")
        print(f"🔢 DEBUG Valores -> BASE: {data['BASE IMPONIBLE']} | IMPUESTOS: {data['IMPUESTOS']} | TOTAL: {data['IMPORTE TOTAL']}")

        # Detecção e extração por layout alternativo
        if is_special_layout(page):
            print("🔁 Detecção de layout alternativo – aplicando extração especial...")
            special_vals = extract_values_for_special_layout(page)
            for key, val in special_vals.items():
                data[key] = val  # <-- sobrescreve SEM verificar se está preenchido

        # Fallback (apenas se ainda houver campo ausente)
        if any(data.get(k) is None for k in ["BASE IMPONIBLE", "IMPUESTOS", "IMPORTE TOTAL"]):
            fallback_vals = extract_from_text_fallback(page)
            for key, val in fallback_vals.items():
                if data.get(key) is None:
                    data[key] = val

        return validate_totals(data)

    except Exception as e:
        print(f"❌ Erro ao processar {pdf_path}: {e}")
        print(traceback.format_exc())
        return {"ARQUIVO": Path(pdf_path).name, "ERRO": str(e)}


# --- Funções auxiliares ---
def extract_emisor(page):
    try:
        full_text = page.get_text("text")
        emisor_labels = [
            r"Endesa Energía, S[.]A[.]U[.]", r"ENDESA MOBILITY S[.]L[.]",
            r"Endesa Medios y Sistemas S[.]L[.]", r"ENDESA, Sociedad Anónima",
            r"EDISTRIBUCI[^\n]*"
        ]
        for pattern in emisor_labels:
            match = re.search(r"^\s*(" + pattern + ")", full_text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).strip()
        for pattern in emisor_labels:
            match = re.search("(" + pattern + ")", full_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        match = re.search(r"(ENDESA[^\n]*)", full_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    except:
        pass
    return "N/A"

def extract_num_cliente(page):
    return _extract_by_label(page, ["Nº Cliente:", "N° Cliente:", "No Cliente:", "Customer Nº:", "Customer N°:", "Customer No:","Nº Cliente"], r"(\d{6,})")

def extract_cliente(page):
    try:
        labels = ["Nombre:", "Name:", "Razón Social:"]
        for label in labels:
            rects = page.search_for(label)
            if rects:
                rect = rects[0]
                line_rect = fitz.Rect(0, rect.y0 - 1, page.rect.width, rect.y1 + 1)
                text = page.get_text("text", clip=line_rect)
                match = re.search(r"(?:Nombre|Name|Razón Social)[:\s]+(.*?)(?:\s*NIF/CIF:|\s*NIF IVA:|\s*Dirección Fiscal:|$)", text, re.IGNORECASE)
                if match:
                    return match.group(1).strip().removeprefix("F:").strip()
    except:
        pass
    return None

def extract_referencia_factura(page):
    # Modificação: Coloquei um parêntese externo para capturar *qualquer* um dos padrões
    # e usei grupos não-capturantes (?:...) para as alternativas internas.
    pattern = r"((?:FT\s?\d{2,4}/\d{5,})|(?:\d{2}\s*/\s*\d{8,}\s*/\s*\d{2}))"
    # Os rótulos parecem OK
    labels = ["Nº Factura:", "N° Factura:", "Invoice Nº:", "Invoice No:", "Amendment Invoice Nº:"]
    # A chamada para _extract_by_label continua a mesma, mas agora match.group(1) funcionará
    return _extract_by_label(page, labels, pattern)

def extract_descripcion(page):
    try:
        labels = ["Descripción", "Description", "Detalle de la Factura", "Invoice detail", "Concepto"]
        end_labels = ["Impuestos repercutidos", "Output taxes", "Totales", "TOTALS", "Subtotal", "BASE IMPONIBLE", "Observaciones", "Observations", "Pag.", "Rogamos envíen"]
        desc_rect = None
        for l in labels:
            found = page.search_for(l)
            if found:
                desc_rect = found[0]
                break
        if not desc_rect:
            return "N/A"
        top_y = desc_rect.y1
        bottom_y = page.rect.height
        for el in end_labels:
            found = page.search_for(el)
            if found:
                bottom_y = min(bottom_y, found[0].y0)
        area = fitz.Rect(0, top_y, page.rect.width * 0.35, bottom_y)
        words = page.get_text("words", clip=area, sort=True)
        texts = [w[4] for w in words if not re.fullmatch(r"[\d.,\s-]+|EUR|USD|%|UN|MMBTU|IVA|VAT", w[4], re.IGNORECASE)]
        return re.sub(r'\s+', ' ', " ".join(texts)).strip()
    except:
        return "N/A"

def extract_base_imponible(page):
    return extract_valor_area(page, ["BASE IMPONIBLE", "Tax base"], label="BASE IMPONIBLE")

def extract_impuestos(page):
    return extract_valor_area(page, ["IVA repercutido", "VAT Output tax", "Cuota"], label="IMPUESTOS")

def extract_importe_total(page):
    return extract_valor_area(page, ["TOTAL importe Factura", "Invoice total value"], label="IMPORTE TOTAL")

def extract_valor_area(page, labels, label="VALOR", width_ratio=0.6, height_limit=10):
    try:
        ref_start = None
        totals_found = page.search_for("TOTALS")
        if totals_found:
            ref_start = totals_found[0].y0
        for l in labels:
            found = page.search_for(l)
            if not found:
                continue
            candidates = [r for r in found if not ref_start or r.y0 > ref_start]
            if not candidates:
                continue
            label_rect = candidates[0]
            search_rect = fitz.Rect(0, label_rect.y0 - 1, page.rect.width, label_rect.y1 + 1)
            text = page.get_text("text", clip=search_rect)
            print(f"🔍 [DEBUG] {label} - linha capturada: '{text.strip()}'")
            match = re.search(r"(-?[\d\s.,]{5,})", text)
            if match:
                return normalize_number(match.group(1))
    except Exception as e:
        print(f"⚠️ Erro ao extrair {label}: {e}")
    return None

def normalize_number(text):
    try:
        if not text:
            return None

        text = str(text).strip()
        text = re.sub(r"[€$EURUSD]", "", text).strip()

        # Detecta valor negativo com hífen no final (ex: "1,59-")
        is_negative = False
        if text.endswith('-'):
            is_negative = True
            text = text[:-1].strip()

        # Remove espaços entre dígitos
        text = re.sub(r"(?<=\d)\s+(?=\d)", "", text)

        # Trata número sem separador com 2 casas como centavos
        if re.fullmatch(r"\d{5,}", text):
            text = text[:-2] + "." + text[-2:]
        elif ',' in text and '.' in text:
            if text.rfind(',') > text.rfind('.'):
                text = text.replace('.', '').replace(',', '.')
            else:
                text = text.replace(',', '')
        elif ',' in text:
            text = text.replace(',', '.')
        elif '.' in text:
            parts = text.split('.')
            if all(len(p) == 3 for p in parts[1:]):
                text = text.replace('.', '')

        value = float(text)
        return -value if is_negative else value

    except Exception as e:
        print(f"Erro na normalização de número '{text}': {e}")
        return None



def _extract_by_label(page, labels, pattern):
    try:
        for label in labels:
            found = page.search_for(label)
            if found:
                rect = found[0]
                line_rect = fitz.Rect(0, rect.y0 - 2, page.rect.width, rect.y1 + 2)
                text = page.get_text("text", clip=line_rect)
                match = re.search(pattern, text)
                if match:
                    return match.group(1)
    except:
        pass
    return None

def validate_totals(data):
    try:
        base = data.get("BASE IMPONIBLE")
        total = data.get("IMPORTE TOTAL")
        tax = data.get("IMPUESTOS")
        if base is not None and total is not None:
            if tax is None:
                tax_calc = round(total - base, 2)
                data["IMPUESTOS"] = tax_calc
    except:
        pass
    return data

def extract_observaciones(doc):
    try:
        obs_labels = ["Observaciones", "Observations"]
        end_labels = ["Pag.", "ENDESA", "Please send proof", "Rogamos envíen"]
        for i in range(doc.page_count):
            page = doc.load_page(i)
            for label in obs_labels:
                found = page.search_for(label)
                if not found:
                    continue
                label_rect = found[0]
                search_rect = fitz.Rect(0, label_rect.y1, page.rect.width, page.rect.height)
                for end_label in end_labels:
                    found_end = page.search_for(end_label, clip=search_rect)
                    if found_end:
                        end_y = min(r.y0 for r in found_end)
                        search_rect.y1 = end_y
                        break
                blocks = page.get_text("blocks", clip=search_rect, sort=True)
                obs_text = " ".join([b[4].strip() for b in blocks if b[4].strip()])
                return re.sub(r'\s+', ' ', obs_text).strip()
        return "N/A"
    except Exception as e:
        print(f"Erro ao extrair OBSERVACIONES: {e}")
        return "N/A"

def is_special_layout(page):
    full_text = page.get_text("text")
    return ("Factura Rectificativa" in full_text) or ("TOTALS" not in full_text and "TOTALES" not in full_text)

def extract_values_for_special_layout(page):
    special_data = {}
    try:
        full_text = page.get_text("text")

        match_base = re.search(r"BASE IMPONIBLE[\s:\n]*(-?[\d.,]+-?)", full_text, re.IGNORECASE)
        if match_base:
            special_data["BASE IMPONIBLE"] = normalize_number(match_base.group(1))

        match_tax = re.search(r"repercutido[^\n\r]*(?:[\s/]+)?(-?[\d.,]+-?)", full_text, re.IGNORECASE)
        if match_tax:
            special_data["IMPUESTOS"] = normalize_number(match_tax.group(1))

        match_total = re.search(r"TOTAL Importe Factura[\s:\n]*(-?[\d.,]+-?)", full_text, re.IGNORECASE)
        if match_total:
            special_data["IMPORTE TOTAL"] = normalize_number(match_total.group(1))

        print(f"🔍 [Modelo Especial] Captura: {special_data}")
    except Exception as e:
        print(f"❌ Erro em modelo especial: {e}")
    return special_data


def extract_from_text_fallback(page):
    fallback_data = {}
    try:
        keywords = {
            "BASE IMPONIBLE": "BASE IMPONIBLE",
            "IMPUESTOS": "repercutido",
            "IMPORTE TOTAL": "TOTAL Importe Factura"
        }
        for campo, palavra in keywords.items():
            found = page.search_for(palavra)
            if found:
                rect = found[0]
                search_rect = fitz.Rect(
                    rect.x1 + 2,
                    rect.y0 - 1,
                    min(rect.x1 + 100, page.rect.width - 5),
                    rect.y1 + 1
                )
                texto_lateral = page.get_text("text", clip=search_rect)
                print(f"🔍 [Fallback DEBUG] {campo} ao lado de '{palavra}': '{texto_lateral.strip()}'")
                match = re.search(r"(-?[\d.,]+)", texto_lateral)
                if match:
                    fallback_data[campo] = normalize_number(match.group(1))
        return fallback_data
    except Exception as e:
        print(f"❌ Erro no fallback: {e}")
        return {}

def extract_moeda(page):
    """
    Procura pelo símbolo ou código de moeda mais comum na página.
    Retorna, por exemplo, '€', 'EUR', 'USD' ou None.
    """
    text = page.get_text("text")
    # Regex buscando símbolo ou sigla de moeda
    m = re.search(r"\b(€|EUR|USD|US\$)\b", text)
    return m.group(1) if m else None


def process_folder(folder_path, output_file):
    folder = Path(folder_path)
    pdf_files = sorted(folder.glob("*.pdf"))
    all_data = []

    print(f"📂 Iniciando processamento de {len(pdf_files)} arquivos PDF...")
    for pdf in pdf_files:
        print(f"🔍 Processando: {pdf.name}")
        result = extract_invoice_fields(pdf)
        all_data.append(result)

    df = pd.DataFrame(all_data)
    df.to_excel(output_file, index=False, engine="openpyxl")
    print(f"✅ Extração finalizada. Resultados salvos em: {output_file}")

# --- Execução ---
if __name__ == "__main__":
    pasta_faturas = r"C:\\Users\\BR0321808688\\OneDrive - Enel Spa\\Área de Trabalho\\2025\\PILOTO OCR\\FATURAS"
    arquivo_saida = r"C:\\Users\\BR0321808688\\OneDrive - Enel Spa\\Área de Trabalho\\2025\\PILOTO OCR\\FATURAS\\faturas_EXTRAIDAS_FINAL.xlsx"
    process_folder(pasta_faturas, arquivo_saida)
