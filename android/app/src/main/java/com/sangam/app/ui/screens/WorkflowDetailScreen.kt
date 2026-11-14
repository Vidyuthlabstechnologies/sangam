package com.sangam.app.ui.screens

import com.sangam.app.ui.components.friendlyError
import com.sangam.app.ui.components.BackButton
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Payment
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sangam.app.network.ApiClient
import com.sangam.app.network.RealtimeClient
import com.sangam.app.network.WorkflowResponse
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WorkflowDetailScreen(
    workflowId: String,
    onBack: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var wf by remember { mutableStateOf<WorkflowResponse?>(null) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }

    suspend fun load() {
        try {
            wf = ApiClient.api.getWorkflow(workflowId)
        } catch (e: Exception) {
            error = friendlyError(e, "load this workflow")
        }
        loading = false
    }

    LaunchedEffect(workflowId) {
        load()
        RealtimeClient.subscribeWorkflow(workflowId)
        RealtimeClient.events.collect { evt ->
            if (evt.data.optString("workflow_id") == workflowId) {
                load()
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(wf?.name ?: "Workflow")
                        if (wf != null) {
                            Spacer(Modifier.width(8.dp))
                            AssistChip(
                                onClick = {},
                                label = { Text(wf!!.state, style = MaterialTheme.typography.labelSmall) },
                            )
                        }
                    }
                },
                navigationIcon = {
                    BackButton(onBack)
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
            )
        }
    ) { padding ->
        when {
            loading -> Box(
                Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) {
                CircularProgressIndicator()
            }
            error != null -> Box(
                Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) {
                Text("$error", color = MaterialTheme.colorScheme.error)
            }
            wf != null -> {
                val workflow = wf!!
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .padding(16.dp)
                        .verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(16.dp)) {
                            Text(
                                "Details",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.Bold,
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            DetailRow("State", workflow.state)
                            DetailRow("Phase", workflow.current_phase)
                            DetailRow("Phases", workflow.phases.joinToString(", "))
                        }
                    }

                    if (workflow.approvals.isNotEmpty()) {
                        Card(modifier = Modifier.fillMaxWidth()) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Text(
                                    "Approvals",
                                    style = MaterialTheme.typography.titleLarge,
                                    fontWeight = FontWeight.Bold,
                                )
                                Spacer(modifier = Modifier.height(8.dp))
                                workflow.approvals.forEach { a ->
                                    Row(
                                        Modifier.fillMaxWidth().padding(vertical = 4.dp),
                                        verticalAlignment = Alignment.CenterVertically,
                                    ) {
                                        AssistChip(
                                            onClick = {},
                                            label = { Text(a.status) },
                                            modifier = Modifier.padding(end = 8.dp),
                                        )
                                        Text(
                                            a.required_actors.joinToString(),
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                }
                            }
                        }
                    }

                }
            }
        }
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Text("$label: ", fontWeight = FontWeight.Medium, modifier = Modifier.width(100.dp))
        Text(value, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
