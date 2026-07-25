from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_session
from app.models.actor import Actor
from app.core.sarvam import SarvamAI, TTS_LANGUAGES, STT_LANGUAGES
from app.core.semantic_boundary import SemanticBoundaryDetector
from app.core.retry import retry_async
from app.api.dependencies import get_current_actor

router = APIRouter(prefix="/ai", tags=["sarvam-ai"])


class TTSRequest(BaseModel):
    text: str
    target_language_code: str = "hi-IN"
    speaker: str = "priya"
    pace: float = 1.0
    pitch: float = 0.0
    loudness: float = 1.0


class TranslateRequest(BaseModel):
    text: str
    source_language_code: str = "auto"
    target_language_code: str = "en-IN"
    model: str = "mayura:v1"
    mode: str = "formal"


class LLMRequest(BaseModel):
    messages: List[dict]
    model: str = "sarvam-30b"
    temperature: float = 0.7
    max_tokens: Optional[int] = None


class TextAnalyticsRequest(BaseModel):
    text: str
    questions: Optional[List[dict]] = None
    task: Optional[str] = None  # Support "sentiment", "entities", "summary", etc.


class BoundaryDetectionRequest(BaseModel):
    text: str
    language_code: str = "en-IN"
    workflow_name: Optional[str] = None
    workflow_description: Optional[str] = None
    actor_types: List[str] = ["human"]
    phases: List[str] = ["initiation", "approval", "execution"]
    metadata: Optional[dict] = None


class TransliterateRequest(BaseModel):
    text: str
    source_language_code: str = "auto"
    target_language_code: str = "en-IN"


@router.post("/speech-to-text", response_model=dict)
async def speech_to_text(
    file: UploadFile = File(...),
    language_code: str = Form("unknown"),
    mode: str = Form("transcribe"),
    with_timestamps: bool = Form(False),
    current_actor: Actor = Depends(get_current_actor),
):
    try:
        sarvam = SarvamAI()
        audio_data = await file.read()
        result = await sarvam.speech_to_text(
            audio_data=audio_data,
            filename=file.filename or "audio.wav",
            language_code=language_code,
            mode=mode,
            with_timestamps=with_timestamps,
        )
        return {
            "transcript": result.transcript,
            "language_code": result.language_code,
            "language_probability": result.language_probability,
            "timestamps": result.timestamps,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sarvam API error: {str(e)}")


@router.post("/text-to-speech", response_model=dict)
async def text_to_speech(
    req: TTSRequest,
    current_actor: Actor = Depends(get_current_actor),
):
    try:
        sarvam = SarvamAI()
        result = await sarvam.text_to_speech(
            text=req.text,
            target_language_code=req.target_language_code,
            speaker=req.speaker,
            pace=req.pace,
            pitch=req.pitch,
            loudness=req.loudness,
        )
        return {
            "audio_base64": result.audio_base64,
            "request_id": result.request_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sarvam API error: {str(e)}")


@router.post("/translate", response_model=dict)
async def translate(
    req: TranslateRequest,
    current_actor: Actor = Depends(get_current_actor),
):
    try:
        sarvam = SarvamAI()
        result = await sarvam.translate(
            text=req.text,
            source_language_code=req.source_language_code,
            target_language_code=req.target_language_code,
            model=req.model,
            mode=req.mode,
        )
        return {
            "translated_text": result.translated_text,
            "source_language_code": result.source_language_code,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sarvam API error: {str(e)}")


async def _call_sarvam_llm(req: LLMRequest):
    sarvam = SarvamAI()
    return await sarvam.llm_complete(
        messages=req.messages,
        model=req.model,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    )


@router.post("/llm", response_model=dict)
async def llm_complete(
    req: LLMRequest,
    current_actor: Actor = Depends(get_current_actor),
):
    try:
        result = await retry_async(
            _call_sarvam_llm, req,
            max_retries=2,
            base_delay=0.5,
            max_delay=5,
        )
        return {
            "content": result.content,
            "model": result.model,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sarvam API error: {str(e)}")


@router.post("/text-analytics", response_model=dict)
async def text_analytics(
    req: TextAnalyticsRequest,
    current_actor: Actor = Depends(get_current_actor),
):
    try:
        sarvam = SarvamAI()
        if req.task:
            # For simple tasks like sentiment, use the task directly
            answers = await sarvam.text_analytics(
                text=req.text,
                questions=[{"question": f"Analyze {req.task} of the text", "type": req.task}],
            )
        else:
            answers = await sarvam.text_analytics(
                text=req.text,
                questions=req.questions or [],
            )
        return {"answers": answers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sarvam API error: {str(e)}")


@router.post("/vision/extract", response_model=dict)
async def vision_extract(
    file: UploadFile = File(...),
    language_code: str = Form("hi-IN"),
    output_format: str = Form("md"),
    current_actor: Actor = Depends(get_current_actor),
):
    try:
        sarvam = SarvamAI()
        doc_data = await file.read()
        result = await sarvam.vision_extract(
            document_data=doc_data,
            filename=file.filename or "document.pdf",
            language_code=language_code,
            output_format=output_format,
        )
        return {
            "job_id": result.job_id,
            "status": "processing",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sarvam API error: {str(e)}")


@router.post("/speech-to-text-translate", response_model=dict)
async def speech_to_text_translate(
    file: UploadFile = File(...),
    source_language_code: str = Form("unknown"),
    with_diarization: bool = Form(False),
    current_actor: Actor = Depends(get_current_actor),
):
    try:
        sarvam = SarvamAI()
        audio_data = await file.read()
        result = await sarvam.stt_translate(
            audio_data=audio_data,
            filename=file.filename or "audio.wav",
            source_language_code=source_language_code,
            with_diarization=with_diarization,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sarvam API error: {str(e)}")


@router.get("/vision/status/{job_id}", response_model=dict)
async def vision_status(
    job_id: str,
    current_actor: Actor = Depends(get_current_actor),
):
    try:
        sarvam = SarvamAI()
        result = await sarvam.vision_job_status(job_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sarvam API error: {str(e)}")


@router.get("/languages", response_model=dict)
async def list_languages(
    current_actor: Actor = Depends(get_current_actor),
):
    return {
        "stt": STT_LANGUAGES,
        "tts": TTS_LANGUAGES,
        "translate": list(set(STT_LANGUAGES) | {"en-IN"}),
    }


@router.get("/voices", response_model=dict)
async def list_voices(
    current_actor: Actor = Depends(get_current_actor),
):
    from app.core.sarvam import TTS_SPEAKERS
    voices = {s: {} for s in TTS_SPEAKERS}
    return {"voices": voices}


class IdentifyLanguageRequest(BaseModel):
    text: str


@router.post("/identify-language", response_model=dict)
async def identify_language(
    req: IdentifyLanguageRequest,
    current_actor: Actor = Depends(get_current_actor),
):
    try:
        sarvam = SarvamAI()
        result = await sarvam.identify_language(req.text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sarvam API error: {str(e)}")


@router.post("/transliterate", response_model=dict)
async def transliterate(
    req: TransliterateRequest,
    current_actor: Actor = Depends(get_current_actor),
):
    try:
        sarvam = SarvamAI()
        result = await sarvam.transliterate(
            text=req.text,
            source_language_code=req.source_language_code,
            target_language_code=req.target_language_code,
        )
        return {"transliterated_text": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sarvam API error: {str(e)}")


@router.post("/detect-boundaries", response_model=dict)
async def detect_semantic_boundaries(
    req: BoundaryDetectionRequest,
    current_actor: Actor = Depends(get_current_actor),
):
    try:
        detector = SemanticBoundaryDetector()
        # Use text as workflow_description if not provided
        workflow_name = req.workflow_name or "Text Analysis"
        workflow_description = req.workflow_description or req.text
        result = await detector.detect(
            workflow_name=workflow_name,
            workflow_description=workflow_description,
            actor_types=req.actor_types,
            phases=req.phases,
            metadata=req.metadata,
        )
        return {
            "boundaries": result.boundaries,
            "risk_score": result.risk_score,
            "summary": result.summary,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
