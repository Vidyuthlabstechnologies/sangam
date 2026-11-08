package com.sangam.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.sangam.app.network.ApiClient
import com.sangam.app.network.RealtimeClient
import com.sangam.app.network.WorkflowResponse
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    onNavigateToOnboarding: () -> Unit = {},
    onNavigateToCallInbox: () -> Unit = {},
    onNavigateToWorkflows: () -> Unit = {},
    onNavigateToApprovals: () -> Unit = {},
    onNavigateToActors: () -> Unit = {},
    onNavigateToAIAssistant: () -> Unit = {},
    onNavigateToVoiceWorkflow: () -> Unit = {},
    onNavigateToVendors: () -> Unit = {},
) {
    val scope = rememberCoroutineScope()
    var workflows by remember { mutableStateOf<List<WorkflowResponse>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var wsState by remember { mutableStateOf("") }

    suspend fun refresh() {
        try {
            val response = ApiClient.api.listWorkflows(pageSize = 10)
            workflows = response.items
        } catch (_: Exception) { }
    }

    LaunchedEffect(Unit) {
        refresh()
        loading = false
        RealtimeClient.events.collect { evt ->
            when (evt.event) {
                "workflow_update", "approval_update", "connected" -> refresh()
            }
        }
    }

    LaunchedEffect(Unit) {
        RealtimeClient.state.collect { state ->
            wsState = when (state) {
                is com.sangam.app.network.RealtimeState.Connected -> "LIVE"
                is com.sangam.app.network.RealtimeState.Connecting -> "CONNECTING"
                is com.sangam.app.network.RealtimeState.Disconnected -> ""
                is com.sangam.app.network.RealtimeState.Error -> "OFFLINE"
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("SANGAMITRA", style = MaterialTheme.typography.headlineLarge)
                        if (wsState.isNotEmpty()) {
                            Spacer(Modifier.width(8.dp))
                            Text(
                                wsState,
                                style = MaterialTheme.typography.labelSmall,
                                color = if (wsState.contains("LIVE"))
                                    MaterialTheme.colorScheme.primary
                                else MaterialTheme.colorScheme.error,
                            )
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
            )
        },
        bottomBar = {
            NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                NavigationBarItem(
                    selected = true,
                    onClick = {},
                    icon = { Icon(Icons.Default.Home, contentDescription = "Home") },
                    label = { Text("Home") },
                )
                NavigationBarItem(
                    selected = false,
                    onClick = onNavigateToOnboarding,
                    icon = { Icon(Icons.Default.Call, contentDescription = "Voice Agent") },
                    label = { Text("Voice Agent") },
                )
                NavigationBarItem(
                    selected = false,
                    onClick = onNavigateToCallInbox,
                    icon = { Icon(Icons.Default.Inbox, contentDescription = "Call Inbox") },
                    label = { Text("Call Inbox") },
                )
                NavigationBarItem(
                    selected = false,
                    onClick = onNavigateToWorkflows,
                    icon = { Icon(Icons.Default.List, contentDescription = "Workflows") },
                    label = { Text("Workflows") },
                )
                NavigationBarItem(
                    selected = false,
                    onClick = onNavigateToVendors,
                    icon = { Icon(Icons.Default.Business, contentDescription = "Vendors") },
                    label = { Text("Vendors") },
                )
            }
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Card(
                    onClick = onNavigateToOnboarding,
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.primary,
                        contentColor = MaterialTheme.colorScheme.onPrimary,
                    ),
                ) {
                    Column(
                        modifier = Modifier.padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text(
                                "ZERO-PROMPT CALLING AGENT STUDIO",
                                style = MaterialTheme.typography.labelLarge,
                            )
                            Icon(Icons.Default.ArrowForward, contentDescription = "Launch")
                        }
                        Text(
                            "Deploy AI Sales & Receptionist Agent in 60s",
                            style = MaterialTheme.typography.headlineMedium,
                            fontWeight = FontWeight.Bold,
                        )
                        Text(
                            "Live lines: +91 80 6427 0314 (Abhishek Industries) · +91 80 6427 0306 (Surya Enterprises) · Choose Mitra, Swar, or Vani mascot · Plans from ₹799 (60% Profit Economics)",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }

            item {
                Text(
                    "Command Center",
                    style = MaterialTheme.typography.displayLarge,
                )
                Spacer(modifier = Modifier.height(8.dp))
            }

            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    StatCard("Active", workflows.count { it.state == "active" }, MaterialTheme.colorScheme.primary)
                    StatCard("Pending", workflows.count { it.state in listOf("draft", "paused") }, MaterialTheme.colorScheme.tertiary)
                    StatCard("Done", workflows.count { it.state == "completed" }, MaterialTheme.colorScheme.secondary)
                }
            }

            item {
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    ElevatedCard(
                        onClick = onNavigateToAIAssistant,
                        modifier = Modifier.weight(1f),
                    ) {
                        Column(
                            modifier = Modifier.padding(16.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Icon(
                                Icons.Default.Smartphone,
                                contentDescription = "AI",
                                modifier = Modifier.size(32.dp),
                                tint = MaterialTheme.colorScheme.primary,
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Text("AI Assistant", fontWeight = FontWeight.Bold)
                            Text("Chat with Sarvam LLM", style = MaterialTheme.typography.bodySmall,
                                 color = MaterialTheme.colorScheme.onSurfaceVariant,
                                 textAlign = TextAlign.Center)
                        }
                    }
                    ElevatedCard(
                        onClick = onNavigateToVoiceWorkflow,
                        modifier = Modifier.weight(1f),
                    ) {
                        Column(
                            modifier = Modifier.padding(16.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Icon(
                                Icons.Default.Mic,
                                contentDescription = "Voice",
                                modifier = Modifier.size(32.dp),
                                tint = MaterialTheme.colorScheme.primary,
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Text("Voice Workflow", fontWeight = FontWeight.Bold)
                            Text("Create with speech", style = MaterialTheme.typography.bodySmall,
                                 color = MaterialTheme.colorScheme.onSurfaceVariant,
                                 textAlign = TextAlign.Center)
                        }
                    }
                }
            }

            item {
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        "Recent Workflows",
                        style = MaterialTheme.typography.headlineMedium,
                    )
                    if (wsState.contains("LIVE")) {
                        Text(
                            "LIVE",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.primary,
                        )
                    }
                }
            }

            if (loading) {
                item {
                    Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
            } else if (workflows.isEmpty()) {
                item {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                    ) {
                        Text(
                            "No workflows yet. Try voice creation!",
                            modifier = Modifier.padding(24.dp),
                            style = MaterialTheme.typography.bodyLarge,
                        )
                    }
                }
            } else {
                items(workflows) { wf ->
                    WorkflowCard(wf)
                }
            }
        }
    }
}

@Composable
fun RowScope.StatCard(label: String, count: Int, color: Color) {
    Card(
        modifier = Modifier.weight(1f),
        colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.1f)),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                count.toString(),
                style = MaterialTheme.typography.displayLarge,
                color = color,
                fontWeight = FontWeight.Bold,
            )
            Text(
                label,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
fun WorkflowCard(workflow: WorkflowResponse) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        onClick = {},
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    workflow.name,
                    style = MaterialTheme.typography.titleMedium,
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    "Phase: ${workflow.current_phase}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            AssistChip(
                onClick = {},
                label = {
                    Text(workflow.state, style = MaterialTheme.typography.labelLarge)
                },
            )
        }
    }
}
