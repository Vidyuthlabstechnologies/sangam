package com.sangam.app.ui.screens

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import com.sangam.app.network.RealtimeClient
import kotlinx.coroutines.launch

data class ApprovalListItem(
    val id: String,
    val workflow_id: String,
    val status: String,
    val required_actors: List<String>,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ApprovalsScreen(onWorkflowClick: (String) -> Unit) {
    val scope = rememberCoroutineScope()
    var approvals by remember { mutableStateOf<List<ApprovalListItem>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }

    suspend fun refresh() {
        try {
            val resp = ApiClient.api.listWorkflows(pageSize = 50)
            approvals = resp.items.flatMap { wf ->
                wf.approvals.map { ApprovalListItem(it.id, wf.id, it.status, it.required_actors) }
            }
        } catch (e: Exception) {
            error = e.message
        }
        loading = false
    }

    LaunchedEffect(Unit) {
        refresh()
        RealtimeClient.events.collect { evt ->
            if (evt.event == "approval_update") {
                refresh()
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Approvals") },
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
            ) { CircularProgressIndicator() }

            error != null -> Box(
                Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) { Text("Error: $error", color = MaterialTheme.colorScheme.error) }

            approvals.isEmpty() -> Box(
                Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.padding(24.dp)
                ) {
                    Image(
                        painter = painterResource(id = R.drawable.mascot_kite_adjudicator),
                        contentDescription = "All Approvals Cleared",
                        modifier = Modifier.size(130.dp),
                        contentScale = ContentScale.Fit
                    )
                    Spacer(Modifier.height(14.dp))
                    Text(
                        "All Quorums Cleared!",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(Modifier.height(4.dp))
                    Text(
                        "Your Sarvam AI calling agents are handling all customer calls autonomously.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center
                    )
                }
            }

            else -> {
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(approvals) { a ->
                        Card(
                            onClick = { onWorkflowClick(a.workflow_id) },
                            modifier = Modifier.fillMaxWidth(),
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
                                        "Approval",
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.SemiBold,
                                    )
                                    Text(
                                        "Workflow: ${a.workflow_id.take(8)}...",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                                AssistChip(
                                    onClick = {},
                                    label = { Text(a.status) },
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
