import io
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Headless mode for server
import matplotlib.pyplot as plt
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import base64

from pipeline.preprocess import preprocess_pipeline
from pipeline.denoise import run_all_denoisers
from pipeline.metrics import compute_all_metrics, compute_weighted_score, rank_methods

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"
FRONTEND_DIR = BASE_DIR / "frontend"

# Static files mounted at end of file

def decode_image(data_or_path) -> np.ndarray:
    """Robustly decode image bytes or filepath into a standard BGR uint8 ndarray."""
    img = None
    if isinstance(data_or_path, bytes):
        if not data_or_path:
            return None
        arr = np.frombuffer(data_or_path, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
        if img is None:
            try:
                from PIL import Image
                pil_img = Image.open(io.BytesIO(data_or_path)).convert('RGB')
                img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            except Exception:
                img = None
    elif isinstance(data_or_path, (str, Path)):
        img = cv2.imread(str(data_or_path), cv2.IMREAD_UNCHANGED)
        if img is None:
            try:
                from PIL import Image
                pil_img = Image.open(str(data_or_path)).convert('RGB')
                img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            except Exception:
                img = None

    if img is None:
        return None

    # Handle 16-bit or floating-point images
    if img.dtype == np.uint16:
        img = (img / 256).astype(np.uint8)
    elif img.dtype.kind == 'f':
        img = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    elif img.dtype != np.uint8:
        img = np.clip(img, 0, 255).astype(np.uint8)

    # Handle channels
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    elif img.ndim == 3 and img.shape[2] == 1:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    return img

def encode_img(img: np.ndarray) -> str:
    if img.dtype.kind == 'f':
        img = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    elif img.dtype != np.uint8:
        img = np.clip(img, 0, 255).astype(np.uint8)
    _, buffer = cv2.imencode('.png', img)
    return base64.b64encode(buffer).decode('utf-8')

@app.get("/images")
async def get_images():
    if not ASSETS_DIR.exists():
        return []
    images = [f.name for f in ASSETS_DIR.iterdir() if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.tif', '.tiff']]
    return images

import xml.etree.ElementTree as ET

@app.get("/metadata/{image_name}")
async def get_metadata(image_name: str):
    """Parses corresponding PDS4 XML label to extract metadata."""
    if not ASSETS_DIR.exists():
        return JSONResponse(status_code=404, content={"error": "Assets directory not found"})
    
    # Try to find corresponding xml
    # E.g., ch2_ohr_ncp_20260103T1005176450_b_brw_d18.png -> ch2_ohr_ncp_20260103T1005176450_d_img_d18.xml
    base = image_name.rsplit('_b_brw_', 1)
    if len(base) == 2:
        xml_name = base[0] + "_d_img_" + base[1].rsplit('.', 1)[0] + ".xml"
    else:
        # Fallback for generic files
        xml_name = image_name.rsplit('.', 1)[0] + ".xml"
        
    xml_path = ASSETS_DIR / xml_name
    if not xml_path.exists():
        return {"available": False, "message": "No metadata XML found"}
        
    try:
        # Parse PDS4 XML
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # XML Namespaces in PDS4 are often used, we use a simple generic find approach 
        # that ignores namespaces by checking tag ends.
        def find_val(name):
            for elem in root.iter():
                if elem.tag.endswith('}'+name) or elem.tag == name:
                    return elem.text
            return "N/A"
            
        metadata = {
            "available": True,
            "start_date_time": find_val("start_date_time"),
            "orbit_number": find_val("imaging_orbit_number"),
            "latitude": find_val("upper_left_latitude"),
            "longitude": find_val("upper_left_longitude"),
            "incidence_angle": find_val("solar_incidence"),
            "emission_angle": find_val("sun_elevation")  # using elevation as a proxy/additional metric
        }
        return metadata
    except Exception as e:
        return {"available": False, "error": str(e)}

def generate_histogram_plot(raw_img: np.ndarray, clahe_img: np.ndarray) -> str:
    """Generates a high-resolution base64 encoded matplotlib histogram comparing raw and CLAHE intensities."""
    # Ensure 1D arrays of floats [0,1]
    raw_flat = raw_img.flatten()
    clahe_flat = clahe_img.flatten()

    fig, ax = plt.subplots(figsize=(11, 4.6), facecolor='#080A0F', dpi=140)
    ax.set_facecolor('#0c1018')
    
    # Plot histograms
    ax.hist(
        raw_flat, 
        bins=256, 
        range=(0, 1), 
        color='#4A6FA5', 
        alpha=0.55, 
        edgecolor='#6B90C4',
        linewidth=0.5,
        label='Raw PSR Input (Normalized)', 
        density=True
    )
    ax.hist(
        clahe_flat, 
        bins=256, 
        range=(0, 1), 
        color='#D4AF37', 
        alpha=0.65, 
        edgecolor='#F5D061',
        linewidth=0.5,
        label='CLAHE Adaptive Contrast Enhanced', 
        density=True
    )
    
    # Grid & Spines
    ax.grid(True, linestyle='--', linewidth=0.6, alpha=0.18, color='#ffffff')
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color('#252E3E')
        spine.set_linewidth(0.8)
    
    # Styling
    ax.set_title('Pixel Radiance Distribution: Raw PSR vs. CLAHE Contrast Expansion', color='#F5F5F7', fontsize=12.5, fontweight='bold', pad=14)
    ax.set_xlabel('Normalized Pixel Intensity [0.0 = Deep Shadow / Noise Floor, 1.0 = Sunlight Peak]', color='#A1A1A6', fontsize=9.5, labelpad=8)
    ax.set_ylabel('Relative Frequency Density', color='#A1A1A6', fontsize=9.5, labelpad=8)
    ax.tick_params(axis='x', colors='#A1A1A6', labelsize=9)
    ax.tick_params(axis='y', colors='#A1A1A6', labelsize=9)
    
    # Legend
    legend = ax.legend(facecolor='#141924', edgecolor='#2F3A4E', labelcolor='#F5F5F7', fontsize=9.5, loc='upper right', framealpha=0.95)
    for text in legend.get_texts():
        text.set_color('#F5F5F7')

    plt.tight_layout()
    
    # Save to base64
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=140, bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')



@app.post("/run-pipeline")
async def run_pipeline_api(
    image: UploadFile = File(None), 
    image_name: str = Form(None),
    clip: float = Form(3.0), 
    tile: int = Form(8),
    crop_x: float = Form(50.0),
    crop_y: float = Form(50.0)
):
    img = None
    context = None
    if image is not None and hasattr(image, "read") and getattr(image, "filename", None):
        contents = await image.read()
        img = decode_image(contents)
    elif image_name and (ASSETS_DIR / image_name).exists():
        # Load the full image directly (no crop)
        img = decode_image(ASSETS_DIR / image_name)
    else:
        return JSONResponse(status_code=400, content={"error": "No image provided. Please choose a sample swath or select a file to upload."})
        
    if img is None:
        return JSONResponse(status_code=400, content={"error": "Could not decode the provided image. Please upload a valid JPG, PNG, or TIFF image file."})

    psr, norm, clahe = preprocess_pipeline(img, clahe_clip=clip, clahe_tile=(tile, tile))
    den = run_all_denoisers(clahe)
    
    metrics = {}
    results = {}
    
    # Compute baseline metrics (CLAHE vs Norm) for delta calculations
    baseline_metrics = compute_all_metrics(norm, clahe)
    baseline_metrics["_score"] = compute_weighted_score(baseline_metrics)
    
    for name, r in den.items():
        m = compute_all_metrics(norm, r["image"])
        m["_score"] = compute_weighted_score(m)
        m["_time"] = r["time_s"]
        metrics[name] = m
        results[name] = {
            "image": encode_img(r["image"]),
            "metrics": m
        }
        
    ranking = rank_methods(metrics)
    best_method = ranking[0][0]
    
    # Generate Illumination Map
    best_img = den[best_method]["image"]
    best_img_u8 = (np.clip(best_img, 0, 1) * 255).astype(np.uint8)
    colorized_bgr = cv2.applyColorMap(best_img_u8, cv2.COLORMAP_INFERNO)
    
    return {
        "preprocessing": {
            "original": encode_img(psr),
            "normalized": encode_img(norm),
            "clahe": encode_img(clahe),
            "histogram_plot": generate_histogram_plot(norm, clahe),
            "baseline_metrics": baseline_metrics
        },
        "results": results,
        "ranking": ranking,
        "best_method": best_method,
        "illumination_map": encode_img(colorized_bgr),
        "context": context
    }

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
