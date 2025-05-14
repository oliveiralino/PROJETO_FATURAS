import tkinter as tk
from tkinter import filedialog, messagebox, Listbox, Scrollbar
import threading
import os
from pathlib import Path
import logging
import fitz  # PyMuPDF
import pandas as pd
import numpy
import paddleocr
import sys 


# Import módulos de extração
import script_digital  #  script para faturas digitais
import script_ocr    #  script para faturas OCR

# Configuração logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s')

import logging
logging.basicConfig(
    level=logging.DEBUG,
    filename="extratorfaturas.log",
    filemode="w",
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Variáveis de controle globais para GUI
pasta_pdfs_var = None
arquivo_saida_var = None
file_listbox = None
status_label = None
root = None

# Função para definir os caminhos dos modelos
def get_model_paths():
    """
    Define os caminhos para os modelos PaddleOCR, considerando se o código está
    rodando dentro de um executável congelado (PyInstaller).
    """
    base_model_dir = "paddle_models"  # Diretório base dos modelos

    if getattr(sys, 'frozen', False):
        # Código está rodando dentro do .exe
        base_dir = os.path.dirname(sys.executable)
        model_dir = os.path.join(base_dir, base_model_dir)
    else:
        # Código está rodando como script
        model_dir = base_model_dir

    # Certifique-se de que o caminho existe!
    if not os.path.isdir(model_dir):
        logging.error(f"Diretório de modelos não encontrado: {model_dir}")
        # messagebox.showerror("Erro", f"Diretório de modelos não encontrado: {model_dir}\nCertifique-se de que a pasta 'paddle_models' está no mesmo diretório do executável.")
        return None, None, None, None # Retorna None para indicar erro

    det_model_dir = os.path.join(model_dir, 'det')
    rec_model_dir = os.path.join(model_dir, 'rec')
    cls_model_dir = os.path.join(model_dir, 'cls')
    layout_model_dir = os.path.join(model_dir, 'layout') # Adicionado o diretório layout

    # Verificando se os diretorios existem
    if not all([os.path.isdir(det_model_dir), os.path.isdir(rec_model_dir), os.path.isdir(cls_model_dir), os.path.isdir(layout_model_dir)]):
         logging.error(f"Diretorio de modelos det: {det_model_dir}")
         logging.error(f"Diretorio de modelos rec: {rec_model_dir}")
         logging.error(f"Diretorio de modelos cls: {cls_model_dir}")
         logging.error(f"Diretorio de modelos layout: {layout_model_dir}")
         # messagebox.showerror("Erro", "Um ou mais diretórios de modelos PaddleOCR não foram encontrados.\nCertifique-se de que a estrutura de diretórios dentro de 'paddle_models' está correta (det, rec, cls, layout).")
         return None, None, None, None

    return det_model_dir, rec_model_dir, cls_model_dir, layout_model_dir

# Inicialização do PaddleOCR
det_model_dir, rec_model_dir, cls_model_dir, layout_model_dir = get_model_paths()
if det_model_dir and rec_model_dir and cls_model_dir and layout_model_dir:
    try:
        ocr = paddleocr.PaddleOCR(
            use_angle_cls=True,
            lang='en',
            det_model_dir=det_model_dir,
            rec_model_dir=rec_model_dir,
            cls_model_dir=cls_model_dir,
            layout_model_dir = layout_model_dir, # Adicionado
            show_log=False # Desativa o log do PaddleOCR
            #device = 'cpu' # Forçar CPU se necessário (teste)
        )
        logging.info("PaddleOCR inicializado com sucesso usando modelos locais.")

    except Exception as e:
        logging.error(f"Erro ao inicializar PaddleOCR: {e}")
        # messagebox.showerror("Erro", f"Erro ao inicializar PaddleOCR.\nVerifique os logs para mais detalhes.\n{e}")
        ocr = None  # Define ocr como None para evitar erros posteriores
else:
    ocr = None

# Funções GUI
def selecionar_pasta_pdfs():
    global pasta_pdfs_var, file_listbox # Assegura que estamos usando as globais
    folder = filedialog.askdirectory(title="Select PDFs folder: ")
    if folder:
        pasta_pdfs_var.set(folder)
        atualizar_listbox(folder)

def selecionar_arquivo_saida():
    global arquivo_saida_var # Assegura que estamos usando a global
    file = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                       filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                                       title="Save result as: ")
    if file:
        arquivo_saida_var.set(file)

def atualizar_listbox(folder_path):
    global file_listbox # Assegura que estamos usando a global
    if file_listbox:
        file_listbox.delete(0, tk.END)
        try:
            for f in sorted(Path(folder_path).glob("*.pdf")):
                file_listbox.insert(tk.END, f.name)
        except Exception as e:
            logging.error(f"Error listing files in the folder {folder_path}: {e}")
            # messagebox.showerror("Folder Error", f"Could not list files in the folder: {folder_path}\n{e}")


def iniciar_extracao_gui():
    global pasta_pdfs_var, arquivo_saida_var, status_label # Assegura que estamos usando as globais

    folder = pasta_pdfs_var.get().strip()
    output_file_path = arquivo_saida_var.get().strip()

    if not folder or not os.path.isdir(folder):
        messagebox.showerror("Input Error", "Please select a valid PDF folder.")
        return
    if not output_file_path:
        messagebox.showerror("Input Error", "Please select an output file.")
        return

    status_label.config(text="Processing... Please wait.", fg="blue")
    # Para garantir que a GUI atualize antes da thread começar
    if root:
        root.update_idletasks()

    # Executa a extração em uma thread separada para não bloquear a GUI
    thread = threading.Thread(target=run_extraction_wrapper, args=(folder, output_file_path), daemon=True)
    thread.start()


def detect_pdf_type(pdf_path: Path) -> str:
    """
    Detecta se um PDF é primariamente 'Digital' (baseado em texto) ou requer 'OCR' (imagem).
    Critérios atuais:
    - Digital: se a primeira página tiver mais de 100 "palavras" (blocos de texto).
    - OCR: se a primeira página tiver mais de 2 imagens E menos de 50 "palavras".
    - Fallback: 'Digital' (pode ser ajustado para 'OCR' se for um fallback mais seguro).
    """
    try:
        doc = fitz.open(str(pdf_path)) # fitz.open aceita string ou Path
        if not doc.page_count:
            logging.warning(f"PDF sem páginas: {pdf_path.name}. Assumindo OCR.")
            doc.close()
            return 'OCR'

        page = doc.load_page(0)  # Analisa apenas a primeira página para rapidez
        
        # Usar get_text("blocks") pode ser mais robusto que "words" para contar unidades de texto significativas
        # blocks retorna tuplas (x0, y0, x1, y1, "text", block_no, block_type)
        # block_type = 0 para texto, 1 para imagem
        text_blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
        num_text_elements = len(text_blocks) # Conta blocos de texto não vazios

        images = page.get_images(full=True)
        num_images = len(images)
        doc.close()

        logging.debug(f"Análise de {pdf_path.name}: Text Elements={num_text_elements}, Images={num_images}")

        # Critérios de decisão (ajuste os limiares conforme necessário)
        if num_text_elements > 70:  # Se tiver bastante texto, é provável que seja digital
            logging.info(f"Arquivo '{pdf_path.name}' detectado como: Digital (textos: {num_text_elements})")
            return 'Digital'
        if num_images > 0 and num_text_elements < 20: # Se tiver imagens e muito pouco texto
            logging.info(f"Arquivo '{pdf_path.name}' detectado como: OCR (textos: {num_text_elements}, imagens: {num_images})")
            return 'OCR'
        
        # Fallback: Se não for claramente um ou outro, pode ser um digital "pobre" ou um OCR com algum texto.
        # Dependendo dos seus arquivos, pode ser melhor assumir OCR como fallback se 'Digital' falhar.
        # Por ora, mantendo o seu fallback original se ajustado ao novo critério.
        # Se tiver algum texto mas não muito, e poucas/nenhuma imagem, ainda tentar digital.
        if num_text_elements >= 20 :
             logging.info(f"Arquivo '{pdf_path.name}' detectado como: Digital (fallback - algum texto: {num_text_elements})")
             return 'Digital'

        logging.info(f"Arquivo '{pdf_path.name}' detectado como: OCR (fallback final - pouco texto: {num_text_elements})")
        return 'OCR' # Fallback final para OCR se muito pouco texto

    except Exception as e:
        logging.error(f"Erro ao detectar tipo do PDF '{pdf_path.name}': {e}. Assumindo OCR como fallback.")
        if doc: # Garante que o documento seja fechado se a exceção ocorrer após a abertura
            doc.close()
        return 'OCR' # Fallback em caso de erro na detecção

def run_extraction_wrapper(folder, output_file):
    """ Wrapper para chamar run_extraction e atualizar a GUI no final """
    global status_label
    try:
        all_results = run_extraction(folder, output_file)

        # Salvar Excel
        if all_results: # Somente salva se houver resultados (mesmo que sejam erros)
            df = pd.DataFrame(all_results)
            df.to_excel(output_file, index=False, engine='openpyxl')
            success_msg = f"Extração concluída! {len(all_results)} arquivos processados. Salvo em: {output_file}"
            logging.info(success_msg)
            status_label.config(text="Extração concluída!", fg="green")
            messagebox.showinfo("Concluído", success_msg)
        else:
            info_msg = "Nenhum arquivo PDF encontrado ou processado na pasta."
            logging.info(info_msg)
            status_label.config(text=info_msg, fg="orange")
            messagebox.showinfo("Concluído", info_msg)

    except Exception as e:
        error_msg = f"Erro geral durante a extração ou ao salvar o Excel: {e}"
        logging.error(error_msg, exc_info=True) # Loga o traceback completo
        status_label.config(text="Erro na extração!", fg="red")
        # messagebox.showerror("Erro Crítico", error_msg)


def run_extraction(folder_path_str: str, output_file_path_str: str) -> list:
    """
    Processa os PDFs em uma pasta, detecta seu tipo e chama o script de extração apropriado.
    """
    global status_label, root # Para atualizar a GUI

    all_extracted_data = []
    folder_path = Path(folder_path_str)
    pdf_files = sorted(list(folder_path.glob("*.pdf")))

    if not pdf_files:
        logging.warning(f"Nenhum arquivo PDF encontrado em '{folder_path_str}'.")
        return all_extracted_data

    logging.info(f"Iniciando extração para {len(pdf_files)} arquivos em '{folder_path_str}'.")

    for i, pdf_path in enumerate(pdf_files):
        current_file_msg = f"Processando {i+1}/{len(pdf_files)}: {pdf_path.name}"
        logging.info(current_file_msg)
        if status_label and root:
            status_label.config(text=current_file_msg, fg="blue")
            root.update_idletasks() # Força a atualização da GUI

        dados_fatura = {"ARQUIVO": pdf_path.name, "SOURCE_DETECTION": "Indefinido", "SOURCE_EXTRACTION": "Nenhum"}
        
        try:
            tipo_fatura = detect_pdf_type(pdf_path)
            dados_fatura["SOURCE_DETECTION"] = tipo_fatura

            if tipo_fatura == 'Digital':
                logging.info(f"Chamando script_digital para: {pdf_path.name}")
                # Seu script_digital.py tem extract_invoice_fields(pdf_path)
                extracted_data_digital = script_digital.extract_invoice_fields(str(pdf_path))
                if extracted_data_digital:
                    dados_fatura.update(extracted_data_digital) # Combina os dicionários
                    dados_fatura["SOURCE_EXTRACTION"] = "Digital"
                else:
                    dados_fatura["ERRO"] = "Extrator digital não retornou dados."
                    dados_fatura["SOURCE_EXTRACTION"] = "Digital (Falhou)"
            
            elif tipo_fatura == 'OCR':
                logging.info(f"Chamando script_ocr para: {pdf_path.name}")
                # Suposição: script_ocr.py tem processar_pdf_ocr(pdf_path)
                # Ajuste o nome da função se for diferente no seu script_ocr.py
                extracted_data_ocr = script_ocr.processar_pdf_ocr(str(pdf_path))
                if extracted_data_ocr:
                    dados_fatura.update(extracted_data_ocr)
                    dados_fatura["SOURCE_EXTRACTION"] = "OCR"
                else:
                    dados_fatura["ERRO"] = "Extrator OCR não retornou dados."
                    dados_fatura["SOURCE_EXTRACTION"] = "OCR (Falhou)"
            else:
                # Caso detect_pdf_type retorne algo inesperado (não deveria acontecer com a lógica atual)
                logging.error(f"Tipo de fatura desconhecido '{tipo_fatura}' para {pdf_path.name}.")
                dados_fatura["ERRO"] = f"Tipo de detecção desconhecido: {tipo_fatura}"
            
            # Verifica se houve um erro durante a extração, mesmo que os dados tenham sido parcialmente preenchidos
            if "ERRO" in dados_fatura and dados_fatura.get("ERRO"):
                 logging.warning(f"Processado com erro {pdf_path.name}: {dados_fatura['ERRO']}")
            else:
                 logging.info(f"{pdf_path.name} processado com sucesso via {dados_fatura['SOURCE_EXTRACTION']}.")

        except Exception as e:
            logging.error(f"Exceção ao processar o arquivo '{pdf_path.name}': {e}", exc_info=True)
            dados_fatura["ERRO"] = f"Exceção: {str(e)}"
            dados_fatura["SOURCE_EXTRACTION"] = "Falha Geral"
        
        all_extracted_data.append(dados_fatura)

    return all_extracted_data


def create_gui():
    global pasta_pdfs_var, arquivo_saida_var, file_listbox, status_label, root

    root = tk.Tk()
    root.title("Invoice data extracion")
    root.geometry("600x450") # Tamanho inicial um pouco maior

    pasta_pdfs_var = tk.StringVar()
    arquivo_saida_var = tk.StringVar()

    main_frame = tk.Frame(root, padx=10, pady=10)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Configuração de Grid para responsividade
    main_frame.columnconfigure(1, weight=1) # Coluna do Entry expande

    # Seletor de Pasta de PDFs
    tk.Label(main_frame, text="PDFs folder:").grid(row=0, column=0, sticky="w", pady=5, padx=5)
    entry_pasta_pdfs = tk.Entry(main_frame, textvariable=pasta_pdfs_var, width=50)
    entry_pasta_pdfs.grid(row=0, column=1, sticky="ew", pady=5, padx=5)
    btn_selecionar_pasta = tk.Button(main_frame, text="Selecionar Pasta", command=selecionar_pasta_pdfs)
    btn_selecionar_pasta.grid(row=0, column=2, sticky="e", pady=5, padx=5)

    # Seletor de Arquivo de Saída
    tk.Label(main_frame, text="Save file in:").grid(row=1, column=0, sticky="w", pady=5, padx=5)
    entry_arquivo_saida = tk.Entry(main_frame, textvariable=arquivo_saida_var, width=50)
    entry_arquivo_saida.grid(row=1, column=1, sticky="ew", pady=5, padx=5)
    btn_selecionar_saida = tk.Button(main_frame, text="Selecionar Arquivo", command=selecionar_arquivo_saida)
    btn_selecionar_saida.grid(row=1, column=2, sticky="e", pady=5, padx=5)

    # Botão Iniciar
    btn_iniciar = tk.Button(main_frame, text="Starting extraction", command=iniciar_extracao_gui, bg="lightblue", font=("Arial", 10, "bold"))
    btn_iniciar.grid(row=2, column=0, columnspan=3, pady=15, ipady=5) # ipady para altura interna

    # Status Label
    status_label = tk.Label(main_frame, text="Waiting...", fg="blue", wraplength=550, justify=tk.LEFT) 
    status_label.grid(row=3, column=0, columnspan=3, sticky="ew", pady=5)

    # Listbox para mostrar arquivos
    tk.Label(main_frame, text="Files in the selected folder:").grid(row=4, column=0, columnspan=3, sticky="w", pady=(10,0))
    listbox_frame = tk.Frame(main_frame)
    listbox_frame.grid(row=5, column=0, columnspan=3, sticky="nsew", pady=5)
    main_frame.rowconfigure(5, weight=1) 
    listbox_frame.columnconfigure(0, weight=1) 

    file_listbox = Listbox(listbox_frame, width=70, height=10) 
    file_listbox.grid(row=0, column=0, sticky="nsew")

    scrollbar = Scrollbar(listbox_frame, orient="vertical", command=file_listbox.yview)
    scrollbar.grid(row=0, column=1, sticky="ns")
    file_listbox.config(yscrollcommand=scrollbar.set)

    root.mainloop()

if __name__ == "__main__":
    create_gui()
