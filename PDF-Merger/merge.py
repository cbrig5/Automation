from pypdf import PdfWriter
import os

merger = PdfWriter()

path = './pdfs'

for pdf in os.listdir(path):
    
    pdf_path = os.path.join(path, pdf)

    if pdf_path.endswith('.pdf'):
        merger.append(pdf_path)

merger.write("./merged_pdfs/merged-pdf.pdf")
merger.close()