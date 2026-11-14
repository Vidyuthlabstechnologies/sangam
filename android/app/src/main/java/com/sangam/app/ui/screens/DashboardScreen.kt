package com.sangam.app.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import com.sangam.app.ui.components.ErrorState
import com.sangam.app.ui.components.friendlyError
import com.sangam.app.R
import com.sangam.app.network.ApiClient
import com.sangam.app.network.FirebaseSession
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
    onNavigateToVoiceAgents: () -> Unit = {},
    onNavigateToCampaigns: () -> Unit = {},
    onNavigateToVendors: () -> Unit = {},
    onOpenWorkflow: (String) -> Unit = {},
    onSignOut: () -> Unit = {},
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    var confirmSignOut by remember { mutableStateOf(false) }
    if (confirmSignOut) {
        AlertDialog(
            onDismissRequest = { confirmSignOut = false },
            title = { Text("Sign out?") },
            text = { Text("You can sign back in any time with Google or your email.") },
            confirmButton = {
                TextButton(onClick = {
                    confirmSignOut = false
                    FirebaseSession.signOut(context)
                    onSignOut()
                }) { Text("Sign out") }
            },
            dismissButton = {
                TextButton(onClick = { confirmSignOut = false }) { Text("Cancel") }
            },
        )
    }
    val scope = rememberCoroutineScope()
    var workflows by remember { mutableStateOf<List<WorkflowResponse>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var loadError by remember { mutableStateOf<String?>(null) }
    var wsState by remember { mutableStateOf("") }

    suspend fun refresh() {
        try {
            val response = ApiClient.api.listWorkflows(pageSize = 10)
            workflows = response.items
            loadError = null
        } catch (e: Exception) {
            loadError = friendlyError(e, "load your workflows")
        }
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

    fun retry() {
        scope.launch {
            loading = true
            refresh()
            loading = false
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            "Sangamitra",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.Bold,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.weight(1f, fill = false),
                        )
                        if (wsState == "OFFLINE") {
                            Spacer(Modifier.width(8.dp))
                            Text(
                                "Offline",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.error,
                                maxLines = 1,
                            )
                        }
                    }
                },
                actions = {
                    IconButton(onClick = { confirmSignOut = true }) {
                        Icon(Icons.AutoMirrored.Filled.Logout, contentDescription = "Sign out")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
            )
        },
        bottomBar = {
            // Four short, single-line labels. Five long ones broke mid-word ("Workfl-ows")
            // on 320dp phones with large text. Vendors moved to a card below.
            NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                listOf(
                    Triple(Icons.Default.Home, "Home", {}),
                    Triple(Icons.Default.SupportAgent, "Agent", onNavigateToOnboarding),
                    Triple(Icons.Default.Inbox, "Calls", onNavigateToCallInbox),
                    Triple(Icons.AutoMirrored.Filled.List, "Workflows", onNavigateToWorkflows),
                ).forEachIndexed { index, (icon, label, onClick) ->
                    NavigationBarItem(
                        selected = index == 0,
                        onClick = onClick,
                        icon = { Icon(icon, contentDescription = null) },
                        label = { Text(label, maxLines = 1, softWrap = false, overflow = TextOverflow.Ellipsis) },
                    )
                }
            }
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
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
                    Row(
                        modifier = Modifier.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(
                                "Your voice agent",
                                style = MaterialTheme.typography.labelLarge,
                                color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.8f),
                            )
                            Text(
                                "Answer every call, in your customer's language",
                                style = MaterialTheme.typography.headlineMedium,
                                fontWeight = FontWeight.Bold,
                            )
                            Text(
                                "Paste your website, pick a plan and get a number your agent answers. Takes about a minute.",
                                style = MaterialTheme.typography.bodyMedium,
                            )
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text("Set up or change", style = MaterialTheme.typography.labelLarge)
                                Spacer(Modifier.width(4.dp))
                                Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = null, modifier = Modifier.size(16.dp))
                            }
                        }
                        Image(
                            painter = painterResource(id = R.drawable.mascot_kite_idle),
                            contentDescription = null,
                            modifier = Modifier.size(72.dp),
                            contentScale = ContentScale.Fit,
                        )
                    }
                }
            }

            item {
                Text(
                    "Overview",
                    style = MaterialTheme.typography.headlineMedium,
                    modifier = Modifier
                        .padding(top = 8.dp)
                        .semantics { heading() },
                )
            }

            item {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(IntrinsicSize.Min),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    StatCard("Active", workflows.count { it.state == "active" }, MaterialTheme.colorScheme.primary)
                    StatCard("Waiting", workflows.count { it.state in listOf("draft", "paused") }, MaterialTheme.colorScheme.tertiary)
                    StatCard("Done", workflows.count { it.state == "completed" }, MaterialTheme.colorScheme.secondary)
                }
            }

            item {
                ShortcutGrid(
                    listOf(
                        Shortcut(Icons.Default.Call, "Talk to agents", "Test live or place a call", onNavigateToVoiceAgents),
                        Shortcut(Icons.Default.Campaign, "Call campaigns", "Call a list of customers", onNavigateToCampaigns),
                        Shortcut(Icons.Default.Mic, "Voice workflow", "Speak to create one", onNavigateToVoiceWorkflow),
                        Shortcut(Icons.Default.CheckCircle, "Approvals", "Waiting for you", onNavigateToApprovals),
                        Shortcut(Icons.Default.AutoAwesome, "AI assistant", "Ask or draft", onNavigateToAIAssistant),
                        Shortcut(Icons.Default.People, "People", "Your team and agents", onNavigateToActors),
                        Shortcut(Icons.Default.Business, "Vendors", "Suppliers and licences", onNavigateToVendors),
                    )
                )
            }

            item {
                Text(
                    "Recent workflows",
                    style = MaterialTheme.typography.headlineMedium,
                    modifier = Modifier
                        .padding(top = 8.dp)
                        .semantics { heading() },
                )
            }

            if (loading) {
                item {
                    Box(Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator()
                    }
                }
            } else if (loadError != null && workflows.isEmpty()) {
                item { ErrorState(loadError!!, onRetry = ::retry) }
            } else if (workflows.isEmpty()) {
                item {
                    Card(
                        onClick = onNavigateToVoiceWorkflow,
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                    ) {
                        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text("No workflows yet", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                            Text(
                                "Tap here and say what should happen, for example \"When a caller books a visit, ask me to approve it\".",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            } else {
                items(workflows, key = { it.id }) { wf ->
                    WorkflowCard(wf, onClick = { onOpenWorkflow(wf.id) })
                }
            }
        }
    }
}

private data class Shortcut(
    val icon: ImageVector,
    val title: String,
    val subtitle: String,
    val onClick: () -> Unit,
)

/** Two columns of equal-height tiles, so a two-line title never makes a ragged grid. */
@Composable
private fun ShortcutGrid(items: List<Shortcut>) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        items.chunked(2).forEach { row ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(IntrinsicSize.Min),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                row.forEach { item ->
                    ElevatedCard(
                        onClick = item.onClick,
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxHeight(),
                    ) {
                        Column(
                            modifier = Modifier.padding(14.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            Icon(item.icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                            Text(item.title, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                            Text(
                                item.subtitle,
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

@Composable
fun RowScope.StatCard(label: String, count: Int, color: Color) {
    Card(
        modifier = Modifier
            .weight(1f)
            .fillMaxHeight()
            .semantics(mergeDescendants = true) {},
        colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.1f)),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 12.dp, horizontal = 8.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                count.toString(),
                style = MaterialTheme.typography.headlineLarge,
                color = if (color == MaterialTheme.colorScheme.tertiary) Color(0xFF92400E) else color,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
            )
            Text(
                label,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                softWrap = false,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

/** Raw states from the backend ("active", "draft") as words people use. */
fun workflowStateLabel(state: String): String = when (state.lowercase()) {
    "active" -> "Running"
    "draft" -> "Draft"
    "paused" -> "Paused"
    "completed" -> "Done"
    "failed" -> "Failed"
    else -> state.replaceFirstChar { it.uppercase() }
}

fun workflowPhaseLabel(phase: String): String =
    phase.lowercase().replace('_', ' ').replaceFirstChar { it.uppercase() }

@Composable
fun WorkflowCard(workflow: WorkflowResponse, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        onClick = onClick,
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
                    workflow.name,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    "Stage: ${workflowPhaseLabel(workflow.current_phase)}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            // A status label, not a button: an AssistChip looked tappable and did nothing.
            Surface(
                shape = RoundedCornerShape(8.dp),
                color = MaterialTheme.colorScheme.secondaryContainer,
            ) {
                Text(
                    workflowStateLabel(workflow.state),
                    style = MaterialTheme.typography.labelLarge,
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                    maxLines = 1,
                )
            }
        }
    }
}
