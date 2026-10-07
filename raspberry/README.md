# Canecas Inteligentes — Raspberry Pi

Este componente corre en la Raspberry Pi (o en un PC con webcam para la primera prueba). YOLO solo detecta que hay un objeto frente a la cámara. La clasificación del residuo la hace el backend existente, en `POST /classify`.

## Preparación

```bash
cd raspberry
python -m venv .venv
```

En Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

En la Raspberry Pi:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Ajusta `BACKEND_URL` en `.env` para apuntar al FastAPI. En local suele ser `http://127.0.0.1:8000`. La primera ejecución descarga `yolov8n.pt`.

## Ejecución

Con el backend en marcha:

```bash
python main.py
```

Se abre una sola ventana de kiosko, en pantalla completa. La dirección por defecto es http://127.0.0.1:8765. Ahí se ve la cámara en vivo, con el recuadro de YOLO y sin el nombre ni la confianza del objeto. Las imágenes de las canecas azul, verde y negra se asocian en `kiosk/kiosk.json`.

`Ctrl+C` cierra el programa.

Cuando un objeto se mantiene durante `CONSECUTIVE_FRAMES` por encima de `CONFIDENCE_THRESHOLD`, se guarda la foto en `captures/` junto con un JSON y se envía al backend. Durante `COOLDOWN_SECONDS` no se toma otra foto del mismo objeto.

Si el backend no responde, la imagen permanece en `captures/` y se reintenta al volver a abrir el programa.
