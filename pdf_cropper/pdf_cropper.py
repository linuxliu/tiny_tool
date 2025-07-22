import tkinter as tk
from tkinter import filedialog
from pdf2image import convert_from_path
from PIL import Image, ImageTk
import PyPDF2
from PyPDF2 import PdfReader, PdfWriter
import os
from collections import OrderedDict

class PDFCropper:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Cropper (Optimized for Large PDFs)")
        self.pdf_path = None
        self.current_page = 0
        self.total_pages = 0
        self.crop_coords_per_page = {}  # Dictionary to store crop coordinates for each page
        self.global_crop_coords = None  # Store global crop coordinates
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.page_cache = OrderedDict()  # Cache for page images (LRU cache)
        self.cache_limit = 10  # Limit cache to 10 pages to control memory
        
        # Create GUI elements
        self.canvas = tk.Canvas(root, width=800, height=600, cursor="cross")
        self.canvas.pack()
        
        # File selection button
        tk.Button(root, text="Select PDF File", command=self.select_pdf_file).pack(side=tk.TOP)
        
        # Navigation and crop buttons (initially disabled)
        self.prev_button = tk.Button(root, text="Previous", command=self.prev_page, state=tk.DISABLED)
        self.prev_button.pack(side=tk.LEFT)
        self.next_button = tk.Button(root, text="Next", command=self.next_page, state=tk.DISABLED)
        self.next_button.pack(side=tk.LEFT)
        self.apply_all_button = tk.Button(root, text="Apply to All Pages", command=self.apply_to_all_pages, state=tk.DISABLED)
        self.apply_all_button.pack(side=tk.LEFT)
        self.crop_button = tk.Button(root, text="Crop PDF", command=self.crop_pdf, state=tk.DISABLED)
        self.crop_button.pack(side=tk.RIGHT)
        self.page_label = tk.Label(root, text="No PDF loaded")
        self.page_label.pack(side=tk.BOTTOM)
    
    def select_pdf_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if file_path:
            self.pdf_path = file_path
            self.load_pdf()
    
    def load_pdf(self):
        # Reset previous state
        self.page_cache.clear()
        self.total_pages = 0
        self.crop_coords_per_page = {}
        self.global_crop_coords = None
        self.current_page = 0
        self.canvas.delete("all")
        
        # Get total pages without loading images
        try:
            with open(self.pdf_path, 'rb') as f:
                pdf_reader = PdfReader(f)
                self.total_pages = len(pdf_reader.pages)
            
            # Enable buttons
            self.prev_button.config(state=tk.NORMAL)
            self.next_button.config(state=tk.NORMAL)
            self.apply_all_button.config(state=tk.NORMAL)
            self.crop_button.config(state=tk.NORMAL)
            
            # Bind mouse events for drawing rectangle
            self.canvas.bind("<ButtonPress-1>", self.start_rect)
            self.canvas.bind("<B1-Motion>", self.draw_rect)
            self.canvas.bind("<ButtonRelease-1>", self.end_rect)
            
            # Display first page
            self.display_page(self.current_page)
        
        except Exception as e:
            print(f"Error loading PDF: {str(e)}")
            self.page_label.config(text="Error loading PDF")
            self.prev_button.config(state=tk.DISABLED)
            self.next_button.config(state=tk.DISABLED)
            self.apply_all_button.config(state=tk.DISABLED)
            self.crop_button.config(state=tk.DISABLED)
    
    def load_page_image(self, page_number):
        """Load a single page image and cache it."""
        if page_number in self.page_cache:
            return self.page_cache[page_number]
        
        try:
            # Load only the specified page
            pages = convert_from_path(self.pdf_path, dpi=72, first_page=page_number + 1, last_page=page_number + 1)
            if not pages:
                raise ValueError(f"Failed to load page {page_number + 1}")
            img = pages[0]
            img = img.resize((800, 600), Image.Resampling.LANCZOS)
            
            # Cache the image
            self.page_cache[page_number] = img
            if len(self.page_cache) > self.cache_limit:
                self.page_cache.popitem(last=False)  # Remove least recently used page
            
            return img
        except Exception as e:
            print(f"Error loading page {page_number + 1}: {str(e)}")
            return None
    
    def display_page(self, page_number):
        if 0 <= page_number < self.total_pages:
            # Load page image
            img = self.load_page_image(page_number)
            if img:
                self.photo = ImageTk.PhotoImage(img)
                self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
                self.page_label.config(text=f"Page {page_number + 1}/{self.total_pages}")
                self.current_page = page_number
                
                # Draw existing crop rectangle if it exists for this page or globally
                if self.rect:
                    self.canvas.delete(self.rect)
                    self.rect = None
                if page_number in self.crop_coords_per_page:
                    x1, y1, x2, y2 = self.crop_coords_per_page[page_number]
                    self.rect = self.canvas.create_rectangle(x1, y1, x2, y2, outline="red", width=2)
                elif self.global_crop_coords:
                    x1, y1, x2, y2 = self.global_crop_coords
                    self.rect = self.canvas.create_rectangle(x1, y1, x2, y2, outline="blue", width=2)
            else:
                self.page_label.config(text=f"Error loading page {page_number + 1}")
    
    def start_rect(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2)
    
    def draw_rect(self, event):
        if self.rect and self.start_x is not None:
            curr_x = self.canvas.canvasx(event.x)
            curr_y = self.canvas.canvasy(event.y)
            self.canvas.coords(self.rect, self.start_x, self.start_y, curr_x, curr_y)
    
    def end_rect(self, event):
        curr_x = self.canvas.canvasx(event.x)
        curr_y = self.canvas.canvasy(event.y)
        # Store coordinates (x1, y1, x2, y2) for the current page
        x1, x2 = min(self.start_x, curr_x), max(self.start_x, curr_x)
        y1, y2 = min(self.start_y, curr_y), max(self.start_y, curr_y)
        self.crop_coords_per_page[self.current_page] = (x1, y1, x2, y2)
        self.start_x = None
        self.start_y = None
    
    def apply_to_all_pages(self):
        if self.current_page not in self.crop_coords_per_page:
            print("Error: No crop area selected for the current page")
            return
        # Copy current page's crop coordinates to global
        self.global_crop_coords = self.crop_coords_per_page[self.current_page]
        print("Current page's crop area applied to all pages")
        # Redraw to show global crop (blue outline)
        self.display_page(self.current_page)
    
    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.display_page(self.current_page)
    
    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.display_page(self.current_page)
    
    def crop_pdf(self):
        if not self.crop_coords_per_page and not self.global_crop_coords:
            print("Error: No crop areas selected for any page or globally")
            return
        
        # Prompt user to select output file path
        output_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Save Cropped PDF As"
        )
        if not output_path:
            print("Error: No output file selected")
            return
        
        try:
            # Open the input PDF
            pdf_reader = PdfReader(self.pdf_path)
            pdf_writer = PdfWriter()
            
            # Process each page
            for page_num, page in enumerate(pdf_reader.pages):
                # Get original page dimensions
                original_width = float(page.mediabox.right - page.mediabox.left)
                original_height = float(page.mediabox.top - page.mediabox.bottom)
                
                # Use per-page crop coordinates if available, else use global, else keep original
                if page_num in self.crop_coords_per_page:
                    x1, y1, x2, y2 = self.crop_coords_per_page[page_num]
                elif self.global_crop_coords:
                    x1, y1, x2, y2 = self.global_crop_coords
                else:
                    pdf_writer.add_page(page)
                    continue
                
                # Convert canvas coordinates to PDF coordinates
                canvas_width, canvas_height = 800, 600
                scale_x = original_width / canvas_width
                scale_y = original_height / canvas_height
                
                # Convert Tkinter canvas coordinates to PDF coordinates
                # Tkinter: y increases downward; PDF: y increases upward
                pdf_x1 = x1 * scale_x
                pdf_x2 = x2 * scale_x
                pdf_y1 = (canvas_height - y2) * scale_y  # y2 is the bottom in canvas, maps to lower Y in PDF
                pdf_y2 = (canvas_height - y1) * scale_y  # y1 is the top in canvas, maps to higher Y in PDF
                
                # Ensure coordinates are within bounds
                pdf_x1 = max(0, min(pdf_x1, original_width))
                pdf_x2 = max(0, min(pdf_x2, original_width))
                pdf_y1 = max(0, min(pdf_y1, original_height))
                pdf_y2 = max(0, min(pdf_y2, original_height))
                
                # Debug output to verify coordinates
                print(f"Page {page_num + 1}:")
                print(f"  Canvas coords: ({x1}, {y1}, {x2}, {y2})")
                print(f"  PDF coords: ({pdf_x1}, {pdf_y1}, {pdf_x2}, {pdf_y2})")
                
                # Set crop box
                page.mediabox.lower_left = (pdf_x1, pdf_y1)
                page.mediabox.upper_right = (pdf_x2, pdf_y2)
                pdf_writer.add_page(page)
            
            # Write output PDF
            with open(output_path, 'wb') as output_file:
                pdf_writer.write(output_file)
            
            print(f"PDF successfully cropped and saved as {output_path}")
        
        except FileNotFoundError:
            print("Error: Input PDF file not found")
        except Exception as e:
            print(f"Error occurred: {str(e)}")

def main():
    root = tk.Tk()
    app = PDFCropper(root)
    root.mainloop()

if __name__ == "__main__":
    main()
