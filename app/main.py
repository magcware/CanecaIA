import time
import base64
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from app.config import VALID_CATEGORIES
from app.openai_service import classify_image
from app.mqtt_client import publish_result

app = FastAPI(
    title="EcoClasifica API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/")
def root():
    return {
        "status": "online"
    }


@app.post("/classify")
async def classify(file: UploadFile = File(...)):

    start_time = time.time()

    try:

        image_bytes = await file.read()

        base64_image = base64.b64encode(
            image_bytes
        ).decode()

        result = classify_image(
            base64_image
        )

        if result not in VALID_CATEGORIES:
            raise ValueError(
                f"Categoría no válida: {result}"
            )

        # Publicar resultado MQTT
        publish_result(result)

        color_map = {
            "Recyclable": "blue",
            "Organic": "green",
            "NonRecyclable": "black"
        }

        end_time = time.time()

        return {
            "success": True,
            "classification": result,
            "color": color_map.get(result, "gray"),

            # NUEVO
            "processing_time_seconds": round(
                end_time - start_time,
                2
            ),

            # opcional milisegundos
            "processing_time_ms": round(
                (end_time - start_time) * 1000
            )
        }

    except Exception as e:

        end_time = time.time()

        return {
            "success": False,
            "error": str(e),
            "processing_time_seconds": round(
                end_time - start_time,
                2
            )
        }