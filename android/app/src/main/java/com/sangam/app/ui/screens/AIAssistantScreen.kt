package com.sangam.app.ui.screens

import com.sangam.app.ui.components.str

import com.sangam.app.ui.components.PrimaryButton
import com.sangam.app.ui.components.friendlyError
import com.sangam.app.ui.components.BackButton
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sangam.app.R
import com.sangam.app.network.ApiClient
import com.sangam.app.network.LLMMessage
import com.sangam.app.network.LLMRequest
import com.sangam.app.ui.theme.*
import kotlinx.coroutines.launch

data class ChatMessage(
    val role: String,
    val content: String,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AIAssistantScreen(
    onBack: () -> Unit = {},
) {
    val scope = rememberCoroutineScope()
    var messages by remember { mutableStateOf(listOf(
        ChatMessage("assistant", str(R.string.namaste_i_m_your_sangamitra_assistant))
    )) }
    var inputText by remember { mutableStateOf("") }
    var loading by remember { mutableStateOf(false) }
    val listState = rememberLazyListState()

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.size - 1)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(str(R.string.ai_assistant)) },
                navigationIcon = {
                    BackButton(onBack)
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
            )
        },
        bottomBar = {
            Surface(
                tonalElevation = 3.dp,
                shadowElevation = 8.dp,
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    OutlinedTextField(
                        value = inputText,
                        onValueChange = { inputText = it },
                        modifier = Modifier.weight(1f),
                        placeholder = { Text(str(R.string.ask_anything)) },
                        enabled = !loading,
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    PrimaryButton(
                        onClick = {
                            val userMsg = inputText.trim()
                            if (userMsg.isNotEmpty() && !loading) {
                                inputText = ""
                                messages = messages + ChatMessage("user", userMsg)
                                loading = true
                                scope.launch {
                                    try {
                                        val llmMessages = messages.map { LLMMessage(it.role, it.content) }
                                        val response = ApiClient.aiApi.llmComplete(
                                            LLMRequest(messages = llmMessages)
                                        )
                                        messages = messages + ChatMessage("assistant", response.content)
                                    } catch (e: Exception) {
                                        messages = messages + ChatMessage("assistant", friendlyError(e, str(R.string.get_an_answer)))
                                    }
                                    loading = false
                                }
                            }
                        },
                        enabled = !loading,
                    ) {
                        if (loading) {
                            CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                        } else {
                            Text(str(R.string.send))
                        }
                    }
                }
            }
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            state = listState,
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(vertical = 16.dp),
        ) {
            items(messages) { msg ->
                val isUser = msg.role == "user"
                if (isUser) {
                    Column(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalAlignment = Alignment.End,
                    ) {
                        Surface(
                            shape = RoundedCornerShape(
                                topStart = 16.dp,
                                topEnd = 4.dp,
                                bottomStart = 16.dp,
                                bottomEnd = 16.dp,
                            ),
                            color = SangamObsidian,
                        ) {
                            Text(
                                text = msg.content,
                                modifier = Modifier.padding(12.dp),
                                color = SangamPureWhite,
                            )
                        }
                    }
                } else {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.Top,
                    ) {
                        Image(
                            painter = painterResource(R.drawable.mascot_kite_idle),
                            contentDescription = str(R.string.kite_co_pilot),
                            modifier = Modifier.size(36.dp),
                            contentScale = ContentScale.Fit,
                        )
                        Surface(
                            shape = RoundedCornerShape(
                                topStart = 4.dp,
                                topEnd = 16.dp,
                                bottomStart = 16.dp,
                                bottomEnd = 16.dp,
                            ),
                            color = SangamAlabaster,
                            border = BorderStroke(1.dp, SangamBorder),
                            modifier = Modifier.weight(1f, fill = false),
                        ) {
                            Text(
                                text = msg.content,
                                modifier = Modifier.padding(12.dp),
                                color = SangamObsidian,
                            )
                        }
                    }
                }
            }
            if (loading) {
                item {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Image(
                            painter = painterResource(R.drawable.mascot_kite_thinking),
                            contentDescription = str(R.string.kite_thinking),
                            modifier = Modifier.size(36.dp),
                            contentScale = ContentScale.Fit,
                        )
                        Surface(
                            shape = RoundedCornerShape(4.dp, 16.dp, 16.dp, 16.dp),
                            color = SangamAlabaster,
                            border = BorderStroke(1.dp, SangamBorder),
                        ) {
                            Row(
                                modifier = Modifier.padding(12.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(14.dp),
                                    strokeWidth = 2.dp,
                                    color = SangamObsidian,
                                )
                                Text(
                                    str(R.string.thinking),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = SangamMuted,
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
