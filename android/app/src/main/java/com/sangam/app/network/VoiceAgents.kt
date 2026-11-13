package com.sangam.app.network

import android.annotation.SuppressLint
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.NoiseSuppressor
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import okio.ByteString.Companion.toByteString
import org.json.JSONObject
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query
import java.util.concurrent.TimeUnit

// ---- REST: /voice-agents ------------------------------------------------

data class VoiceAgentDto(
    val id: String,
    val tenant_id: String,
    val app_id: String,
    val app_version: Int?,
    val label: String,
    val agent_phone_number: String?,
    val can_call_out: Boolean,
)

data class OutboundCallRequest(
    val app_id: String,
    val user_phone_number: String,
    val initial_language_name: String? = null,
)

data class VoiceAgentCallDto(
    val id: String,
    val attempt_id: String?,
    val app_id: String,
    val user_phone: String,
    val status: String,
    val duration_seconds: Double?,
    val failure_reason: String?,
    val created_at: String,
)

data class TranscriptMessageDto(val role: String, val content: String)

data class TranscriptDto(val interaction_id: String?, val messages: List<TranscriptMessageDto>)

interface SangamVoiceAgentApi {
    @GET("/voice-agents/agents")
    suspend fun myAgents(): List<VoiceAgentDto>

    @POST("/voice-agents/calls")
    suspend fun placeCall(@Body body: OutboundCallRequest): VoiceAgentCallDto

    @GET("/voice-agents/calls")
    suspend fun calls(@Query("limit") limit: Int = 30): List<VoiceAgentCallDto>

    @GET("/voice-agents/calls/{id}/transcript")
    suspend fun transcript(@Path("id") id: String): TranscriptDto
}

/** Agent languages Samvaad accepts as initial_language_name. */
val VOICE_AGENT_LANGUAGES = listOf(
    "Kannada", "Hindi", "English", "Telugu", "Tamil", "Malayalam",
    "Marathi", "Bengali", "Gujarati", "Punjabi", "Odia",
)

// ---- Live session: /voice-agents/ws/{app_id} ----------------------------

data class TranscriptLine(val role: String, val content: String)

sealed class VoiceSessionState {
    data object Idle : VoiceSessionState()
    data object Connecting : VoiceSessionState()
    data object Live : VoiceSessionState()
    data class Ended(val reason: String, val seconds: Int) : VoiceSessionState()
    data class Failed(val message: String) : VoiceSessionState()
}

/**
 * One live conversation with a voice agent, proxied by our backend.
 *
 * The Voice Agents key never reaches the phone. We stream 16 kHz mono 16-bit
 * PCM from the mic as binary frames and play back the agent's PCM, whose
 * sample rate the server announces in an "audio_format" message. On
 * "user_interrupt" (the caller talked over the agent) playback is flushed.
 */
class VoiceAgentSession(private val appId: String, private val language: String?) {

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val client = OkHttpClient.Builder()
        .pingInterval(20, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.SECONDS)
        .build()

    private val _state = MutableStateFlow<VoiceSessionState>(VoiceSessionState.Idle)
    val state: StateFlow<VoiceSessionState> = _state.asStateFlow()

    private val _transcript = MutableStateFlow<List<TranscriptLine>>(emptyList())
    val transcript: StateFlow<List<TranscriptLine>> = _transcript.asStateFlow()

    private val _muted = MutableStateFlow(false)
    val muted: StateFlow<Boolean> = _muted.asStateFlow()

    private var ws: WebSocket? = null
    private var recorder: AudioRecord? = null
    private var micJob: Job? = null
    private var player: AudioTrack? = null
    private var playerRate = SAMPLE_RATE

    fun start() {
        if (_state.value == VoiceSessionState.Connecting || _state.value == VoiceSessionState.Live) return
        _state.value = VoiceSessionState.Connecting
        _transcript.value = emptyList()
        scope.launch {
            val token = FirebaseSession.idToken()
            if (token == null) {
                _state.value = VoiceSessionState.Failed("Please sign in again")
                return@launch
            }
            val base = TokenManager.getServerUrl().toHttpUrlOrNull()
            if (base == null) {
                _state.value = VoiceSessionState.Failed("Server URL is not valid")
                return@launch
            }
            val url = base.newBuilder()
                .scheme(if (base.scheme == "https") "https" else "http")
                .encodedPath("/voice-agents/ws/")
                .addPathSegment(appId)
                .query(null)
                .addQueryParameter("token", token)
                .apply { if (!language.isNullOrBlank()) addQueryParameter("language", language) }
                .build()
            ws = client.newWebSocket(Request.Builder().url(url).build(), listener)
        }
    }

    fun setMuted(value: Boolean) {
        _muted.value = value
    }

    fun sendText(text: String) {
        val clean = text.trim()
        if (clean.isEmpty()) return
        ws?.send(JSONObject().put("type", "text").put("text", clean).toString())
    }

    /** Hang up. Safe to call more than once. */
    fun stop() {
        ws?.send("""{"type":"end"}""")
        stopAudio()
        scope.launch {
            kotlinx.coroutines.delay(1500)
            ws?.close(1000, "hang up")
            ws = null
        }
    }

    fun release() {
        stopAudio()
        ws?.cancel()
        ws = null
        scope.cancel()
    }

    private fun addLine(role: String, content: String) {
        if (content.isBlank()) return
        _transcript.value = _transcript.value + TranscriptLine(role, content)
    }

    private val listener = object : WebSocketListener() {
        override fun onMessage(webSocket: WebSocket, text: String) {
            val msg = try { JSONObject(text) } catch (_: Exception) { return }
            when (msg.optString("type")) {
                "ready" -> {
                    _state.value = VoiceSessionState.Live
                    startMic(webSocket)
                }
                "transcript" -> addLine(msg.optString("role"), msg.optString("content"))
                "audio_format" -> preparePlayer(msg.optInt("sample_rate", SAMPLE_RATE))
                "event" -> if (msg.optString("event") == "user_interrupt") flushPlayback()
                "ended" -> {
                    _state.value = VoiceSessionState.Ended(msg.optString("reason"), msg.optInt("seconds"))
                    stopAudio()
                }
                "error" -> {
                    _state.value = VoiceSessionState.Failed(friendlyError(msg.optInt("status"), msg.optString("detail")))
                    stopAudio()
                }
            }
        }

        override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
            val track = player ?: preparePlayer(playerRate)
            val data = bytes.toByteArray()
            track.write(data, 0, data.size)
        }

        override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
            webSocket.close(code, reason)
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            stopAudio()
            if (_state.value is VoiceSessionState.Live || _state.value is VoiceSessionState.Connecting) {
                _state.value = VoiceSessionState.Ended("closed", 0)
            }
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            stopAudio()
            if (_state.value !is VoiceSessionState.Ended && _state.value !is VoiceSessionState.Failed) {
                _state.value = VoiceSessionState.Failed("Connection lost. Check your internet and try again.")
            }
        }
    }

    @SuppressLint("MissingPermission") // The screen asks for RECORD_AUDIO before start().
    private fun startMic(socket: WebSocket) {
        if (micJob != null) return
        val minBuf = AudioRecord.getMinBufferSize(SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val rec = try {
            AudioRecord(
                MediaRecorder.AudioSource.VOICE_COMMUNICATION,
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                maxOf(minBuf, FRAME_BYTES * 4),
            )
        } catch (e: Exception) {
            _state.value = VoiceSessionState.Failed("Microphone is not available")
            return
        }
        if (rec.state != AudioRecord.STATE_INITIALIZED) {
            rec.release()
            _state.value = VoiceSessionState.Failed("Microphone is not available")
            return
        }
        // The agent's voice comes out of the speaker; without echo cancelling it hears itself.
        if (AcousticEchoCanceler.isAvailable()) AcousticEchoCanceler.create(rec.audioSessionId)?.enabled = true
        if (NoiseSuppressor.isAvailable()) NoiseSuppressor.create(rec.audioSessionId)?.enabled = true
        recorder = rec
        rec.startRecording()
        micJob = scope.launch {
            val buf = ByteArray(FRAME_BYTES)
            val silence = ByteArray(FRAME_BYTES)
            while (isActive) {
                val n = rec.read(buf, 0, buf.size)
                if (n <= 0) continue
                // Muted still sends silence so the agent's turn-taking keeps working.
                val frame = if (_muted.value) silence else buf
                socket.send(frame.toByteString(0, n))
            }
        }
    }

    private fun preparePlayer(rate: Int): AudioTrack {
        val existing = player
        if (existing != null && rate == playerRate) return existing
        existing?.let { it.stop(); it.release() }
        playerRate = rate
        val minBuf = AudioTrack.getMinBufferSize(rate, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val track = AudioTrack.Builder()
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            .setAudioFormat(
                AudioFormat.Builder()
                    .setSampleRate(rate)
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .build()
            )
            .setBufferSizeInBytes(maxOf(minBuf, rate))
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()
        track.play()
        player = track
        return track
    }

    private fun flushPlayback() {
        player?.let {
            it.pause()
            it.flush()
            it.play()
        }
    }

    private fun stopAudio() {
        micJob?.cancel()
        micJob = null
        recorder?.let {
            try { it.stop() } catch (_: Exception) { }
            it.release()
        }
        recorder = null
        player?.let {
            try { it.stop() } catch (_: Exception) { }
            it.release()
        }
        player = null
    }

    private fun friendlyError(status: Int, detail: String): String = when (status) {
        402 -> "Add call credit to talk to your agent."
        404 -> "This agent is not set up for your business yet."
        503 -> "Voice agents are not switched on yet. Try again later."
        else -> detail.ifBlank { "Could not start the call" }
    }

    companion object {
        const val SAMPLE_RATE = 16000
        // 20 ms of 16 kHz 16-bit mono.
        const val FRAME_BYTES = SAMPLE_RATE / 50 * 2
    }
}
