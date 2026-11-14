package com.sangam.app.ui.screens

import com.sangam.app.ui.components.SecondaryButton
import com.sangam.app.ui.components.PrimaryButton
import com.sangam.app.ui.components.friendlyError
import com.sangam.app.ui.components.BackButton
import android.Manifest
import android.content.pm.PackageManager
import android.media.MediaPlayer
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.compose.ui.text.style.TextAlign
import android.media.MediaRecorder
import android.os.Build
import android.util.Base64
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sangam.app.R
import com.sangam.app.network.ApiClient
import com.sangam.app.network.TokenManager
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

enum class VoiceState { IDLE, RECORDING, PROCESSING, REVIEW, DONE }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VoiceWorkflowScreen(
    onBack: () -> Unit = {},
    onWorkflowCreated: () -> Unit = {},
) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var state by remember { mutableStateOf(VoiceState.IDLE) }
    var transcript by remember { mutableStateOf("") }
    var workflowName by remember { mutableStateOf("") }
    var workflowDesc by remember { mutableStateOf("") }
    var detectedLang by remember { mutableStateOf("") }
    var error by remember { mutableStateOf("") }
    var recordingFile by remember { mutableStateOf<File?>(null) }
    var mediaRecorder by remember { mutableStateOf<MediaRecorder?>(null) }

    fun startRecording() {
        error = ""
        state = VoiceState.RECORDING
        scope.launch {
            try {
                val dir = context.cacheDir
                val file = File(dir, "sangam_voice_${System.currentTimeMillis()}.3gp")
                recordingFile = file
                val recorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                    MediaRecorder(context)
                } else {
                    @Suppress("DEPRECATION") MediaRecorder()
                }
                recorder.setAudioSource(MediaRecorder.AudioSource.MIC)
                recorder.setOutputFormat(MediaRecorder.OutputFormat.THREE_GPP)
                recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AMR_NB)
                recorder.setOutputFile(file.absolutePath)
                recorder.prepare()
                recorder.start()
                mediaRecorder = recorder
            } catch (e: Exception) {
                error = "Could not start recording. Check that Sangamitra has microphone permission."
                state = VoiceState.IDLE
            }
        }
    }

    // Recording without RECORD_AUDIO granted throws, which showed a dead-end error.
    val micPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) startRecording()
        else error = "Sangamitra needs the microphone to hear you. Allow it in Settings, or type your workflow in the AI assistant."
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Voice workflow") },
                navigationIcon = {
                    BackButton(onBack)
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(24.dp)
                .verticalScroll(rememberScrollState()),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                "Say what should happen, in any Indian language. For example: \"When a caller books a visit, ask me to approve it.\"",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
            Spacer(modifier = Modifier.height(32.dp))

            when (state) {
                VoiceState.IDLE -> {
                    FilledTonalButton(
                        onClick = {
                            val granted = ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
                                PackageManager.PERMISSION_GRANTED
                            if (granted) startRecording() else micPermission.launch(Manifest.permission.RECORD_AUDIO)
                        },
                        modifier = Modifier.size(156.dp),
                        contentPadding = PaddingValues(12.dp),
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Image(
                                painter = painterResource(id = R.drawable.mascot_kite_idle),
                                contentDescription = null,
                                modifier = Modifier.size(56.dp),
                                contentScale = ContentScale.Fit
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Text("Tap to speak", style = MaterialTheme.typography.labelLarge, textAlign = TextAlign.Center)
                        }
                    }
                }

                VoiceState.RECORDING -> {
                    FilledTonalButton(
                        onClick = {
                            state = VoiceState.PROCESSING
                            scope.launch {
                                try {
                                    mediaRecorder?.apply {
                                        stop()
                                        release()
                                    }
                                    mediaRecorder = null

                                    val file = recordingFile ?: throw Exception("No recording file")
                                    val audioData = withContext(Dispatchers.IO) { file.readBytes() }
                                    val requestBody = audioData.toRequestBody("audio/3gp".toMediaTypeOrNull())
                                    val part = MultipartBody.Part.createFormData("file", file.name, requestBody)
                                    val langPart = "unknown".toRequestBody("text/plain".toMediaTypeOrNull())
                                    val modePart = "transcribe".toRequestBody("text/plain".toMediaTypeOrNull())
                                    val tsPart = "false".toRequestBody("text/plain".toMediaTypeOrNull())

                                    val sttResult = ApiClient.aiApi.speechToText(part, langPart, modePart, tsPart)
                                    transcript = sttResult.transcript
                                    detectedLang = sttResult.language_code

                                    val systemPrompt = """
                                        You are a workflow creation AI. From the user's spoken description, extract:
                                        - name: a short workflow title (max 6 words)
                                        - description: a 1-2 sentence summary
                                        - phases: choose 2-4 from ["INITIATION","APPROVAL","EXECUTION","VERIFICATION","SETTLEMENT"]
                                        Respond with ONLY valid JSON — no markdown, no extra text.
                                        Example: {"name": "Vendor Payment", "description": "Approve and process vendor invoice", "phases": ["INITIATION","APPROVAL","SETTLEMENT"]}
                                        If the user speaks in Hindi, Tamil, or any Indian language, extract in English anyway.
                                    """.trimIndent()

                                    val llmResult = ApiClient.aiApi.llmComplete(
                                        com.sangam.app.network.LLMRequest(
                                            messages = listOf(
                                                com.sangam.app.network.LLMMessage("system", systemPrompt),
                                                com.sangam.app.network.LLMMessage("user", sttResult.transcript),
                                            ),
                                            model = "sarvam-30b",
                                        )
                                    )

                                    val json = llmResult.content.trim()
                                    val nameMatch = Regex("""\"name\"\s*:\s*\"([^\"]+)\"""").find(json)
                                    val descMatch = Regex("""\"description\"\s*:\s*\"([^\"]+)\"""").find(json)
                                    workflowName = nameMatch?.groupValues?.getOrNull(1) ?: "Voice Workflow"
                                    workflowDesc = descMatch?.groupValues?.getOrNull(1) ?: transcript.take(200)
                                    file.delete()
                                    state = VoiceState.REVIEW
                                } catch (e: Exception) {
                                    error = friendlyError(e, "understand the recording")
                                    state = VoiceState.IDLE
                                }
                            }
                        },
                        modifier = Modifier.size(156.dp),
                        contentPadding = PaddingValues(12.dp),
                        colors = ButtonDefaults.filledTonalButtonColors(
                            containerColor = MaterialTheme.colorScheme.errorContainer,
                        ),
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Image(
                                painter = painterResource(id = R.drawable.mascot_kite_thinking),
                                contentDescription = null,
                                modifier = Modifier.size(56.dp),
                                contentScale = ContentScale.Fit
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Text("Tap when done", style = MaterialTheme.typography.labelLarge, textAlign = TextAlign.Center)
                        }
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("Listening…", color = MaterialTheme.colorScheme.error, fontWeight = FontWeight.SemiBold)
                }

                VoiceState.PROCESSING -> {
                    Image(
                        painter = painterResource(id = R.drawable.mascot_kite_thinking),
                        contentDescription = null,
                        modifier = Modifier.size(110.dp),
                        contentScale = ContentScale.Fit
                    )
                    Spacer(modifier = Modifier.height(14.dp))
                    CircularProgressIndicator()
                    Spacer(modifier = Modifier.height(14.dp))
                    Text("Understanding your request…", fontWeight = FontWeight.SemiBold)
                    Text("Turning what you said into workflow steps", style = MaterialTheme.typography.bodySmall,
                         color = MaterialTheme.colorScheme.onSurfaceVariant)
                }

                VoiceState.REVIEW -> {
                    if (transcript.isNotEmpty()) {
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(
                                containerColor = MaterialTheme.colorScheme.surfaceVariant
                            ),
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Text("You said", fontWeight = FontWeight.Bold)
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(transcript)
                                if (detectedLang.isNotEmpty()) {
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text("Language: $detectedLang",
                                         style = MaterialTheme.typography.bodySmall,
                                         color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }
                        }
                    }
                    Spacer(modifier = Modifier.height(16.dp))

                    OutlinedTextField(
                        value = workflowName,
                        onValueChange = { workflowName = it },
                        label = { Text("Workflow name") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    OutlinedTextField(
                        value = workflowDesc,
                        onValueChange = { workflowDesc = it },
                        label = { Text("Description") },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 3,
                    )
                    Spacer(modifier = Modifier.height(24.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        SecondaryButton(
                            onClick = {
                                state = VoiceState.IDLE
                                transcript = ""
                                workflowName = ""
                                workflowDesc = ""
                                error = ""
                            },
                            modifier = Modifier.weight(1f),
                        ) { Text("Cancel") }

                        PrimaryButton(
                            onClick = {
                                state = VoiceState.DONE
                                scope.launch {
                                    try {
                                        ApiClient.api.createWorkflow(
                                            com.sangam.app.network.WorkflowCreateRequest(
                                                name = workflowName.ifBlank { "Voice Workflow" },
                                                description = workflowDesc.ifBlank { transcript.take(200) },
                                                initiator_id = TokenManager.getActorId() ?: "",
                                            )
                                        )
                                    } catch (e: Exception) {
                                        error = friendlyError(e, "create the workflow")
                                        state = VoiceState.REVIEW
                                    }
                                }
                            },
                            modifier = Modifier.weight(1f),
                        ) { Text("Create workflow") }
                    }
                }

                VoiceState.DONE -> {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.primaryContainer,
                        ),
                    ) {
                        Column(
                            modifier = Modifier.padding(24.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Image(
                                painter = painterResource(id = R.drawable.mascot_kite_victory),
                                contentDescription = "Workflow Created",
                                modifier = Modifier.size(110.dp),
                                contentScale = ContentScale.Fit
                            )
                            Spacer(modifier = Modifier.height(10.dp))
                            Text("Workflow created", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(workflowName, fontWeight = FontWeight.Bold)
                            Spacer(modifier = Modifier.height(16.dp))
                            PrimaryButton(onClick = onWorkflowCreated) {
                                Text("Go to workflows")
                            }
                            Spacer(modifier = Modifier.height(8.dp))
                            TextButton(onClick = {
                                state = VoiceState.IDLE
                                transcript = ""
                                workflowName = ""
                                workflowDesc = ""
                            }) { Text("Create another") }
                        }
                    }
                }
            }

            if (error.isNotEmpty()) {
                Spacer(modifier = Modifier.height(16.dp))
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer,
                    ),
                ) {
                    Text(
                        error,
                        modifier = Modifier.padding(12.dp),
                        color = MaterialTheme.colorScheme.onErrorContainer,
                    )
                }
            }
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            mediaRecorder?.release()
        }
    }
}
