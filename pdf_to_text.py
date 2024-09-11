import pytesseract
from pdf2image import convert_from_path
import os
import re
from spellchecker import SpellChecker
from difflib import get_close_matches
import spacy
from PIL import Image


# Set the image size limit for PIL to None to avoid decompression bomb errors
Image.MAX_IMAGE_PIXELS = None  

# Set the path for Tesseract OCR executable
pytesseract.pytesseract.tesseract_cmd = r'D:\Project\Tess\tesseract.exe'

# Path to Poppler's bin folder
poppler_path = r'D:\Project\Poppler\poppler-24.07.0\Library\bin'

# Set cache directory for temporary files
cache_dir = r'D:\Project\cache'
os.makedirs(cache_dir, exist_ok=True)  # Ensure the cache directory exists

# Initialize the spell checker with reduced edit distance to speed up correction
spell = SpellChecker(distance=1)  # Lower the edit distance to speed up

# Load the D&D monster whitelist from the text file
whitelist_path = r'D:\Project\dnd_monster_whitelist.txt'
with open(whitelist_path, 'r') as f:
    dnd_whitelist = set(line.strip() for line in f)

# Load Spacy's English language model
nlp = spacy.load("en_core_web_sm")
nlp.max_length = 2000000  # Set a higher text limit

# Function to check if a word is close to a monster name in the whitelist
def is_word_in_whitelist(word):
    close_matches = get_close_matches(word, dnd_whitelist, n=1, cutoff=0.8)
    return bool(close_matches)

# Function to convert PDF pages to images and run OCR on each page
def ocr_pdf_to_text(pdf_path):
    try:
        # Convert PDF pages to images using poppler_path and specify cache directory
        print(f"Converting PDF to images for: {pdf_path}")
        images = convert_from_path(pdf_path, poppler_path=poppler_path, output_folder=cache_dir)
        
        full_text = ""
        for page_num, image in enumerate(images, start=1):
            try:
                # Use OCR to extract text from each page image
                print(f"Processing page {page_num} of {pdf_path}")
                ocr_text = pytesseract.image_to_string(image)
                full_text += f"--- Page {page_num} ---\n{ocr_text}\n"
            except Exception as img_error:
                print(f"Error processing page {page_num} in {pdf_path}: {img_error}")
        
        return full_text
    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")
        return None

# Function to clean up and spell-check the extracted text
def clean_and_spellcheck_text(text):
    # Remove multiple periods, asterisks, or other redundant characters
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'·+', '', text)
    
    # Remove multiple spaces and newlines
    text = re.sub(r'\n{2,}', '\n', text)  # Reduce multiple newlines to one
    text = re.sub(r'\s{2,}', ' ', text)   # Reduce multiple spaces to one

    # Apply basic punctuation fixes using regex
    text = re.sub(r'(?<=[a-z])(?=[A-Z])', '. ', text)  # Add a period between a lowercase and uppercase letter
    text = re.sub(r'(?<=[0-9])(?=[A-Z])', '. ', text)  # Add a period after a number if the next letter is uppercase
    text = re.sub(r'\s*\n', '.\n', text)               # Add periods at the end of lines that are sentence-like

    # Use Spacy to segment the text into sentences
    doc = nlp(text)
    sentences = [sent.text for sent in doc.sents]

    # Rebuild the cleaned and spell-checked text with better structure
    corrected_text = []
    for sentence in sentences:
        words = sentence.split()
        corrected_sentence = []
        for word in words:
            if word in dnd_whitelist or is_word_in_whitelist(word):  # Check if word is in whitelist
                corrected_sentence.append(word)  # Skip D&D words
            elif len(word) > 15 or re.search(r'\d', word):  # Skip overly long words and those with numbers
                corrected_sentence.append(word)
            else:
                corrected_word = word
                try:
                    misspelled = spell.unknown([word])
                    if misspelled:
                        correction = spell.correction(word)
                        corrected_word = correction if correction else word  # Replace with corrected word if available
                except Exception as e:
                    print(f"Error correcting word '{word}': {e}")
                    corrected_word = word
                corrected_sentence.append(corrected_word)
        corrected_text.append(' '.join(corrected_sentence))
    
    # Join the sentences back into paragraphs
    return '\n\n'.join(corrected_text)  # Use double newlines for paragraph separation

# Function to process each PDF, extract text via OCR, clean, spell-check it, and save as .txt
def process_pdf_file(pdf_path, txt_output_folder):
    # Ensure absolute paths are used
    pdf_path = os.path.abspath(pdf_path)
    txt_output_folder = os.path.abspath(txt_output_folder)

    # Extract the base name of the PDF (without extension)
    base_name = os.path.basename(pdf_path).replace('.pdf', '')
    
    # Path to the corresponding .txt file
    txt_file_path = os.path.join(txt_output_folder, f"{base_name}.txt")

    # Check if the .txt file already exists
    if os.path.exists(txt_file_path):
        print(f"Skipping {pdf_path}, text file already exists: {txt_file_path}")
        return  # Skip this file if the text file already exists

    print(f"Processing file: {pdf_path}")

    # Extract the text from the PDF using OCR
    extracted_text = ocr_pdf_to_text(pdf_path)
    
    # If extraction was successful, proceed to clean, spell-check, and save the text
    if extracted_text:
        cleaned_text = clean_and_spellcheck_text(extracted_text)
        
        # Save the cleaned and spell-checked text to a file
        with open(txt_file_path, 'w', encoding='utf-8') as txt_file:
            txt_file.write(cleaned_text)
        
        print(f"Text extracted, cleaned, and spell-checked for {pdf_path} and saved to {txt_file_path}")
    else:
        print(f"Failed to process {pdf_path}")

# Function to process all PDF files in a folder
def process_pdf_folder(pdf_folder, txt_output_folder):
    # Ensure absolute paths are used
    pdf_folder = os.path.abspath(pdf_folder)
    txt_output_folder = os.path.abspath(txt_output_folder)

    # Ensure the output folder exists
    if not os.path.exists(txt_output_folder):
        os.makedirs(txt_output_folder)

    # Check for PDF files in the folder
    print(f"Scanning folder for PDF files: {pdf_folder}")
    pdf_files = [f for f in os.listdir(pdf_folder) if f.endswith(".pdf")]
    if not pdf_files:
        print("No PDF files found.")
        return
    
    # Loop through all PDF files in the folder and process them
    for file_name in pdf_files:
        pdf_path = os.path.join(pdf_folder, file_name)
        process_pdf_file(pdf_path, txt_output_folder)

# Folder where the PDFs are located
pdf_folder_path = r"E:\D&D\Books"

# Folder where the cleaned .txt files will be saved
txt_output_folder_path = r"E:\D&D\Books\Text"

# Process the folder
process_pdf_folder(pdf_folder_path, txt_output_folder_path)
