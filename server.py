import io
import cv2
import numpy as np
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
    _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return base64.b64encode(buffer).decode('utf-8')

@app.get("/images")
async def get_images():
    if not ASSETS_DIR.exists():
        return []
    images = [f.name for f in ASSETS_DIR.iterdir() if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.tif', '.tiff']]
    return images

@app.post("/run-pipeline")
async def run_pipeline_api(
    image: UploadFile = File(None), 
    image_name: str = Form(None),
    clip: float = Form(3.0), 
    tile: int = Form(8)
):
    img = None
    if image is not None and hasattr(image, "read") and getattr(image, "filename", None):
        contents = await image.read()
        img = decode_image(contents)
    elif image_name and (ASSETS_DIR / image_name).exists():
        img = decode_image(ASSETS_DIR / image_name)
    else:
        return JSONResponse(status_code=400, content={"error": "No image provided. Please choose a sample swath or select a file to upload."})
        
    if img is None:
        return JSONResponse(status_code=400, content={"error": "Could not decode the provided image. Please upload a valid JPG, PNG, or TIFF image file."})

    # Resize large images to speed up processing significantly
    max_dim = 1024
    h, w = img.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / float(max(h, w))
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    psr, norm, clahe = preprocess_pipeline(img, clahe_clip=clip, clahe_tile=(tile, tile))
    den = run_all_denoisers(clahe)
    
    metrics = {}
    results = {}
    
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
            "clahe": encode_img(clahe)
        },
        "results": results,
        "ranking": ranking,
        "best_method": best_method,
        "illumination_map": encode_img(colorized_bgr)
    }

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
