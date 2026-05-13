import asyncio
import base64
import os

import streamlit as st
import streamlit.components.v1 as components

try:
    import edge_tts
except Exception:
    edge_tts = None


async def _asegurar_intro_estatica(texto: str, archivo_salida: str) -> None:
    """Genera y guarda de forma estática el audio de introducción si no existe.

    Args:
        texto: Texto a sintetizar para la introducción.
        archivo_salida: Ruta donde guardar el MP3.

    Returns:
        None
    """

    os.makedirs(os.path.dirname(archivo_salida), exist_ok=True)
    if not os.path.exists(archivo_salida):
        voz = "es-ES-AlvaroNeural"
        communicate = edge_tts.Communicate(texto, voz)
        await communicate.save(archivo_salida)


def _render_audio_html(src: str, audio_id: str, *, loop: bool = False, volume: float | None = None) -> None:
        """Inserta HTML que reproduce audio en la página Streamlit.

        Args:
                src: URL o data URI del audio.
                audio_id: Identificador HTML para el elemento audio.
                loop: Si el audio debe repetirse en bucle.
                volume: Volumen entre 0.0 y 1.0, si se desea forzar.

        Returns:
                None
        """

        loop_attr = " loop" if loop else ""
        volume_js = f"try {{ audio.volume = {volume}; }} catch (e) {{}}" if volume is not None else ""
        html = f"""
        <div style="display:none">
            <audio id="{audio_id}" autoplay{loop_attr}>
                <source src="{src}" type="audio/mp3">
            </audio>
        </div>
        <script>
            (function() {{
                const audio = document.getElementById('{audio_id}');
                if (!audio) return;
                {volume_js}
                audio.play().catch(() => {{}});
            }})();
        </script>
        """
        components.html(html, height=0)


async def _generar_audio_en_memoria(texto: str) -> bytes:
    """Genera audio TTS en memoria usando `edge_tts`.

    Args:
        texto: Texto a sintetizar.

    Returns:
        Bytes del MP3 sintetizado.
    """

    voz = "es-ES-AlvaroNeural"
    communicate = edge_tts.Communicate(texto, voz)

    audio_bytes = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_bytes += chunk["data"]
    return audio_bytes


def _reproducir_bytes_automatico(audio_bytes: bytes) -> None:
    """Inserta HTML para reproducir directamente bytes de audio (base64).

    Args:
        audio_bytes: Contenido binario del MP3.

    Returns:
        None
    """

    b64 = base64.b64encode(audio_bytes).decode()
    codigo_html = f"""
        <audio autoplay="true">
        <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        """
    st.markdown(codigo_html, unsafe_allow_html=True)


def play_intro_once(texto: str = "Bienvenidos a Atrapa un Millón IA. Preparando partida...") -> None:
    """Reproduce una introducción de bienvenida una sola vez por sesión.

    Si el audio ya existe en `assets/audio/intro.mp3` lo reutiliza, si no lo genera.

    Args:
        texto: Texto de la introducción.

    Returns:
        None
    """

    if edge_tts is None:
        return
    if st.session_state.get("intro_reproducida", False):
        return
    with st.spinner("Preparando la presentación..."):
        intro_path = os.path.join("assets", "audio", "intro.mp3")
        asyncio.run(_asegurar_intro_estatica(texto, intro_path))
        with open(intro_path, "rb") as file:
            intro_b64 = base64.b64encode(file.read()).decode()
        _render_audio_html(f"data:audio/mp3;base64,{intro_b64}", "introAudio", volume=0.9)
        st.session_state["intro_reproducida"] = True


def speak_text(texto: str) -> None:
    """Sintetiza y reproduce texto de forma inmediata en la UI.

    Args:
        texto: Texto a sintetizar y reproducir.

    Returns:
        None
    """

    if edge_tts is None:
        return
    try:
        audio = asyncio.run(_generar_audio_en_memoria(texto))
        _reproducir_bytes_automatico(audio)
    except Exception:
        return


def generate_question_audio(question) -> str | None:
    """Genera y guarda en disco el audio de una `Question`.

    Args:
        question: Objeto que contiene atributos `tema`, `pregunta` y `opciones`.

    Returns:
        Ruta al archivo MP3 creado o `None` si no se puede generar.
    """

    if not question or edge_tts is None:
        return None
    try:
        tema = getattr(question, "tema", "")
        pregunta = getattr(question, "pregunta", "")
        opciones = getattr(question, "opciones", []) or []
        opciones_text = ", ".join(opciones)
        texto = f"Tema {tema}. Pregunta: {pregunta}. Opciones: {opciones_text}."
        audio = asyncio.run(_generar_audio_en_memoria(texto))
        audio_dir = os.path.join("assets", "audio")
        os.makedirs(audio_dir, exist_ok=True)
        audio_path = os.path.join(audio_dir, f"question_{abs(hash(texto))}.mp3")
        with open(audio_path, "wb") as file:
            file.write(audio)
        return audio_path
    except Exception:
        return None


def play_background_music() -> None:
    """Reproduce la música de fondo si existe el archivo en `assets/audio`.

    Returns:
        None
    """

    background_path = os.path.join("assets", "audio", "background.mp3")
    if not os.path.exists(background_path):
        return
    with open(background_path, "rb") as file:
        bg_b64 = base64.b64encode(file.read()).decode()
    _render_audio_html(f"data:audio/mp3;base64,{bg_b64}", "backgroundMusic", loop=True, volume=0.08)


def play_question_voice(audio_path: str | None) -> None:
    """Reproduce la pista de voz de la pregunta desde archivo.

    Args:
        audio_path: Ruta al MP3 de la pregunta.

    Returns:
        None
    """

    if not audio_path or not os.path.exists(audio_path):
        return
    with open(audio_path, "rb") as file:
        q_b64 = base64.b64encode(file.read()).decode()
    _render_audio_html(f"data:audio/mp3;base64,{q_b64}", "questionVoice", volume=0.85)


def play_question_audio(audio_bytes: bytes) -> None:
    """Reproduce audio de pregunta que ya está en memoria (bytes).

    Args:
        audio_bytes: Contenido binario del MP3.

    Returns:
        None
    """

    if not audio_bytes:
        return
    _reproducir_bytes_automatico(audio_bytes)


def play_question_scene(audio_path: str | None) -> None:
    """Reproduce la escena de la pregunta: música de fondo + voz de pregunta.

    Args:
        audio_path: Ruta al MP3 de la pregunta.

    Returns:
        None
    """

    if not audio_path:
        return
    play_background_music()
    play_question_voice(audio_path)


def cleanup_question_audio() -> None:
    """Elimina todos los archivos de audio de preguntas almacenados.

    Busca archivos que empiecen por `question_` y terminen en `.mp3`.

    Returns:
        None
    """

    audio_dir = os.path.join("assets", "audio")
    if not os.path.exists(audio_dir):
        return
    try:
        for filename in os.listdir(audio_dir):
            if filename.startswith("question_") and filename.endswith(".mp3"):
                file_path = os.path.join(audio_dir, filename)
                os.remove(file_path)
    except Exception:
        # Silenciosamente ignorar si hay problemas al borrar
        pass


def speak_question(question) -> None:
    """Sintetiza y reproduce la pregunta en voz (sin almacenar en disco).

    Args:
        question: Objeto con atributos `tema`, `pregunta` y `opciones`.

    Returns:
        None
    """

    if not question:
        return
    tema = getattr(question, "tema", "")
    pregunta = getattr(question, "pregunta", "")
    opciones = getattr(question, "opciones", []) or []
    opciones_text = ", ".join(opciones)
    texto = f"Tema {tema}. Pregunta: {pregunta}. Opciones: {opciones_text}."
    speak_text(texto)
