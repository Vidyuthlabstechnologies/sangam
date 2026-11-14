package com.sangam.app.ui.screens

import com.sangam.app.ui.components.str
import com.sangam.app.ui.components.LanguageDialog
import androidx.compose.material.icons.filled.Translate

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
    var showLanguages by remember { mutableStateOf(false) }
    if (showLanguages) LanguageDialog(onDismiss = { showLanguages = false })
    if (confirmSignOut) {
        AlertDialog(
            onDismissRequest = { confirmSignOut = false },
            title = { Text(str(R.string.sign_out)) },
            text = { Text(str(R.string.you_can_sign_back_in_any)) },
            confirmButton = {
                TextButton(onClick = {
                    confirmSignOut = false
                    FirebaseSession.signOut(context)
                    onSignOut()
                }) { Text(str(R.string.sign_out_2)) }
            },
            dismissButton = {
                TextButton(onClick = { confirmSignOut = false }) { Text(str(R.string.cancel)) }
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
            loadError = friendlyError(e, str(R.string.load_your_workflows))
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
                            str(R.string.sangamitra),
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.Bold,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.weight(1f, fill = false),
                        )
                        if (wsState == "OFFLINE") {
                            Spacer(Modifier.width(8.dp))
                            Text(
                                str(R.string.offline),
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.error,
                                maxLines = 1,
                            )
                        }
                    }
                },
                actions = {
                    IconButton(onClick = { showLanguages = true }) {
                        Icon(Icons.Default.Translate, contentDescription = str(R.string.app_language))
                    }
                    IconButton(onClick = { confirmSignOut = true }) {
                        Icon(Icons.AutoMirrored.Filled.Logout, contentDescription = str(R.string.sign_out_2))
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
                    Triple(Icons.Default.Home, str(R.string.home), {}),
                    Triple(Icons.Default.SupportAgent, str(R.string.agent), onNavigateToOnboarding),
                    Triple(Icons.Default.Inbox, str(R.string.calls), onNavigateToCallInbox),
                    Triple(Icons.AutoMirrored.Filled.List, str(R.string.workflows), onNavigateToWorkflows),
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
                                str(R.string.your_voice_agent),
                                style = MaterialTheme.typography.labelLarge,
                                color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.8f),
                            )
                            Text(
                                str(R.string.answer_every_call_in_your_customer),
                                style = MaterialTheme.typography.headlineMedium,
                                fontWeight = FontWeight.Bold,
                            )
                            Text(
                                str(R.string.paste_your_website_pick_a_plan),
                                style = MaterialTheme.typography.bodyMedium,
                            )
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(str(R.string.set_up_or_change), style = MaterialTheme.typography.labelLarge)
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
                    str(R.string.overview),
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
                    StatCard(str(R.string.active), workflows.count { it.state == "active" }, MaterialTheme.colorScheme.primary)
                    StatCard(str(R.string.waiting), workflows.count { it.state in listOf("draft", "paused") }, MaterialTheme.colorScheme.tertiary)
                    StatCard(str(R.string.done), workflows.count { it.state == "completed" }, MaterialTheme.colorScheme.secondary)
                }
            }

            item {
                ShortcutGrid(
                    listOf(
                        Shortcut(Icons.Default.Call, str(R.string.talk_to_agents), str(R.string.test_live_or_place_a_call), onNavigateToVoiceAgents),
                        Shortcut(Icons.Default.Campaign, str(R.string.call_campaigns), str(R.string.call_a_list_of_customers), onNavigateToCampaigns),
                        Shortcut(Icons.Default.Mic, str(R.string.voice_workflow), str(R.string.speak_to_create_one), onNavigateToVoiceWorkflow),
                        Shortcut(Icons.Default.CheckCircle, str(R.string.approvals), str(R.string.waiting_for_you), onNavigateToApprovals),
                        Shortcut(Icons.Default.AutoAwesome, str(R.string.ai_assistant), str(R.string.ask_or_draft), onNavigateToAIAssistant),
                        Shortcut(Icons.Default.People, str(R.string.people), str(R.string.your_team_and_agents), onNavigateToActors),
                        Shortcut(Icons.Default.Business, str(R.string.vendors), str(R.string.suppliers_and_licences), onNavigateToVendors),
                    )
                )
            }

            item {
                Text(
                    str(R.string.recent_workflows),
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
                            Text(str(R.string.no_workflows_yet), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                            Text(
                                str(R.string.tap_here_and_say_what_should),
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
    "active" -> str(R.string.running)
    "draft" -> str(R.string.draft)
    "paused" -> str(R.string.paused)
    "completed" -> str(R.string.done)
    "failed" -> str(R.string.failed)
    else -> state.replaceFirstChar { it.uppercase() }
}

fun workflowPhaseLabel(phase: String): String = when (phase.lowercase()) {
    "initiation" -> str(R.string.phase_initiation)
    "approval" -> str(R.string.phase_approval)
    "execution" -> str(R.string.phase_execution)
    "verification" -> str(R.string.phase_verification)
    "settlement" -> str(R.string.phase_settlement)
    "exception" -> str(R.string.phase_exception)
    else -> phase.lowercase().replace('_', ' ').replaceFirstChar { it.uppercase() }
}

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
                    str(R.string.stage, workflowPhaseLabel(workflow.current_phase)),
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
