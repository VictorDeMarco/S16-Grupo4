# Atrapa un Millón IA (Streamlit + Gemini)

Juego inspirado en **Atrapa un Millón** con dos modos:

- `custom`: el usuario define hasta 8 temas.
- `clasico`: Gemini genera 8 pares de temas (16 preguntas) en una única llamada masiva; por ronda eliges 1 tema de 2.

## Requisitos

- Python 3.11+
- Clave de API de Gemini

## Instalación

```cmd
cd /d c:\Users\danir\Desktop\UNIVERSIDAD\S16
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Configuración

1. Copia `.env.example` a `.env`.
2. Define tu clave:

```cmd
set GEMINI_API_KEY=tu_api_key
set GEMINI_MODEL=gemini-2.0-flash
```

También puedes guardar estas variables en `.env`.

## Ejecutar

```cmd
cd /d c:\Users\danir\Desktop\UNIVERSIDAD\S16
.venv\Scripts\activate
streamlit run app.py
```

## Pruebas

```cmd
cd /d c:\Users\danir\Desktop\UNIVERSIDAD\S16
.venv\Scripts\activate
pytest -q
```

## Notas de diseño

- Las apuestas se gestionan en bloques de `25,000`.
- No puedes apostar más del saldo disponible.
- Debes dejar al menos una trampilla vacía, excepto en la ronda 8.
- `fuente_busqueda` siempre es textual (sin URL).
- En modo clásico, la generación corre en segundo plano y puede cancelarse al iniciar modo custom.
