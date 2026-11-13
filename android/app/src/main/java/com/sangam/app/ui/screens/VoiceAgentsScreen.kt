package com.sangam.app.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.sangam.app.network.ApiClient
import com.sangam.app.network.OutboundCallRequest
import com.sangam.app.network.TranscriptMessageDto
import com.sangam.app.network.VOICE_AGENT_LANGUAGES
import com.sangam.app.network.VoiceAgentCallDto
import com.sangam.app.network.VoiceAgentDto
import com.sangam.app.network.VoiceAgentSession
import com.sangam.app.network.VoiceSessionState
import com.sangam.app.ui.theme.SangamCrimson
import com.sangam.app.ui.theme.SangamMuted
import kotlinx.coroutines.launch
import retrofit2.HttpException

/**
 * Talk to the business's Samvaad voice agent live through our backend, or have
 * it phone a customer. The Voice Agents key stays on the server.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VoiceAgentsScreen(onBack: () -> Unit = {}) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var agents by remember { mutableStateOf<List<VoiceAgentDto>>(emptyList()) }
    var calls by remember { mutableStateOf<List<VoiceAgentCallDto>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var loadError by remember { mutableStateOf<String?>(null) }
    var selected by remember { mutableStateOf<VoiceAgentDto?>(null) }
    var language by remember { mutableStateOf("English") }
    var session by remember { mutableStateOf<VoiceAgentSession?>(null) }
    var transcriptFor by remember { mutableStateOf<VoiceAgentCallDto?>(null) }

    suspend fun refresh() {
        loading = true
        loadError = null
        try {
            agents = ApiClient.voiceAgentApi.myAgents()
            if (selected == null || agents.none { it.id == selected?.id }) selected = agents.firstOrNull()
            calls = ApiClient.voiceAgentApi.calls()
        } catch (e: Exception) {
            loadError = describeError(e)
        }
        loading = false
    }

    LaunchedEffect(Unit) { refresh() }
    DisposableEffect(Unit) { onDispose { session?.release() } }

    fun startTalking() {
        val agent = selected ?: return
        session?.release()
        session = VoiceAgentSession(agent.app_id, language).also { it.start() }
    }

    val micPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) startTalking() else loadError = "Allow the microphone to talk to your agent."
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Voice Agents") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { scope.launch { refresh() } }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                },
            )
        },
    ) { padding ->
        val active = session
        if (active != null) {
            LiveCall(
                session = active,
                agentLabel = selected?.label ?: "Agent",
                modifier = Modifier.padding(padding),
                onClose = {
                    active.release()
                    session = null
                    scope.launch { refresh() }
                },
            )
            return@Scaffold
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (loading && agents.isEmpty()) {
                item { LinearProgressIndicator(modifier = Modifier.fillMaxWidth()) }
            }
            loadError?.let { err ->
                item { Text(err, color = SangamCrimson) }
            }
            if (!loading && agents.isEmpty() && loadError == null) {
                item {
                    Text(
                        "No voice agent is set up for your business yet. Once your agent is linked, it shows up here.",
                        color = SangamMuted,
                    )
                }
            }

            if (agents.isNotEmpty()) {
                item {
                    Text("Agent", style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(8.dp))
                    Picker(
                        label = "Agent",
                        value = selected?.label ?: "",
                        options = agents.map { it.label },
                        onPick = { i -> selected = agents[i] },
                    )
                    Spacer(Modifier.height(8.dp))
                    Picker(
                        label = "Language",
                        value = language,
                        options = VOICE_AGENT_LANGUAGES,
                        onPick = { i -> language = VOICE_AGENT_LANGUAGES[i] },
                    )
                }
                item {
                    Button(
                        onClick = {
                            val granted = ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
                                PackageManager.PERMISSION_GRANTED
                            if (granted) startTalking() else micPermission.launch(Manifest.permission.RECORD_AUDIO)
                        },
                        enabled = selected != null,
                        modifier = Modifier.fillMaxWidth().height(52.dp),
                    ) {
                        Icon(Icons.Default.Mic, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("Talk to your agent now")
                    }
                    Text(
                        "Try it the way your customers will hear it. Calls use your call credit.",
                        style = MaterialTheme.typography.bodySmall,
                        color = SangamMuted,
                        modifier = Modifier.padding(top = 4.dp),
                    )
                }
                selected?.takeIf { it.can_call_out }?.let { agent ->
                    item {
                        OutboundCallCard(agent = agent, language = language, onPlaced = { scope.launch { refresh() } })
                    }
                }
            }

            if (calls.isNotEmpty()) {
                item {
                    Spacer(Modifier.height(8.dp))
                    Text("Recent calls", style = MaterialTheme.typography.titleMedium)
                }
                items(calls, key = { it.id }) { call ->
                    CallRow(call = call, onClick = { transcriptFor = call })
                }
            }
        }
    }

    transcriptFor?.let { call ->
        TranscriptDialog(call = call, onDismiss = { transcriptFor = null })
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun Picker(label: String, value: String, options: List<String>, onPick: (Int) -> Unit) {
    var open by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = open, onExpandedChange = { open = it }) {
        OutlinedTextField(
            value = value,
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = open) },
            modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable).fillMaxWidth(),
        )
        ExposedDropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            options.forEachIndexed { i, option ->
                DropdownMenuItem(text = { Text(option) }, onClick = { onPick(i); open = false })
            }
        }
    }
}

@Composable
private fun OutboundCallCard(agent: VoiceAgentDto, language: String, onPlaced: () -> Unit) {
    val scope = rememberCoroutineScope()
    var phone by remember { mutableStateOf("+91") }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    val valid = Regex("^\\+[1-9]\\d{7,14}$").matches(phone.trim())

    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Have the agent call a customer", fontWeight = FontWeight.Bold)
            OutlinedTextField(
                value = phone,
                onValueChange = { phone = it.filter { c -> c == '+' || c.isDigit() } },
                label = { Text("Customer phone, with country code") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                modifier = Modifier.fillMaxWidth(),
            )
            Button(
                onClick = {
                    busy = true
                    message = null
                    scope.launch {
                        message = try {
                            ApiClient.voiceAgentApi.placeCall(
                                OutboundCallRequest(agent.app_id, phone.trim(), language)
                            )
                            onPlaced()
                            "Calling now. The result shows under Recent calls."
                        } catch (e: Exception) {
                            describeError(e)
                        }
                        busy = false
                    }
                },
                enabled = valid && !busy,
            ) {
                Icon(Icons.Default.Call, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(if (busy) "Placing call" else "Call")
            }
            message?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = SangamMuted) }
        }
    }
}

@Composable
private fun CallRow(call: VoiceAgentCallDto, onClick: () -> Unit) {
    ElevatedCard(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Row(modifier = Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(call.user_phone, fontWeight = FontWeight.Bold)
                Text(
                    call.created_at.take(16).replace('T', ' '),
                    style = MaterialTheme.typography.bodySmall,
                    color = SangamMuted,
                )
                call.failure_reason?.takeIf { it.isNotBlank() }?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = SangamCrimson)
                }
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(statusLabel(call.status), style = MaterialTheme.typography.labelLarge)
                call.duration_seconds?.let {
                    Text(formatSeconds(it.toInt()), style = MaterialTheme.typography.bodySmall, color = SangamMuted)
                }
            }
        }
    }
}

@Composable
private fun TranscriptDialog(call: VoiceAgentCallDto, onDismiss: () -> Unit) {
    var lines by remember { mutableStateOf<List<TranscriptMessageDto>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(call.id) {
        try {
            lines = ApiClient.voiceAgentApi.transcript(call.id).messages
        } catch (e: Exception) {
            error = describeError(e)
        }
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = { TextButton(onClick = onDismiss) { Text("Close") } },
        title = { Text("Call with ${call.user_phone}") },
        text = {
            val shown = lines
            when {
                error != null -> Text(error ?: "", color = SangamCrimson)
                shown == null -> LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                shown.isEmpty() -> Text("No transcript for this call yet.", color = SangamMuted)
                else -> LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(shown) { TranscriptBubble(it.role, it.content) }
                }
            }
        },
    )
}

@Composable
private fun LiveCall(
    session: VoiceAgentSession,
    agentLabel: String,
    modifier: Modifier,
    onClose: () -> Unit,
) {
    val state by session.state.collectAsState()
    val transcript by session.transcript.collectAsState()
    val muted by session.muted.collectAsState()
    var typed by remember { mutableStateOf("") }
    val listState = rememberLazyListState()
    LaunchedEffect(transcript.size) {
        if (transcript.isNotEmpty()) listState.animateScrollToItem(transcript.size - 1)
    }
    val finished = state is VoiceSessionState.Ended || state is VoiceSessionState.Failed

    Column(modifier = modifier.fillMaxSize().padding(16.dp)) {
        Text(agentLabel, style = MaterialTheme.typography.headlineSmall)
        Text(
            when (val s = state) {
                VoiceSessionState.Idle, VoiceSessionState.Connecting -> "Connecting"
                VoiceSessionState.Live -> if (muted) "Live, you are muted" else "Live, go ahead and speak"
                is VoiceSessionState.Ended -> "Call ended" + if (s.seconds > 0) " after ${formatSeconds(s.seconds)}" else ""
                is VoiceSessionState.Failed -> s.message
            },
            color = if (state is VoiceSessionState.Failed) SangamCrimson else SangamMuted,
        )
        if (state == VoiceSessionState.Connecting) {
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth().padding(top = 8.dp))
        }
        LazyColumn(
            state = listState,
            modifier = Modifier.weight(1f).fillMaxWidth().padding(vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(transcript) { TranscriptBubble(it.role, it.content) }
        }
        if (state == VoiceSessionState.Live) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = typed,
                    onValueChange = { typed = it },
                    placeholder = { Text("Or type a message") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
                IconButton(
                    onClick = { session.sendText(typed); typed = "" },
                    enabled = typed.isNotBlank(),
                ) {
                    Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send")
                }
            }
            Spacer(Modifier.height(12.dp))
        }
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
            if (!finished) {
                OutlinedButton(
                    onClick = { session.setMuted(!muted) },
                    enabled = state == VoiceSessionState.Live,
                    modifier = Modifier.weight(1f).height(52.dp),
                ) {
                    Icon(if (muted) Icons.Default.MicOff else Icons.Default.Mic, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(if (muted) "Unmute" else "Mute")
                }
                Button(
                    onClick = { session.stop() },
                    colors = ButtonDefaults.buttonColors(containerColor = SangamCrimson),
                    modifier = Modifier.weight(1f).height(52.dp),
                ) {
                    Icon(Icons.Default.CallEnd, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("Hang up")
                }
            } else {
                Button(onClick = onClose, modifier = Modifier.fillMaxWidth().height(52.dp)) {
                    Text("Done")
                }
            }
        }
    }
}

@Composable
private fun TranscriptBubble(role: String, content: String) {
    val fromAgent = role == "assistant" || role == "agent" || role == "bot"
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (fromAgent) Arrangement.Start else Arrangement.End,
    ) {
        Surface(
            shape = MaterialTheme.shapes.medium,
            color = if (fromAgent) MaterialTheme.colorScheme.surfaceVariant else MaterialTheme.colorScheme.primaryContainer,
            modifier = Modifier.widthIn(max = 300.dp),
        ) {
            Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {
                Text(
                    if (fromAgent) "Agent" else "You",
                    style = MaterialTheme.typography.labelSmall,
                    color = SangamMuted,
                )
                Text(content, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

private fun statusLabel(status: String): String = when (status) {
    "pending", "queued" -> "Dialling"
    "connected", "completed" -> "Answered"
    "no_answer" -> "No answer"
    "busy" -> "Busy"
    "failed" -> "Failed"
    else -> status.replace('_', ' ').replaceFirstChar { it.uppercase() }
}

private fun formatSeconds(total: Int): String = "%d:%02d".format(total / 60, total % 60)

private fun describeError(e: Exception): String = when (e) {
    is HttpException -> when (e.code()) {
        400, 422 -> "Check the phone number. Use the full number with country code, like +919876543210."
        402 -> "Add call credit to use your voice agent."
        404 -> "This agent is not set up for your business yet."
        429 -> "Too many calls are still ringing. Wait for one to finish."
        503 -> "Voice agents are not switched on yet. Try again later."
        else -> "Something went wrong (${e.code()}). Try again."
    }
    else -> "Could not reach the server. Check your internet and try again."
}
