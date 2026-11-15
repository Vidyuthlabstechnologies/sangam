package com.sangam.app.ui.screens

import com.sangam.app.ui.components.str

import com.sangam.app.ui.components.friendlyError
import com.sangam.app.ui.components.BackButton
import com.sangam.app.ui.components.ErrorState
import com.sangam.app.ui.components.StatusLabel
import com.sangam.app.ui.components.humanize
import androidx.compose.ui.text.style.TextOverflow
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
    val workflow_name: String,
    val status: String,
    val required_actors: List<String>,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ApprovalsScreen(onWorkflowClick: (String) -> Unit, onBack: () -> Unit = {}) {
    val scope = rememberCoroutineScope()
    var approvals by remember { mutableStateOf<List<ApprovalListItem>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }

    suspend fun refresh() {
        try {
            val resp = ApiClient.api.listWorkflows(pageSize = 50)
            // Gson ignores Kotlin defaults, so a missing list arrives as null.
            approvals = resp.items.flatMap { wf ->
                @Suppress("USELESS_ELVIS")
                (wf.approvals ?: emptyList()).map { ApprovalListItem(it.id, wf.id, wf.name, it.status, it.required_actors) }
            }
            error = null
        } catch (e: Exception) {
            error = friendlyError(e, str(R.string.load_approvals))
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
                title = { Text(str(R.string.approvals)) },
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
            ) { CircularProgressIndicator() }

            error != null -> Box(
                Modifier.fillMaxSize().padding(padding),
                contentAlignment = Alignment.Center,
            ) {
                ErrorState(error!!, onRetry = {
                    loading = true
                    error = null
                    scope.launch { refresh() }
                })
            }

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
                        contentDescription = null,
                        modifier = Modifier.size(130.dp),
                        contentScale = ContentScale.Fit
                    )
                    Spacer(Modifier.height(14.dp))
                    Text(
                        str(R.string.nothing_to_approve),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                    Spacer(Modifier.height(4.dp))
                    Text(
                        str(R.string.requests_that_need_your_decision_will),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center
                    )
                }
            }

            else -> {
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(approvals, key = { it.id }) { a ->
                        Card(
                            onClick = { onWorkflowClick(a.workflow_id) },
                            modifier = Modifier.fillMaxWidth(),
                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                            border = CardDefaults.outlinedCardBorder(),
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(16.dp),
                                horizontalArrangement = Arrangement.spacedBy(12.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        a.workflow_name,
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.SemiBold,
                                        maxLines = 3,
                                        overflow = TextOverflow.Ellipsis,
                                    )
                                    Spacer(Modifier.height(2.dp))
                                    Text(
                                        if (a.status.equals("pending", true)) str(R.string.tap_to_review_and_decide) else str(R.string.tap_to_see_details),
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                                StatusLabel(approvalStatusLabel(a.status))
                            }
                        }
                    }
                }
            }
        }
    }
}

/** "pending" -> "Waiting", the words an owner uses. */
fun approvalStatusLabel(status: String): String = when (status.lowercase()) {
    "pending" -> str(R.string.waiting)
    "approved" -> str(R.string.approved)
    "rejected" -> str(R.string.rejected)
    "escalated" -> str(R.string.escalated)
    else -> humanize(status)
}
