package com.sangam.app.ui.screens

import com.sangam.app.R
import com.sangam.app.ui.components.str

import android.content.Context
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.sangam.app.network.ApiClient
import com.sangam.app.network.CampaignCreateRequest
import com.sangam.app.network.CampaignDemoRequest
import com.sangam.app.network.CampaignDto
import com.sangam.app.network.ContactsUploadRequest
import com.sangam.app.network.VOICE_AGENT_LANGUAGES
import com.sangam.app.network.VoiceAgentDto
import com.sangam.app.ui.theme.SangamCrimson
import com.sangam.app.ui.theme.SangamMuted
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.HttpException

/**
 * Bulk AI calling: upload a contact list, set a goal, and let the voice agent
 * call everyone in parallel until the goal is met.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CampaignsScreen(onBack: () -> Unit = {}, onOpenCampaign: (String) -> Unit = {}) {
    val scope = rememberCoroutineScope()
    var campaigns by remember { mutableStateOf<List<CampaignDto>>(emptyList()) }
    var agents by remember { mutableStateOf<List<VoiceAgentDto>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var creating by remember { mutableStateOf(false) }
    var demoBusy by remember { mutableStateOf(false) }

    suspend fun refresh() {
        loading = true
        error = null
        try {
            campaigns = ApiClient.campaignApi.list()
            agents = try {
                ApiClient.voiceAgentApi.myAgents().filter { it.can_call_out }
            } catch (_: Exception) {
                emptyList()
            }
        } catch (e: Exception) {
            error = describeCampaignError(e)
        }
        loading = false
    }

    LaunchedEffect(Unit) { refresh() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(str(R.string.ai_calling_campaigns)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = str(R.string.back))
                    }
                },
                actions = {
                    IconButton(onClick = { scope.launch { refresh() } }) {
                        Icon(Icons.Default.Refresh, contentDescription = str(R.string.refresh))
                    }
                },
            )
        },
        floatingActionButton = {
            if (!creating) {
                ExtendedFloatingActionButton(
                    onClick = { creating = true },
                    icon = { Icon(Icons.Default.Add, contentDescription = null) },
                    text = { Text(str(R.string.new_campaign)) },
                )
            }
        },
    ) { padding ->
        if (creating) {
            NewCampaignForm(
                agents = agents,
                modifier = Modifier.padding(padding),
                onCancel = { creating = false },
                onStarted = { id ->
                    creating = false
                    onOpenCampaign(id)
                },
            )
            return@Scaffold
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                ElevatedCard(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(str(R.string.hundreds_of_calls_at_once), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text(
                            str(R.string.give_your_agent_a_list_and),
                            style = MaterialTheme.typography.bodyMedium,
                            color = SangamMuted,
                        )
                        OutlinedButton(
                            onClick = {
                                demoBusy = true
                                error = null
                                scope.launch {
                                    try {
                                        val c = ApiClient.campaignApi.demo(CampaignDemoRequest())
                                        onOpenCampaign(c.id)
                                    } catch (e: Exception) {
                                        error = describeCampaignError(e)
                                    }
                                    demoBusy = false
                                }
                            },
                            enabled = !demoBusy,
                        ) {
                            Icon(Icons.Default.PlayArrow, contentDescription = null)
                            Spacer(Modifier.width(8.dp))
                            Text(if (demoBusy) str(R.string.starting) else str(R.string.try_a_simulation_no_real_calls))
                        }
                    }
                }
            }
            if (loading && campaigns.isEmpty()) {
                item { LinearProgressIndicator(modifier = Modifier.fillMaxWidth()) }
            }
            error?.let { item { Text(it, color = SangamCrimson) } }
            if (campaigns.isNotEmpty()) {
                item { Text(str(R.string.your_campaigns), style = MaterialTheme.typography.titleMedium) }
            }
            items(campaigns, key = { it.id }) { c ->
                CampaignRow(c, onClick = { onOpenCampaign(c.id) })
            }
            item { Spacer(Modifier.height(72.dp)) }
        }
    }
}

@Composable
private fun CampaignRow(c: CampaignDto, onClick: () -> Unit) {
    ElevatedCard(onClick = onClick, modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(c.name, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                CampaignStatusChip(c)
            }
            LinearProgressIndicator(
                progress = { (c.success_count.toFloat() / c.target_count.coerceAtLeast(1)).coerceIn(0f, 1f) },
                modifier = Modifier.fillMaxWidth(),
            )
            Text(
                str(R.string.of_contacts, c.success_count, c.target_count, c.goal.lowercase(), c.contacts_total),
                style = MaterialTheme.typography.bodySmall,
                color = SangamMuted,
            )
        }
    }
}

@Composable
fun CampaignStatusChip(c: CampaignDto) {
    val label = when (c.status) {
        "draft" -> str(R.string.draft)
        "running" -> if (c.hold_reason != null) str(R.string.waiting) else str(R.string.calling)
        "paused" -> str(R.string.paused)
        "target_reached" -> str(R.string.goal_reached)
        "completed" -> str(R.string.finished)
        "cancelled" -> str(R.string.cancelled)
        else -> c.status
    }
    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        if (c.isSimulation) {
            AssistChip(onClick = {}, label = { Text(str(R.string.simulation)) })
        }
        AssistChip(onClick = {}, label = { Text(label) })
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun NewCampaignForm(
    agents: List<VoiceAgentDto>,
    modifier: Modifier,
    onCancel: () -> Unit,
    onStarted: (String) -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var name by remember { mutableStateOf("") }
    var goal by remember { mutableStateOf("Site visit booked") }
    var target by remember { mutableStateOf("50") }
    var pitch by remember { mutableStateOf("") }
    var business by remember { mutableStateOf("") }
    var language by remember { mutableStateOf("Telugu") }
    var concurrency by remember { mutableFloatStateOf(50f) }
    var simulate by remember { mutableStateOf(agents.isEmpty()) }
    var agent by remember { mutableStateOf(agents.firstOrNull()) }
    var consent by remember { mutableStateOf(false) }
    var csv by remember { mutableStateOf("") }
    var csvLabel by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) {
            scope.launch {
                val text = withContext(Dispatchers.IO) { readText(context, uri) }
                if (text == null) {
                    message = str(R.string.could_not_read_that_file)
                } else {
                    csv = text
                    val rows = text.lines().count { it.isNotBlank() } - 1
                    csvLabel = str(R.string.contacts_in_file, rows)
                }
            }
        }
    }

    val targetN = target.toIntOrNull() ?: 0
    val ready = name.isNotBlank() && goal.isNotBlank() && targetN > 0 && csv.isNotBlank() &&
        (simulate || (agent != null && consent))

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item { Text(str(R.string.new_campaign), style = MaterialTheme.typography.headlineSmall) }
        item {
            OutlinedTextField(name, { name = it }, label = { Text(str(R.string.campaign_name)) }, singleLine = true,
                modifier = Modifier.fillMaxWidth())
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(goal, { goal = it }, label = { Text(str(R.string.one_success_is)) }, singleLine = true,
                    modifier = Modifier.weight(2f))
                OutlinedTextField(target, { target = it.filter(Char::isDigit).take(5) }, label = { Text(str(R.string.target)) },
                    singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.weight(1f))
            }
        }
        item {
            OutlinedTextField(pitch, { pitch = it }, label = { Text(str(R.string.what_the_agent_offers)) },
                placeholder = { Text(str(R.string.outer_ring_road_villa_plots)) }, modifier = Modifier.fillMaxWidth())
        }
        item {
            OutlinedTextField(business, { business = it }, label = { Text(str(R.string.calling_on_behalf_of)) }, singleLine = true,
                modifier = Modifier.fillMaxWidth())
        }
        item {
            CampaignPicker(str(R.string.default_language), language, VOICE_AGENT_LANGUAGES) { language = VOICE_AGENT_LANGUAGES[it] }
            Text(str(R.string.a_language_column_in_your_file), style = MaterialTheme.typography.bodySmall,
                color = SangamMuted)
        }
        item {
            Text(str(R.string.calls_at_once, concurrency.toInt()), fontWeight = FontWeight.Medium)
            Slider(value = concurrency, onValueChange = { concurrency = it }, valueRange = 1f..100f)
        }
        item {
            OutlinedCard(modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(str(R.string.contacts), fontWeight = FontWeight.Bold)
                    Text(str(R.string.csv_with_a_header_row_phone),
                        style = MaterialTheme.typography.bodySmall, color = SangamMuted)
                    OutlinedButton(onClick = {
                        picker.launch(arrayOf("text/csv", "text/comma-separated-values", "text/plain", "application/vnd.ms-excel"))
                    }) {
                        Icon(Icons.Default.UploadFile, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text(csvLabel ?: str(R.string.choose_csv_file))
                    }
                }
            }
        }
        item {
            OutlinedCard(modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(str(R.string.simulation), fontWeight = FontWeight.Bold)
                            Text(str(R.string.plays_the_calls_out_without_dialling),
                                style = MaterialTheme.typography.bodySmall, color = SangamMuted)
                        }
                        Switch(checked = simulate, onCheckedChange = { simulate = it || agents.isEmpty() })
                    }
                    if (!simulate) {
                        CampaignPicker(str(R.string.voice_agent), agent?.label ?: "", agents.map { it.label }) { agent = agents[it] }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(checked = consent, onCheckedChange = { consent = it })
                            Text(
                                str(R.string.every_number_on_this_list_has),
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                        Text(str(R.string.calls_go_out_only_between_9),
                            style = MaterialTheme.typography.bodySmall, color = SangamMuted)
                    } else if (agents.isEmpty()) {
                        Text(str(R.string.real_calls_need_a_voice_agent),
                            style = MaterialTheme.typography.bodySmall, color = SangamMuted)
                    }
                }
            }
        }
        message?.let { item { Text(it, color = SangamCrimson) } }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = onCancel) { Text(str(R.string.cancel)) }
                Button(
                    onClick = {
                        busy = true
                        message = null
                        scope.launch {
                            try {
                                val api = ApiClient.campaignApi
                                val c = api.create(
                                    CampaignCreateRequest(
                                        name = name.trim(),
                                        mode = if (simulate) "simulation" else "live",
                                        app_id = if (simulate) null else agent?.app_id,
                                        goal = goal.trim(),
                                        target_count = targetN,
                                        language = language,
                                        pitch = pitch.trim().ifBlank { null },
                                        business_name = business.trim().ifBlank { null },
                                        concurrency = concurrency.toInt(),
                                        consent_confirmed = consent,
                                    )
                                )
                                val up = api.uploadContacts(c.id, ContactsUploadRequest(csv))
                                if (up.added == 0) {
                                    message = str(R.string.no_callable_numbers_in_that_file, up.invalid_count, up.suppressed)
                                } else {
                                    api.start(c.id)
                                    onStarted(c.id)
                                }
                            } catch (e: Exception) {
                                message = describeCampaignError(e)
                            }
                            busy = false
                        }
                    },
                    enabled = ready && !busy,
                    modifier = Modifier.weight(1f).height(52.dp),
                ) {
                    Icon(Icons.Default.Campaign, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(if (busy) str(R.string.starting) else str(R.string.start_calling))
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CampaignPicker(label: String, value: String, options: List<String>, onPick: (Int) -> Unit) {
    var open by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = open, onExpandedChange = { open = it }) {
        OutlinedTextField(
            value = value,
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = open) },
            modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable).fillMaxWidth(),
        )
        ExposedDropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            options.forEachIndexed { i, option ->
                DropdownMenuItem(text = { Text(option) }, onClick = { onPick(i); open = false })
            }
        }
    }
}

private fun readText(context: Context, uri: Uri): String? = try {
    context.contentResolver.openInputStream(uri)?.use { stream ->
        val bytes = stream.readBytes()
        if (bytes.size > 2_000_000) null else String(bytes, Charsets.UTF_8)
    }
} catch (_: Exception) {
    null
}

fun describeCampaignError(e: Exception): String = when (e) {
    is HttpException -> {
        val detail = try {
            e.response()?.errorBody()?.string()?.let { body ->
                Regex("\"detail\"\\s*:\\s*\"([^\"]+)\"").find(body)?.groupValues?.get(1)
            }
        } catch (_: Exception) {
            null
        }
        when (e.code()) {
            402 -> str(R.string.add_call_credit_to_run_a)
            404 -> str(R.string.that_campaign_or_agent_is_not)
            409, 422 -> detail ?: str(R.string.check_the_campaign_details_and_try)
            413 -> detail ?: str(R.string.that_list_is_too_long_for)
            else -> detail ?: str(R.string.something_went_wrong_try_again, e.code())
        }
    }
    else -> str(R.string.could_not_reach_the_server_check)
}
