# --- Stage 1: compilar el CSS de Tailwind ---
FROM node:20-slim AS css
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY tailwind.config.js ./
COPY app/static/input.css ./app/static/input.css
COPY app/templates ./app/templates
RUN npm run build:css

# --- Stage 2: imagen de la app ---
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Traer el CSS compilado del stage anterior (no se versiona en git)
COPY --from=css /build/app/static/style.css ./app/static/style.css

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
