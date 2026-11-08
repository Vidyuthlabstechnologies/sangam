from __future__ import annotations
import io
import os
import json
import zipfile
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

import httpx
from fastapi import HTTPException

from app.config import settings
from app.core import fixtures


SARVAM_BASE = "https://api.sarvam.ai"
TTS_LANGUAGES = [
    "en-IN", "hi-IN", "bn-IN", "ta-IN", "te-IN", "gu-IN",
    "kn-IN", "ml-IN", "mr-IN", "pa-IN", "od-IN",
]
STT_LANGUAGES = TTS_LANGUAGES + [
    "as-IN", "ur-IN", "ne-IN", "kok-IN", "ks-IN", "sd-IN",
    "sa-IN", "sat-IN", "mni-IN", "brx-IN", "mai-IN", "doi-IN",
]
TTS_SPEAKERS = [
    "anushka", "abhilash", "manisha", "vidya", "arya", "karun",
    "hitesh", "aditya", "ritu", "priya", "neha", "rahul",
    "pooja", "rohan", "simran", "kavya", "amit", "dev",
    "ishita", "shreya", "ratan", "varun", "manan", "sumit",
    "roopa", "kabir", "aayan", "shubh", "ashutosh", "advait",
    "anand", "tanya", "tarun", "sunny", "mani", "gokul",
    "vijay", "shruti", "suhani", "mohit", "kavitha", "rehan",
    "soham", "rupali"
]


@dataclass
class SarvamSTTResult:
    transcript: str
    language_code: str
    language_probability: float
    timestamps: Optional[List[Dict]] = None


@dataclass
class SarvamTTSResult:
    audio_base64: str
    request_id: str


@dataclass
class SarvamTranslateResult:
    translated_text: str
    source_language_code: str


@dataclass
class SarvamLLMResult:
    content: str
    model: str


@dataclass
class SarvamVisionResult:
    job_id: str
    output_url: Optional[str] = None


class SarvamAI:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.sarvam_api_key or os.environ.get("SARVAM_API_KEY", "")
        # No key configured means fixture mode rather than a hard failure, so
        # the app boots and the demo runs without live credentials. Identical
        # code paths run in both modes.
        self.use_fixtures = settings.use_fixtures or not self.api_key

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "api-subscription-key": self.api_key,
        }


    @staticmethod
    def _raise_for_status(response: httpx.Response, operation: str) -> None:
        """Raise with the API's own error message attached.

        httpx's raise_for_status reports only the status code and a docs
        link, which makes Sarvam failures (bad model, tier limits, invalid
        audio) undiagnosable from logs alone.
        """
        if response.status_code < 400:
            return
        detail = response.text[:400]
        try:
            payload = response.json()
            detail = payload.get("error", {}).get("message") or detail
        except Exception:
            pass
        raise RuntimeError(f"Sarvam {operation} failed ({response.status_code}): {detail}")

    async def speech_to_text(
        self,
        audio_data: bytes,
        filename: str = "audio.wav",
        language_code: str = "unknown",
        mode: str = "transcribe",
        with_timestamps: bool = False,
    ) -> SarvamSTTResult:
        if self.use_fixtures:
            data = fixtures.sarvam_stt(language_code)
            return SarvamSTTResult(
                transcript=data["transcript"],
                language_code=data["language_code"],
                language_probability=data["language_probability"],
            )

        async with httpx.AsyncClient(timeout=120) as client:
            files = {
                "file": (filename, audio_data, self._infer_mime(filename)),
                "model": (None, "saaras:v3"),
                "mode": (None, mode),
                "language_code": (None, language_code),
                "with_timestamps": (None, str(with_timestamps).lower()),
            }
            response = await client.post(
                f"{SARVAM_BASE}/speech-to-text",
                headers=self._headers,
                files=files,
            )
            response.raise_for_status()
            data = response.json()

        return SarvamSTTResult(
            transcript=data.get("transcript", ""),
            language_code=data.get("language_code", language_code),
            language_probability=data.get("language_probability", 0.0),
            timestamps=data.get("timestamps"),
        )

    async def text_to_speech(
        self,
        text: str,
        target_language_code: str = "hi-IN",
        speaker: str = "anushka",
        pace: float = 1.0,
        pitch: float = 0.0,
        loudness: float = 1.0,
        speech_sample_rate: int = 24000,
    ) -> SarvamTTSResult:
        if target_language_code not in TTS_LANGUAGES:
            raise ValueError(
                f"Unsupported TTS language: {target_language_code}. "
                f"Supported: {TTS_LANGUAGES}"
            )
        if speaker not in TTS_SPEAKERS:
            raise ValueError(
                f"Unsupported speaker: {speaker}. Supported: {TTS_SPEAKERS}"
            )

        if self.use_fixtures:
            data = fixtures.sarvam_tts()
            audios = data.get("audios", [])
            return SarvamTTSResult(
                audio_base64=audios[0] if audios else "",
                request_id=data.get("request_id", ""),
            )

        async with httpx.AsyncClient(timeout=60) as client:
            payload = {
                "text": text,
                "target_language_code": target_language_code,
                "speaker": speaker,
                "model": "bulbul:v3",
                "pace": pace,
                "speech_sample_rate": speech_sample_rate,
            }
            response = await client.post(
                f"{SARVAM_BASE}/text-to-speech",
                headers={**self._headers, "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        audios = data.get("audios", [])
        return SarvamTTSResult(
            audio_base64=audios[0] if audios else "",
            request_id=data.get("request_id", ""),
        )

    async def translate(
        self,
        text: str,
        source_language_code: str = "auto",
        target_language_code: str = "en-IN",
        model: str = "mayura:v1",
        mode: str = "formal",
    ) -> SarvamTranslateResult:
        async with httpx.AsyncClient(timeout=30) as client:
            payload = {
                "input": text,
                "source_language_code": source_language_code,
                "target_language_code": target_language_code,
                "model": model,
                "mode": mode,
                "enable_preprocessing": True,
            }
            response = await client.post(
                f"{SARVAM_BASE}/translate",
                headers={**self._headers, "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        return SarvamTranslateResult(
            translated_text=data.get("translated_text", ""),
            source_language_code=data.get("source_language_code", source_language_code),
        )

    async def llm_complete(
        self,
        messages: List[Dict[str, str]],
        model: str = "sarvam-30b",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> SarvamLLMResult:
        # USE_FIXTURES, or no Sarvam key and no local endpoint: canned response.
        # A configured LLM_BASE_URL is an OpenAI-compatible local model and is
        # used only when Sarvam itself is not configured. Tests force fixtures.
        local = (settings.llm_base_url or "").strip()
        if settings.use_fixtures or (not self.api_key and not local):
            data = fixtures.sarvam_llm_for(messages)
            return SarvamLLMResult(
                content=data["choices"][0]["message"]["content"],
                model=model,
            )
        if not self.api_key:
            return await self._llm_openai_compatible(
                messages, model, temperature, max_tokens
            )

        async with httpx.AsyncClient(timeout=120) as client:
            payload: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens:
                payload["max_tokens"] = max_tokens

            response = await client.post(
                f"{SARVAM_BASE}/v1/chat/completions",
                headers={**self._headers, "Content-Type": "application/json"},
                json=payload,
            )
            self._raise_for_status(response, "chat completion")
            data = response.json()

        content = ""
        if data.get("choices"):
            message = data["choices"][0].get("message") or {}
            # Reasoning models return content=null when the token budget was
            # exhausted before an answer was produced. Normalise to "" so
            # callers get a clear empty-content error rather than a TypeError.
            content = message.get("content") or ""

        return SarvamLLMResult(
            content=content,
            model=model,
        )

    async def _llm_openai_compatible(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: Optional[int],
    ) -> SarvamLLMResult:
        """Chat against an operator-hosted OpenAI-compatible server.

        The prompt is the request body and is not logged.
        """
        base = (settings.llm_base_url or "").rstrip("/")
        chosen = (settings.llm_model or model or "local")
        headers = {"Content-Type": "application/json"}
        if settings.llm_api_key:
            headers["Authorization"] = f"Bearer {settings.llm_api_key}"
        payload: Dict[str, Any] = {
            "model": chosen,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{base}/chat/completions",
                headers=headers,
                json=payload,
            )
            self._raise_for_status(response, "openai-compatible chat completion")
            data = response.json()
        content = ""
        if data.get("choices"):
            message = data["choices"][0].get("message") or {}
            content = message.get("content") or ""
        return SarvamLLMResult(content=content, model=chosen)

    async def text_analytics(
        self,
        text: str,
        questions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30) as client:
            payload = {
                "text": text,
                "questions": questions,
            }
            # Try multiple possible endpoints
            for endpoint in ["/text-analytics", "/v1/text-analytics", "/text_analytics"]:
                try:
                    response = await client.post(
                        f"{SARVAM_BASE}{endpoint}",
                        headers={**self._headers, "Content-Type": "application/json"},
                        json=payload,
                    )
                    if response.status_code != 404:
                        response.raise_for_status()
                        data = response.json()
                        return data.get("answers", [])
                except httpx.HTTPStatusError as e:
                    if e.response.status_code != 404:
                        raise
                except Exception:
                    pass
            # If all endpoints return 404, raise the last error
            raise HTTPException(status_code=404, detail="Text analytics endpoint not found")

    async def vision_extract(
        self,
        document_data: bytes,
        filename: str = "document.pdf",
        language_code: str = "hi-IN",
        output_format: str = "md",
    ) -> SarvamVisionResult:
        """Submit a document for digitisation.

        Sarvam's document-intelligence API is a four-step handshake, all of
        which are required before the job will ever leave state "Accepted":

          1. create the job                     -> job_id
          2. request upload URLs                -> presigned Azure SAS URL
          3. PUT the bytes to that URL          (needs x-ms-blob-type)
          4. start the job                      -> begins processing

        Skipping (2)-(4) leaves a job that is accepted but has no input and
        never completes, which is what the previous implementation did: it
        read an ``upload_url`` from a ``storage_container`` key the API does
        not return, so the upload silently never happened.
        """
        if self.use_fixtures:
            job = fixtures.sarvam_vision_job()
            return SarvamVisionResult(job_id=job["job_id"], output_url=None)

        json_headers = {**self._headers, "Content-Type": "application/json"}
        base = f"{SARVAM_BASE}/doc-digitization/job/v1"

        async with httpx.AsyncClient(timeout=300) as client:
            create_response = await client.post(
                base,
                headers=json_headers,
                json={
                    "job_parameters": {
                        "language": language_code,
                        "output_format": output_format,
                    }
                },
            )
            create_response.raise_for_status()
            job_id = create_response.json().get("job_id", "")
            if not job_id:
                raise RuntimeError("Sarvam did not return a job_id")

            upload_response = await client.post(
                f"{base}/upload-files",
                headers=json_headers,
                json={"job_id": job_id, "files": [filename]},
            )
            upload_response.raise_for_status()
            upload_urls = upload_response.json().get("upload_urls", {})
            entry = upload_urls.get(filename) or {}
            file_url = entry.get("file_url")
            if not file_url:
                raise RuntimeError(
                    f"Sarvam returned no upload URL for {filename!r}"
                )

            # Azure block blobs reject a PUT without this header.
            put_response = await client.put(
                file_url,
                content=document_data,
                headers={
                    "x-ms-blob-type": "BlockBlob",
                    "Content-Type": "application/octet-stream",
                },
            )
            put_response.raise_for_status()

            start_response = await client.post(
                f"{base}/{job_id}/start",
                headers=json_headers,
                json={"job_id": job_id},
            )
            start_response.raise_for_status()

            return SarvamVisionResult(job_id=job_id, output_url=None)

    async def vision_job_status(self, job_id: str) -> Dict[str, Any]:
        """Poll a digitisation job, normalised for callers.

        The API reports progress as ``job_state`` with values like
        "Accepted"/"Running"/"Completed"/"Failed". Callers get a lowercased
        ``status`` alias plus, once finished, ``output`` containing the
        extracted text fetched from the job's output URL.
        """
        if self.use_fixtures:
            return fixtures.sarvam_vision_status(job_id)

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f"{SARVAM_BASE}/doc-digitization/job/v1/{job_id}/status",
                headers=self._headers,
            )
            response.raise_for_status()
            data = response.json()

            state = (data.get("job_state") or "").lower()
            data["status"] = state

            if state in ("completed", "partiallycompleted", "succeeded", "done"):
                data["output"] = await self._fetch_job_output(client, job_id, data)

            return data

    async def _fetch_job_output(
        self, client: httpx.AsyncClient, job_id: str, status_payload: Dict[str, Any]
    ) -> str:
        """Download and unpack the extracted text of a completed job.

        Outputs are delivered as a ZIP in blob storage, reachable only via a
        short-lived presigned URL obtained from the download-files endpoint.
        The archive holds the requested format (``document.md``) plus
        per-page structured JSON under ``metadata/``; only the former is
        wanted here.
        """
        output_names = [
            out.get("file_name")
            for detail in (status_payload.get("job_details") or [])
            for out in (detail.get("outputs") or [])
            if out.get("file_name")
        ]
        if not output_names:
            return ""

        response = await client.post(
            f"{SARVAM_BASE}/doc-digitization/job/v1/{job_id}/download-files",
            headers={**self._headers, "Content-Type": "application/json"},
            json={"files": output_names},
        )
        response.raise_for_status()

        chunks: List[str] = []
        for entry in (response.json().get("download_urls") or {}).values():
            file_url = entry.get("file_url") if isinstance(entry, dict) else entry
            if not file_url:
                continue
            payload = await client.get(file_url)
            payload.raise_for_status()
            chunks.append(self._extract_text_payload(payload.content))

        return "\n\n".join(c for c in chunks if c)

    @staticmethod
    def _extract_text_payload(blob: bytes) -> str:
        """Return document text from a raw or zipped output payload."""
        if blob[:2] != b"PK":
            return blob.decode("utf-8", errors="replace")

        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            for name in archive.namelist():
                if name.startswith("metadata/"):
                    continue
                if name.lower().endswith((".md", ".html", ".txt")):
                    return archive.read(name).decode("utf-8", errors="replace")
        return ""

    async def stt_translate(
        self,
        audio_data: bytes,
        filename: str = "audio.wav",
        source_language_code: str = "unknown",
        with_diarization: bool = False,
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=120) as client:
            files = {
                "file": (filename, audio_data, self._infer_mime(filename)),
                "model": (None, "saaras:v3"),
                "with_diarization": (None, str(with_diarization).lower()),
            }
            if source_language_code != "unknown":
                files["source_language_code"] = (None, source_language_code)
            response = await client.post(
                f"{SARVAM_BASE}/speech-to-text-translate",
                headers=self._headers,
                files=files,
            )
            response.raise_for_status()
            return response.json()

    async def identify_language(self, text: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{SARVAM_BASE}/text-lid",
                headers={**self._headers, "Content-Type": "application/json"},
                json={"input": text},
            )
            response.raise_for_status()
            return response.json()

    async def transliterate(
        self,
        text: str,
        source_language_code: str = "auto",
        target_language_code: str = "en-IN",
    ) -> str:
        async with httpx.AsyncClient(timeout=15) as client:
            payload = {
                "input": text,
                "source_language_code": source_language_code,
                "target_language_code": target_language_code,
                "numerals_format": "international",
            }
            response = await client.post(
                f"{SARVAM_BASE}/transliterate",
                headers={**self._headers, "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        return data.get("transliterated_text", "")

    def _infer_mime(self, filename: str) -> str:
        ext = filename.lower().split(".")[-1] if "." in filename else "wav"
        mapping = {
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "ogg": "audio/ogg",
            "flac": "audio/flac",
            "m4a": "audio/mp4",
            "webm": "audio/webm",
            "aac": "audio/aac",
            "opus": "audio/opus",
            "amr": "audio/amr",
            "wma": "audio/x-ms-wma",
        }
        return mapping.get(ext, "audio/wav")

    def _to_json_string(self, obj: Any) -> str:
        return json.dumps(obj)
