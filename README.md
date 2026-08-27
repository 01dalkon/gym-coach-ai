# 🏋️ GymCoach AI

Chat con IA que actúa como entrenador personal virtual: le escribes tu rutina **o le envías una foto del WOD** y te explica cada ejercicio en español, respondiendo con **GIFs animados** de los movimientos.

Embebible en cualquier app (Web, WebView móvil) con una sola línea de código.

## Cómo funciona

```
Usuario (texto o foto) → Widget de chat → API FastAPI → OpenRouter (LLM gratis con visión)
                                              ↓
                            El LLM devuelve explicación + nombres de ejercicios
                                              ↓
                     Fuzzy-match contra el dataset local (1,324 ejercicios)
                                              ↓
                     Respuesta: explicación en español + tarjetas con GIF
```

- **Backend:** Python + FastAPI
- **LLM:** NVIDIA NIM vía [build.nvidia.com](https://build.nvidia.com) (default: `google/diffusiongemma-26b-a4b-it`)
- **Dataset:** 1,324 ejercicios con GIF, músculo objetivo, equipo e instrucciones (incluido en el repo vía Git LFS)
- **Frontend:** widget de chat vanilla JS (sin dependencias), embebible vía `<script>` o `<iframe>`

## Puesta en marcha (5 minutos)

1. Crea una API key gratis en [build.nvidia.com](https://build.nvidia.com)
2. Configura el entorno:

```bash
cp .env.example .env
# edita .env y pega tu NVIDIA_API_KEY
```

3. Levanta con Docker:

```bash
docker compose up --build
```

4. Abre [http://localhost:8000](http://localhost:8000) — verás la demo con el widget flotante. El chat directo está en `/chat.html`.

> El `docker build` incluye el dataset completo (~1 GB con GIFs) vía Git LFS. Para pruebas rápidas sin dataset: `docker build --build-arg INCLUDE_DATASET=false .` (usa 8 ejercicios de ejemplo).

### Sin Docker (desarrollo local con venv)

```bash
# 1. Crea y activa el entorno virtual (venv)
python3 -m venv venv
source venv/bin/activate

# 2. Instala dependencias dentro del venv
pip install -r requirements.txt

# 3. Configura la API key
cp .env.example .env   # edita y pega tu NVIDIA_API_KEY

# 4. Levanta el servidor
uvicorn app.main:app --reload
```

Abre [http://localhost:8000](http://localhost:8000). Para salir del venv: `deactivate`.

## Embeber en cualquier app

**Opción A — script (webs):**

```html
<script src="https://TU-DOMINIO/widget.js" defer></script>
```

**Opción B — iframe (WebViews en apps móviles, como una vista dentro de App):**

```html
<iframe src="https://TU-DOMINIO/chat.html" style="width:100%;height:100%;border:none"></iframe>
```

**Opción C — solo la API** (si quieres tu propia UI nativa):

```
POST /api/chat            (multipart: message, history, image)
GET  /api/exercises/search?q=squat
GET  /health
```

## Despliegue gratuito

| Plataforma | Notas |
|---|---|
| **Hugging Face Spaces** (recomendado) | Gratis, soporta Docker directo. Crea un Space tipo "Docker", sube este repo y agrega `NVIDIA_API_KEY` como secret. Cambia `PORT=7860`. |
| **Render.com** | Free tier con Docker. Se duerme tras 15 min de inactividad. |
| **Railway / Fly.io** | Créditos gratis limitados. |

En todas: sube el repo a GitHub y conecta la plataforma → build automático del Dockerfile.

## Modelos en NVIDIA NIM (build.nvidia.com, ago 2026)

| Modelo | Nota |
|---|---|
| `google/diffusiongemma-26b-a4b-it` | Default. |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | Multimodal (imagen/video/audio). |
| `deepseek-ai/deepseek-v3.2` | Texto, muy bueno en español. |

Para producción real, cambia `NVIDIA_MODEL` a un modelo de pago sin tocar código.

## Estructura

```
gym-coach-ai/
├── app/
│   ├── main.py          # FastAPI: /api/chat, /api/exercises/search, media, estáticos
│   ├── llm.py           # Cliente NVIDIA NIM (visión + JSON estructurado)
│   └── exercises.py     # Carga del dataset + fuzzy matching (ES/EN)
├── static/
│   ├── chat.html        # UI del chat (standalone / iframe)
│   ├── widget.js        # Botón flotante embebible
│   └── index.html       # Página demo
├── data/sample_exercises.json  # Fallback para desarrollo sin dataset
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## Roadmap sugerido

- Historial persistente por usuario (SQLite/Postgres)
- Rate limiting propio + API keys por cliente (para venderlo como SaaS)
- Búsqueda semántica con embeddings (mejor matching de nombres raros de WOD)
- Traducir instrucciones del dataset a español (batch con el mismo LLM)
- Streaming de respuestas (SSE)
