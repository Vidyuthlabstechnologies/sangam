package com.sangam.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.sangam.app.network.ActorResponse
import com.sangam.app.network.ApiClient
import com.sangam.app.network.ApprovalResponse
import com.sangam.app.network.RealtimeClient
import com.sangam.app.network.WorkflowResponse
import com.sangam.app.ui.components.BackButton
import com.sangam.app.ui.components.ErrorState
import com.sangam.app.ui.components.PrimaryButton
import com.sangam.app.ui.components.SecondaryButton
import com.sangam.app.ui.components.StatusLabel
import com.sangam.app.ui.components.friendlyError
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WorkflowDetailScreen(
    workflowId: String,
    onBack: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var wf by remember { mutableStateOf<WorkflowResponse?>(null) }
    var people by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var actionError by remember { mutableStateOf<String?>(null) }
    var busyApproval by remember { mutableStateOf<String?>(null) }

    suspend fun load() {
        try {
            wf = ApiClient.api.getWorkflow(workflowId)
            error = null
        } catch (e: Exception) {
            error = friendlyError(e, "load this workflow")
        }
        loading = false
    }

    fun decide(approval: ApprovalResponse, approve: Boolean) {
        scope.launch {
            busyApproval = approval.id
            actionError = null
            try {
                if (approve) ApiClient.api.approveApproval(approval.id) else ApiClient.api.rejectApproval(approval.id)
                load()
            } catch (e: Exception) {
                actionError = friendlyError(e, if (approve) "approve this" else "reject this")
            }
            busyApproval = null
        }
    }

    LaunchedEffect(workflowId) {
        // Names for actor ids; the screen still works if this fails.
        runCatching { people = ApiClient.api.listActors().associate { it.id to it.name } }
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
                title = { Text("Workflow", maxLines = 1) },
                navigationIcon = { BackButton(onBack) },
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
            error != null && wf == null -> Box(
                Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) {
                ErrorState(error!!, onRetry = {
                    loading = true
                    scope.launch { load() }
                })
            }
            wf != null -> {
                val workflow = wf!!
                @Suppress("USELESS_ELVIS")
                val approvals = workflow.approvals ?: emptyList()
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .verticalScroll(rememberScrollState())
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    // Name gets its own line: in the top bar it was cut to "Approve site vi..."
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(
                            workflow.name,
                            style = MaterialTheme.typography.headlineMedium,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.semantics { heading() },
                        )
                        StatusLabel(workflowStateLabel(workflow.state))
                        if (!workflow.description.isNullOrBlank()) {
                            Text(
                                workflow.description,
                                style = MaterialTheme.typography.bodyLarge,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }

                    if (actionError != null) {
                        Text(
                            actionError!!,
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.semantics { liveRegion = LiveRegionMode.Assertive },
                        )
                    }

                    approvals.filter { it.status.equals("pending", true) }.forEach { a ->
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
                            border = CardDefaults.outlinedCardBorder(),
                        ) {
                            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                                Text("Needs your decision", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                                Text(
                                    "Asked of: " + a.required_actors.joinToString { people[it] ?: "a team member" },
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                                val busy = busyApproval == a.id
                                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    SecondaryButton(onClick = { decide(a, false) }, enabled = !busy, modifier = Modifier.weight(1f)) {
                                        Text("Reject", maxLines = 1)
                                    }
                                    PrimaryButton(onClick = { decide(a, true) }, enabled = !busy, modifier = Modifier.weight(1f)) {
                                        Text("Approve", maxLines = 1)
                                    }
                                }
                            }
                        }
                    }

                    Section("Progress") {
                        workflow.phases.forEachIndexed { i, phase ->
                            val currentIndex = workflow.phases.indexOfFirst { it.equals(workflow.current_phase, true) }
                            val status = when {
                                currentIndex < 0 -> ""
                                i < currentIndex -> "Done"
                                i == currentIndex -> "Now"
                                else -> "Next"
                            }
                            DetailRow("${i + 1}. ${workflowPhaseLabel(phase)}", status, emphasise = i == currentIndex)
                        }
                    }

                    val decided = approvals.filterNot { it.status.equals("pending", true) }
                    if (decided.isNotEmpty()) {
                        Section("Decisions") {
                            decided.forEach { a ->
                                DetailRow(
                                    a.required_actors.joinToString { people[it] ?: "Team member" },
                                    approvalStatusLabel(a.status),
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun Section(title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = CardDefaults.outlinedCardBorder(),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.semantics { heading() },
            )
            Spacer(modifier = Modifier.height(8.dp))
            content()
        }
    }
}

@Composable
private fun DetailRow(label: String, value: String, emphasise: Boolean = false) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            label,
            fontWeight = if (emphasise) FontWeight.SemiBold else FontWeight.Normal,
            style = MaterialTheme.typography.bodyLarge,
            modifier = Modifier.weight(1f),
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        Text(
            value,
            style = MaterialTheme.typography.bodyLarge,
            color = if (emphasise) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant,
            fontWeight = if (emphasise) FontWeight.SemiBold else FontWeight.Normal,
        )
    }
}
