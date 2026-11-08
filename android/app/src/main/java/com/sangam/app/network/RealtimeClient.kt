package com.sangam.app.network

import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import okhttp3.*
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import org.json.JSONObject
import java.util.concurrent.TimeUnit

data class RealtimeEvent(
    val event: String,
    val data: JSONObject,
    val ts: Long = System.currentTimeMillis(),
)

sealed class RealtimeState {
    data object Disconnected : RealtimeState()
    data object Connecting : RealtimeState()
    data object Connected : RealtimeState()
    data class Error(val message: String) : RealtimeState()
}

object RealtimeClient {
    private val client = OkHttpClient.Builder()
        .pingInterval(20, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.SECONDS)
        .build()

    private var ws: WebSocket? = null
    private var job: Job? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private val _events = MutableSharedFlow<RealtimeEvent>(extraBufferCapacity = 64)
    val events: SharedFlow<RealtimeEvent> = _events.asSharedFlow()

    private val _state = MutableStateFlow<RealtimeState>(RealtimeState.Disconnected)
    val state: StateFlow<RealtimeState> = _state.asStateFlow()

    private val _connectionCount = MutableStateFlow(0)
    val connectionCount: StateFlow<Int> = _connectionCount.asStateFlow()

    private val _lastEvent = MutableStateFlow<RealtimeEvent?>(null)
    val lastEvent: StateFlow<RealtimeEvent?> = _lastEvent.asStateFlow()

    private var reconnectAttempts = 0
    private var maxReconnectAttempts = 10
    private val baseDelay = 1000L

    private val callback = object : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            _state.value = RealtimeState.Connected
            reconnectAttempts = 0
            _connectionCount.value = _connectionCount.value + 1
        }

        override fun onMessage(webSocket: WebSocket, text: String) {
            try {
                val json = JSONObject(text)
                val event = json.optString("event", "unknown")
                val data = json.optJSONObject("data") ?: JSONObject()

                if (event == "ping") {
                    webSocket.send("""{"event":"pong"}""")
                    return
                }

                val evt = RealtimeEvent(event, data, json.optLong("ts", System.currentTimeMillis()))
                _events.tryEmit(evt)
                _lastEvent.value = evt
            } catch (_: Exception) { }
        }

        override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
            webSocket.close(code, reason)
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            _state.value = RealtimeState.Disconnected
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            _state.value = RealtimeState.Error(t.message ?: "Connection failed")
            scheduleReconnect()
        }
    }

    fun connect(token: String) {
        disconnect()
        _state.value = RealtimeState.Connecting
        val parsed = TokenManager.getServerUrl().toHttpUrlOrNull()
        if (parsed == null) {
            _state.value = RealtimeState.Error("Server URL is not valid")
            return
        }
        val scheme = if (parsed.scheme == "https") "wss" else "ws"
        val url = parsed.newBuilder()
            .scheme(scheme)
            .encodedPath("/ws")
            .query(null)
            .addQueryParameter("token", token)
            .build()
        ws = client.newWebSocket(Request.Builder().url(url).build(), callback)
    }

    fun subscribeWorkflow(workflowId: String) {
        ws?.send("""{"event":"subscribe_workflow","data":{"workflow_id":"$workflowId"}}""")
    }

    fun disconnect() {
        job?.cancel()
        ws?.close(1000, "Client closing")
        ws = null
        _state.value = RealtimeState.Disconnected
        reconnectAttempts = 0
    }

    private fun scheduleReconnect() {
        if (reconnectAttempts >= maxReconnectAttempts) return
        reconnectAttempts++
        val delay = baseDelay * (1 shl (reconnectAttempts - 1).coerceAtMost(6))
        job = scope.launch {
            delay(delay)
            val token = currentToken()
            if (token != null) connect(token)
        }
    }

    /** Safe to call from the main thread; the token is fetched on IO. */
    fun start() {
        scope.launch {
            val token = currentToken() ?: return@launch
            connect(token)
        }
    }

    private suspend fun currentToken(): String? = FirebaseSession.idToken() ?: TokenManager.getToken()

    fun stop() {
        disconnect()
    }
}
