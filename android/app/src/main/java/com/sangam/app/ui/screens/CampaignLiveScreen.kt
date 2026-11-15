package com.sangam.app.ui.screens

import com.sangam.app.R
import com.sangam.app.ui.components.str

import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sangam.app.network.ActiveCallDto
import com.sangam.app.network.ApiClient
import com.sangam.app.network.CampaignContactDetailDto
import com.sangam.app.network.CampaignContactDto
import com.sangam.app.network.CampaignLiveDto
import com.sangam.app.network.VersusTelecallerDto
import com.sangam.app.ui.theme.SangamCrimson
import com.sangam.app.ui.theme.SangamMuted
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private val SuccessGreen = Color(0xFF15803D)
private val LiveAmber = Color(0xFFD97706)

/** The live board: progress to the goal, every call in flight, and outcomes as they land. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CampaignLiveScreen(campaignId: String, onBack: () -> Unit = {}) {
    val scope = rememberCoroutineScope()
    var live by remember { mutableStateOf<CampaignLiveDto?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var openContact by remember { mutableStateOf<Pair<String, String>?>(null) } // id, name
    var confirmCancel by remember { mutableStateOf(false) }

    suspend fun load() {
        try {
            live = ApiClient.campaignApi.live(campaignId)
            error = null
        } catch (e: Exception) {
            error = describeCampaignError(e)
        }
    }

    // Polling also keeps the campaign dialling; see backend campaign_engine.
    LaunchedEffect(campaignId) {
        while (true) {
            load()
            val l = live
            val busy = l == null || l.campaign.isRunning || l.active.isNotEmpty()
            delay(if (busy) 2000L else 15000L)
        }
    }

    fun control(action: suspend () -> Unit) {
        scope.launch {
            try {
                action()
                load()
            } catch (e: Exception) {
                error = describeCampaignError(e)
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(live?.campaign?.name ?: str(R.string.campaign), maxLines = 1, overflow = TextOverflow.Ellipsis)
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = str(R.string.back))
                    }
                },
                actions = {
                    val c = live?.campaign
                    if (c?.status == "running") {
                        IconButton(onClick = { control { ApiClient.campaignApi.pause(campaignId) } }) {
                            Icon(Icons.Default.Pause, contentDescription = str(R.string.pause))
                        }
                    }
                    if (c?.status == "paused" || c?.status == "draft") {
                        IconButton(onClick = { control { ApiClient.campaignApi.resume(campaignId) } }) {
                            Icon(Icons.Default.PlayArrow, contentDescription = str(R.string.resume))
                        }
                    }
                    if (c != null && c.status in setOf("running", "paused", "draft")) {
                        IconButton(onClick = { confirmCancel = true }) {
                            Icon(Icons.Default.Stop, contentDescription = str(R.string.stop_campaign))
                        }
                    }
                },
            )
        },
    ) { padding ->
        val l = live
        if (l == null) {
            Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                if (error != null) Text(error!!, color = SangamCrimson) else CircularProgressIndicator()
            }
            return@Scaffold
        }
        val c = l.campaign
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (l.simulated) {
                item {
                    Banner(str(R.string.simulation_no_real_calls_are_being), SangamMuted)
                }
            }
            c.hold_reason?.let { item { Banner(it, LiveAmber) } }
            error?.let { item { Banner(it, SangamCrimson) } }

            item { GoalCard(l) }
            item { StatsRow(l) }
            l.versus_telecaller?.takeIf { it.calls_finished > 0 }?.let { item { VersusCard(it) } }

            if (l.active.isNotEmpty()) {
                item {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        PulsingDot(LiveAmber)
                        Spacer(Modifier.width(8.dp))
                        Text(str(R.string.on_call_now, c.count("dialing")), style = MaterialTheme.typography.titleMedium)
                    }
                }
                items(l.active, key = { "a-" + it.id }) { call ->
                    ActiveCallRow(call, onClick = { openContact = call.id to call.name })
                }
            }
            if (l.recent.isNotEmpty()) {
                item { Text(str(R.string.latest_outcomes), style = MaterialTheme.typography.titleMedium) }
                items(l.recent, key = { "r-" + it.id }) { contact ->
                    OutcomeRow(contact, goal = c.goal, onClick = { openContact = contact.id to contact.name })
                }
            }
        }
    }

    openContact?.let { (id, name) ->
        CallDetailDialog(campaignId, id, name, onDismiss = { openContact = null })
    }
    if (confirmCancel) {
        AlertDialog(
            onDismissRequest = { confirmCancel = false },
            title = { Text(str(R.string.stop_this_campaign)) },
            text = { Text(str(R.string.nobody_else_on_the_list_is)) },
            confirmButton = {
                TextButton(onClick = {
                    confirmCancel = false
                    control { ApiClient.campaignApi.cancel(campaignId) }
                }) { Text(str(R.string.stop)) }
            },
            dismissButton = { TextButton(onClick = { confirmCancel = false }) { Text(str(R.string.keep_calling)) } },
        )
    }
}

@Composable
private fun Banner(text: String, color: Color) {
    Surface(color = color.copy(alpha = 0.10f), shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) {
        Text(text, color = color, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(12.dp))
    }
}

@Composable
private fun GoalCard(l: CampaignLiveDto) {
    val c = l.campaign
    val progress by animateFloatAsState(l.progress.toFloat().coerceIn(0f, 1f), animationSpec = tween(800), label = "goal")
    val reached = c.status == "target_reached"
    ElevatedCard(modifier = Modifier.fillMaxWidth()) {
        Row(modifier = Modifier.padding(20.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(contentAlignment = Alignment.Center, modifier = Modifier.size(132.dp)) {
                CircularProgressIndicator(
                    progress = { progress },
                    modifier = Modifier.fillMaxSize(),
                    strokeWidth = 12.dp,
                    color = if (reached) SuccessGreen else MaterialTheme.colorScheme.primary,
                    trackColor = MaterialTheme.colorScheme.surfaceVariant,
                )
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("${c.success_count}", fontSize = 40.sp, fontWeight = FontWeight.Bold)
                    Text(str(R.string.of, c.target_count), style = MaterialTheme.typography.bodyMedium, color = SangamMuted)
                }
            }
            Spacer(Modifier.width(20.dp))
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(c.goal, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                CampaignStatusChip(c)
                Text(
                    if (reached) str(R.string.goal_reached_in, formatDuration(l.versus_telecaller?.ai_elapsed_seconds ?: 0))
                    else str(R.string.lines_contacts, c.concurrency, c.contacts_total),
                    style = MaterialTheme.typography.bodySmall,
                    color = if (reached) SuccessGreen else SangamMuted,
                )
            }
        }
    }
}

@Composable
private fun StatsRow(l: CampaignLiveDto) {
    val c = l.campaign
    val finished = listOf("connected", "no_answer", "busy", "failed").sumOf { c.count(it) }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
        Stat(str(R.string.on_call), c.count("dialing"), LiveAmber, Modifier.weight(1f))
        Stat(str(R.string.called), finished, MaterialTheme.colorScheme.onSurface, Modifier.weight(1f))
        Stat(str(R.string.answered), c.count("connected"), MaterialTheme.colorScheme.primary, Modifier.weight(1f))
        Stat(str(R.string.yes), c.success_count, SuccessGreen, Modifier.weight(1f))
    }
}

@Composable
private fun Stat(label: String, value: Int, color: Color, modifier: Modifier) {
    OutlinedCard(modifier = modifier) {
        Column(Modifier.padding(vertical = 12.dp).fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
            Text("$value", fontSize = 22.sp, fontWeight = FontWeight.Bold, color = color)
            Text(label, style = MaterialTheme.typography.labelSmall, color = SangamMuted, textAlign = TextAlign.Center)
        }
    }
}

@Composable
private fun VersusCard(v: VersusTelecallerDto) {
    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(str(R.string.versus_a_telecaller), fontWeight = FontWeight.Bold)
            Row {
                Column(Modifier.weight(1f)) {
                    Text(str(R.string.your_ai_agent), style = MaterialTheme.typography.labelMedium, color = SangamMuted)
                    Text(formatDuration(v.ai_elapsed_seconds), fontSize = 24.sp, fontWeight = FontWeight.Bold,
                        color = SuccessGreen)
                }
                Column(Modifier.weight(1f)) {
                    Text(str(R.string.one_telecaller), style = MaterialTheme.typography.labelMedium, color = SangamMuted)
                    Text(formatDuration(v.one_telecaller_seconds), fontSize = 24.sp, fontWeight = FontWeight.Bold)
                }
            }
            Text(
                str(R.string.calls_done_keeping_this_pace_by, v.calls_finished, v.telecallers_to_match),
                style = MaterialTheme.typography.bodyMedium,
            )
            v.assumptions?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = SangamMuted) }
        }
    }
}

@Composable
private fun PulsingDot(color: Color) {
    val t = rememberInfiniteTransition(label = "pulse")
    val a by t.animateFloat(0.3f, 1f, infiniteRepeatable(tween(700), RepeatMode.Reverse), label = "alpha")
    Box(Modifier.size(10.dp).alpha(a).background(color, CircleShape))
}

@Composable
private fun ActiveCallRow(call: ActiveCallDto, onClick: () -> Unit) {
    ElevatedCard(onClick = onClick, modifier = Modifier.fillMaxWidth().animateContentSize()) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.Top) {
            Box(Modifier.padding(top = 6.dp)) { PulsingDot(if (call.phase == "ringing") SangamMuted else LiveAmber) }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(call.name.ifBlank { call.phone }, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f),
                        maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text(
                        if (call.phase == "ringing") str(R.string.ringing_clock, formatClock(call.elapsed_seconds)) else formatClock(call.elapsed_seconds),
                        style = MaterialTheme.typography.labelMedium,
                        color = SangamMuted,
                    )
                }
                Text(call.language ?: "", style = MaterialTheme.typography.labelSmall, color = SangamMuted)
                call.line?.let { line ->
                    Text(
                        if (line.role == "agent") str(R.string.agent_line, line.content) else str(R.string.customer_line, line.content),
                        style = MaterialTheme.typography.bodySmall,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
    }
}

@Composable
private fun OutcomeRow(contact: CampaignContactDto, goal: String, onClick: () -> Unit) {
    val (label, color) = outcomeLabel(contact, goal)
    ElevatedCard(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(contact.name.ifBlank { contact.phone }, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f),
                    maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(label, color = color, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
            }
            contact.summary?.let {
                Text(it, style = MaterialTheme.typography.bodySmall, color = SangamMuted, maxLines = 2,
                    overflow = TextOverflow.Ellipsis)
            }
        }
    }
}

private fun outcomeLabel(c: CampaignContactDto, goal: String): Pair<String, Color> = when {
    c.succeeded -> goal to SuccessGreen
    c.opted_out -> str(R.string.do_not_call) to SangamCrimson
    c.status == "connected" -> str(R.string.spoke) to Color(0xFF52525B)
    c.status == "no_answer" -> str(R.string.no_answer) to SangamMuted
    c.status == "busy" -> str(R.string.busy) to SangamMuted
    c.status == "failed" -> str(R.string.failed) to SangamCrimson
    c.status == "suppressed" -> str(R.string.on_dnd_2) to SangamMuted
    c.status == "skipped" -> str(R.string.not_needed) to SangamMuted
    else -> c.status to SangamMuted
}

@Composable
private fun CallDetailDialog(campaignId: String, contactId: String, name: String, onDismiss: () -> Unit) {
    var detail by remember { mutableStateOf<CampaignContactDetailDto?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(contactId) {
        while (true) {
            try {
                detail = ApiClient.campaignApi.contact(campaignId, contactId)
            } catch (e: Exception) {
                error = describeCampaignError(e)
            }
            if (detail?.status != "dialing") break
            delay(2000L)
        }
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = { TextButton(onClick = onDismiss) { Text(str(R.string.close)) } },
        title = { Text(name.ifBlank { str(R.string.call) }) },
        text = {
            val d = detail
            when {
                error != null -> Text(error!!, color = SangamCrimson)
                d == null -> CircularProgressIndicator()
                else -> LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.heightIn(max = 420.dp)) {
                    d.summary?.let { item { Text(it, fontWeight = FontWeight.Medium) } }
                    if (d.transcript.isNullOrEmpty()) {
                        item {
                            Text(
                                if (d.status == "dialing") str(R.string.ringing_2) else str(R.string.no_conversation_recorded),
                                color = SangamMuted,
                            )
                        }
                    }
                    items(d.transcript.orEmpty()) { turn ->
                        val agent = turn.role == "agent"
                        Surface(
                            color = if (agent) MaterialTheme.colorScheme.surfaceVariant else MaterialTheme.colorScheme.primary.copy(alpha = 0.08f),
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Column(Modifier.padding(10.dp)) {
                                Text(if (agent) str(R.string.agent) else str(R.string.customer_2), style = MaterialTheme.typography.labelSmall,
                                    color = SangamMuted)
                                Text(turn.content, style = MaterialTheme.typography.bodyMedium)
                            }
                        }
                    }
                }
            }
        },
    )
}

private fun formatClock(total: Int): String = "%d:%02d".format(total / 60, total % 60)

private fun formatDuration(total: Int): String {
    val h = total / 3600
    val m = (total % 3600) / 60
    val s = total % 60
    return when {
        h > 0 -> str(R.string.h_min, h, m)
        m > 0 -> str(R.string.min_s, m, s)
        else -> str(R.string.s, s)
    }
}
