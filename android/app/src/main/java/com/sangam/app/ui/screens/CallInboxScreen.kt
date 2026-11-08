package com.sangam.app.ui.screens

import android.content.Intent
import android.media.MediaPlayer
import android.net.Uri
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.sangam.app.network.ApiClient
import com.sangam.app.ui.theme.*
import kotlinx.coroutines.launch

data class CallLeadItem(
    val id: String,
    val callerName: String,
    val callerPhone: String,
    val service: String,
    val language: String,
    val urgency: String,
    val notes: String,
    val preferredTime: String,
    val status: String,
    val audioAsset: String,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CallInboxScreen(
    onBack: () -> Unit = {},
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var selectedFilter by remember { mutableStateOf("all") }
    var searchQuery by remember { mutableStateOf("") }
    var playingAsset by remember { mutableStateOf<String?>(null) }
    var mediaPlayer by remember { mutableStateOf<MediaPlayer?>(null) }

    val leads = remember {
        mutableStateListOf(
            CallLeadItem(
                id = "cb_01",
                callerName = "Raghavendra Ceramics Pvt Ltd",
                callerPhone = "+919845098450",
                service = "kaolin",
                language = "kn-IN (Kannada)",
                urgency = "urgent",
                notes = "25 Tonnes China Clay (Kaolin) 325 Mesh for ceramic glaze production in Peenya, Bengaluru. Requested 1kg lab sample first.",
                preferredTime = "Today 4:00 PM",
                status = "new",
                audioAsset = "audio/abhishek_kn.wav",
            ),
            CallLeadItem(
                id = "cb_02",
                callerName = "Cochin Polymers & Coatings",
                callerPhone = "+919447011223",
                service = "quartz",
                language = "ml-IN (Malayalam)",
                urgency = "normal",
                notes = "40 Tonnes high-purity Quartz / Silica powder 200 Mesh delivered to Ernakulam, Kerala. Asked for delivered price per tonne.",
                preferredTime = "Tomorrow 11:00 AM",
                status = "new",
                audioAsset = "audio/abhishek_ml.wav",
            ),
            CallLeadItem(
                id = "cb_03",
                callerName = "Deccan Glass & Refractories",
                callerPhone = "+919000122334",
                service = "feldspar",
                language = "te-IN (Telugu)",
                urgency = "urgent",
                notes = "30 Tonnes Potash Feldspar + 15 Tonnes Dolomite for Hyderabad plant. Confirmed WhatsApp catalog receipt.",
                preferredTime = "Today 5:30 PM",
                status = "contacted",
                audioAsset = "audio/abhishek_te.wav",
            ),
        )
    }

    DisposableEffect(Unit) {
        onDispose {
            mediaPlayer?.release()
        }
    }

    fun playAssetSample(assetPath: String) {
        try {
            mediaPlayer?.release()
            if (playingAsset == assetPath) {
                playingAsset = null
                return
            }
            val afd = context.assets.openFd(assetPath)
            val mp = MediaPlayer().apply {
                setDataSource(afd.fileDescriptor, afd.startOffset, afd.length)
                afd.close()
                prepare()
                setOnCompletionListener { playingAsset = null }
                start()
            }
            mediaPlayer = mp
            playingAsset = assetPath
        } catch (_: Exception) {
            playingAsset = null
        }
    }

    LaunchedEffect(Unit) {
        try {
            val remote = ApiClient.onboardingApi.listCallbacks()
            remote.forEach { row ->
                val id = row["id"]?.toString() ?: return@forEach
                if (leads.none { it.id == id }) {
                    leads.add(
                        0,
                        CallLeadItem(
                            id = id,
                            callerName = row["caller_name"]?.toString() ?: "Verified Caller",
                            callerPhone = row["caller_phone"]?.toString() ?: "+919845000000",
                            service = row["service"]?.toString() ?: "mineral_inquiry",
                            language = row["language"]?.toString() ?: "kn-IN",
                            urgency = row["urgency"]?.toString() ?: "normal",
                            notes = row["notes"]?.toString() ?: "",
                            preferredTime = row["preferred_time"]?.toString() ?: "ASAP",
                            status = row["status"]?.toString() ?: "new",
                            audioAsset = "audio/abhishek_kn.wav",
                        )
                    )
                }
            }
        } catch (_: Exception) { }
    }

    val filteredLeads = leads.filter { item ->
        val matchesFilter = selectedFilter == "all" || item.status == selectedFilter
        val matchesQuery = searchQuery.isBlank() ||
            item.callerName.contains(searchQuery, ignoreCase = true) ||
            item.callerPhone.contains(searchQuery) ||
            item.notes.contains(searchQuery, ignoreCase = true)
        matchesFilter && matchesQuery
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("AI CALL INBOX & LEAD CRM", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                        Text("+91 80 6427 0314 · Abhishek Industries", style = MaterialTheme.typography.bodySmall, color = SangamMuted)
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(
                        onClick = {
                            val csv = buildString {
                                appendLine("Caller Name,Phone,Service,Language,Urgency,Preferred Time,Status,Notes")
                                leads.forEach {
                                    appendLine("\"${it.callerName}\",\"${it.callerPhone}\",\"${it.service}\",\"${it.language}\",\"${it.urgency}\",\"${it.preferredTime}\",\"${it.status}\",\"${it.notes}\"")
                                }
                            }
                            val share = Intent(Intent.ACTION_SEND).apply {
                                type = "text/csv"
                                putExtra(Intent.EXTRA_SUBJECT, "Sangamitra AI Call Leads Export")
                                putExtra(Intent.EXTRA_TEXT, csv)
                            }
                            context.startActivity(Intent.createChooser(share, "Export Leads CSV"))
                        }
                    ) {
                        Icon(Icons.Default.Download, contentDescription = "Export CSV")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = SangamPureWhite),
            )
        },
        containerColor = SangamPureWhite,
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                OutlinedTextField(
                    value = searchQuery,
                    onValueChange = { searchQuery = it },
                    label = { Text("Search buyer, phone, mineral, or city") },
                    leadingIcon = { Icon(Icons.Default.Search, contentDescription = null) },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
            }

            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("all" to "All (${leads.size})", "new" to "New", "contacted" to "Contacted", "closed" to "Closed").forEach { (key, label) ->
                        FilterChip(
                            selected = selectedFilter == key,
                            onClick = { selectedFilter = key },
                            label = { Text(label) },
                        )
                    }
                }
            }

            items(filteredLeads, key = { it.id }) { lead ->
                OutlinedCard(
                    colors = CardDefaults.outlinedCardColors(containerColor = SangamPureWhite),
                    border = BorderStroke(1.dp, if (lead.urgency == "urgent") SangamObsidian else SangamBorder),
                ) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(lead.callerName, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                                Text(
                                    "${lead.callerPhone} · ${lead.language}",
                                    style = MaterialTheme.typography.bodySmall,
                                    fontFamily = FontFamily.Monospace,
                                    color = SangamMuted,
                                )
                            }
                            Surface(
                                color = if (lead.urgency == "urgent") SangamObsidian else SangamAlabaster,
                                shape = RoundedCornerShape(4.dp),
                            ) {
                                Text(
                                    lead.urgency.uppercase(),
                                    color = if (lead.urgency == "urgent") SangamPureWhite else SangamObsidian,
                                    style = MaterialTheme.typography.labelSmall,
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                )
                            }
                        }

                        Text(lead.notes, style = MaterialTheme.typography.bodyMedium, color = SangamObsidian)

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text("Callback Slot: ${lead.preferredTime}", style = MaterialTheme.typography.bodySmall, color = SangamMuted)
                            Text("Status: ${lead.status.uppercase()}", style = MaterialTheme.typography.labelLarge)
                        }

                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(
                                onClick = {
                                    val dial = Intent(Intent.ACTION_DIAL, Uri.parse("tel:${lead.callerPhone}"))
                                    context.startActivity(dial)
                                },
                                colors = ButtonDefaults.buttonColors(containerColor = SangamObsidian),
                                modifier = Modifier.weight(1f),
                            ) {
                                Icon(Icons.Default.Call, contentDescription = null, modifier = Modifier.size(16.dp))
                                Spacer(Modifier.width(4.dp))
                                Text("Call")
                            }

                            OutlinedButton(
                                onClick = {
                                    val msg = Uri.encode("ನಮಸ್ಕಾರ ${lead.callerName}, Abhishek Industries Tumakuru ಇಂದ ನಿಮ್ಮ ${lead.service} ವಿಚಾರಣೆಗೆ quotation ಮತ್ತು ಸ್ಯಾಂಪಲ್ ವಿವರ ಕಳಿಸುತ್ತಿದ್ದೇವೆ.")
                                    val digits = lead.callerPhone.replace("+", "")
                                    val wa = Intent(Intent.ACTION_VIEW, Uri.parse("https://wa.me/$digits?text=$msg"))
                                    context.startActivity(wa)
                                },
                                border = BorderStroke(1.dp, SangamObsidian),
                                modifier = Modifier.weight(1f),
                            ) {
                                Icon(Icons.Default.Send, contentDescription = null, modifier = Modifier.size(16.dp))
                                Spacer(Modifier.width(4.dp))
                                Text("WhatsApp")
                            }

                            OutlinedButton(
                                onClick = { playAssetSample(lead.audioAsset) },
                                border = BorderStroke(1.dp, SangamBorder),
                            ) {
                                Icon(
                                    if (playingAsset == lead.audioAsset) Icons.Default.Stop else Icons.Default.PlayArrow,
                                    contentDescription = "Play Audio",
                                    modifier = Modifier.size(16.dp),
                                )
                                Spacer(Modifier.width(4.dp))
                                Text(if (playingAsset == lead.audioAsset) "Stop" else "Audio")
                            }
                        }

                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            listOf("new" to "Mark New", "contacted" to "Mark Contacted", "closed" to "Mark Closed").forEach { (st, title) ->
                                AssistChip(
                                    onClick = {
                                        val idx = leads.indexOfFirst { it.id == lead.id }
                                        if (idx >= 0) {
                                            leads[idx] = leads[idx].copy(status = st)
                                        }
                                        scope.launch {
                                            try {
                                                ApiClient.onboardingApi.updateCallbackStatus(lead.id, mapOf("status" to st))
                                            } catch (_: Exception) { }
                                        }
                                    },
                                    label = { Text(title, style = MaterialTheme.typography.bodySmall) },
                                )
                            }
                        }
                    }
                }
            }
            item { Spacer(Modifier.height(24.dp)) }
        }
    }
}
